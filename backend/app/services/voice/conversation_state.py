"""
Conversation State Manager — tracks per-call state across tool invocations.

State is persisted to the voice_sessions table so it survives across
the multiple HTTP requests that ElevenLabs makes for server tool calls.
"""
import logging
import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.voice_session import VoiceSession, CallPhase
from .intent_classifier import CallerIntent

logger = logging.getLogger(__name__)

_FRUSTRATION_RE = re.compile(
    r"\b("
    r"(?:dat\s+)?bedoel\s+ik\s+niet|dat\s+is\s+niet\s+wat\s+ik|"
    r"je\s+begrijpt\s+(?:me|mij)\s+niet|u\s+begrijpt\s+(?:me|mij)\s+niet|"
    r"nog\s+steeds\s+niet|dat\s+heb\s+ik\s+al|"
    r"luister\s+(?:je|u)\s+(?:wel|eigenlijk)|dat\s+zei\s+ik|"
    r"dat\s+(?:klopt|helpt)\s+(?:niet|helemaal\s+niet)|"
    r"we\s+draaien\s+in\s+(?:rondjes|cirkels|kringetjes)|"
    r"nee\s+(?:dat\s+)?(?:bedoel|klopt|snap)\s+ik\s+niet"
    r")\b",
    re.I,
)


class ConversationStateManager:
    """
    Get-or-create + update conversation state for a call.

    Usage:
        mgr = ConversationStateManager(db)
        session = mgr.get_or_create(call_sid, call_log_id, company_id)
        mgr.record_turn(session, intent, utterance, tool_name)
    """

    def __init__(self, db: Session):
        self.db = db

    def get_or_create(
        self,
        call_sid: str,
        call_log_id: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> VoiceSession:
        session = self.db.query(VoiceSession).filter(
            VoiceSession.call_sid == call_sid,
        ).first()

        if session:
            return session

        session = VoiceSession(
            id=uuid4(),
            call_sid=call_sid,
            call_log_id=call_log_id,
            company_id=company_id,
            phase=CallPhase.GREETING.value,
        )
        self.db.add(session)
        self.db.flush()
        logger.info("[state] created voice_session for call_sid=%s", call_sid)
        return session

    def record_turn(
        self,
        session: VoiceSession,
        intent: CallerIntent,
        utterance: str,
        tool_name: str,
        confidence: Optional[float] = None,
    ) -> VoiceSession:
        """Update state based on the latest turn."""
        prev_intent = session.last_customer_intent
        session.turn_count = (session.turn_count or 0) + 1
        session.last_customer_intent = intent.value
        session.last_customer_utterance = (utterance or "")[:2000]
        session.updated_at = datetime.utcnow()

        # Phase transitions
        self._update_phase(session, intent, tool_name)

        # Track retrieval
        if tool_name == "search_knowledge":
            session.retrieval_count = (session.retrieval_count or 0) + 1

        # Track goodbye signals
        if intent == CallerIntent.GOODBYE:
            session.goodbye_said_by_customer = True

        if intent == CallerIntent.GRATITUDE:
            pass

        # Track escalation signals
        if intent in (CallerIntent.ANGER, CallerIntent.TRANSFER_REQUEST):
            session.escalation_requested = True

        # Track frustration signals
        if intent == CallerIntent.FRUSTRATION:
            session.frustration_count = (session.frustration_count or 0) + 1
            session.repeat_topic_count = (session.repeat_topic_count or 0) + 1
        elif utterance and _FRUSTRATION_RE.search(utterance):
            session.frustration_count = (session.frustration_count or 0) + 1
            session.repeat_topic_count = (session.repeat_topic_count or 0) + 1

        # Track same-topic repetition (same intent in consecutive retrieval turns)
        if (
            prev_intent
            and intent.value == prev_intent
            and intent in (CallerIntent.QUESTION, CallerIntent.PRICING)
            and tool_name in ("search_knowledge", "get_prices")
        ):
            session.repeat_topic_count = (session.repeat_topic_count or 0) + 1

        # Track transfer
        if tool_name == "transfer_call":
            session.transfer_executed = True
            session.phase = CallPhase.ESCALATING.value

        self.db.flush()
        return session

    def mark_agent_goodbye(self, session: VoiceSession) -> None:
        """Called when the agent initiates closing."""
        session.goodbye_said_by_agent = True
        if session.phase not in (CallPhase.ENDED.value, CallPhase.ESCALATING.value):
            session.phase = CallPhase.CLOSING.value
        self.db.flush()

    def mark_waiting_goodbye(self, session: VoiceSession) -> None:
        session.phase = CallPhase.WAITING_GOODBYE.value
        session.end_call_attempts = (session.end_call_attempts or 0) + 1
        self.db.flush()

    def mark_ended(
        self,
        session: VoiceSession,
        ended_by: str = "agent",
        hangup_reason: str = "normal",
    ) -> None:
        session.phase = CallPhase.ENDED.value
        session.ended_by = ended_by
        session.hangup_reason = hangup_reason
        session.goodbye_handshake_ok = (
            session.goodbye_said_by_agent and session.goodbye_said_by_customer
        )
        self.db.flush()

    def record_low_confidence(self, session: VoiceSession, score: float = 0.0) -> None:
        session.low_confidence_count = (session.low_confidence_count or 0) + 1
        session.last_retrieval_score = score
        self.db.flush()

    def record_repeat_topic(self, session: VoiceSession) -> None:
        session.repeat_topic_count = (session.repeat_topic_count or 0) + 1
        self.db.flush()

    def record_off_topic_block(self, session: VoiceSession) -> None:
        session.off_topic_block_count = (session.off_topic_block_count or 0) + 1
        session.retrieval_skip_count = (session.retrieval_skip_count or 0) + 1
        self.db.flush()

    def record_output_guardrail_block(self, session: VoiceSession) -> None:
        session.output_guardrail_block_count = (session.output_guardrail_block_count or 0) + 1
        self.db.flush()

    def record_language_violation(self, session: VoiceSession) -> None:
        session.language_violation_count = (session.language_violation_count or 0) + 1
        self.db.flush()

    def record_retrieval_score(self, session: VoiceSession, score: float) -> None:
        session.last_retrieval_score = score
        self.db.flush()

    def _update_phase(
        self,
        session: VoiceSession,
        intent: CallerIntent,
        tool_name: str,
    ) -> None:
        current = session.phase

        if current == CallPhase.ENDED.value:
            return

        if current == CallPhase.GREETING.value:
            if intent in (CallerIntent.QUESTION, CallerIntent.PRICING,
                          CallerIntent.APPOINTMENT, CallerIntent.COMPLAINT):
                session.phase = CallPhase.DISCOVERY.value
            elif intent == CallerIntent.GOODBYE:
                session.phase = CallPhase.CLOSING.value

        elif current == CallPhase.DISCOVERY.value:
            if tool_name in ("search_knowledge",):
                session.phase = CallPhase.ANSWERING.value
            elif tool_name in ("check_availability", "book_appointment"):
                session.phase = CallPhase.ACTION.value
            elif intent == CallerIntent.GOODBYE:
                session.phase = CallPhase.CLOSING.value

        elif current == CallPhase.ANSWERING.value:
            if intent == CallerIntent.GOODBYE:
                session.phase = CallPhase.CLOSING.value
            elif intent == CallerIntent.UNCLEAR:
                session.phase = CallPhase.CLARIFYING.value
            elif tool_name in ("check_availability", "book_appointment"):
                session.phase = CallPhase.ACTION.value

        elif current == CallPhase.CLARIFYING.value:
            if intent in (CallerIntent.QUESTION, CallerIntent.PRICING):
                session.phase = CallPhase.ANSWERING.value
            elif intent == CallerIntent.GOODBYE:
                session.phase = CallPhase.CLOSING.value

        elif current == CallPhase.ACTION.value:
            if intent == CallerIntent.GOODBYE:
                session.phase = CallPhase.CLOSING.value
            elif intent in (CallerIntent.QUESTION, CallerIntent.PRICING):
                session.phase = CallPhase.DISCOVERY.value

        elif current == CallPhase.CLOSING.value:
            if intent == CallerIntent.GOODBYE:
                session.goodbye_said_by_customer = True

        elif current == CallPhase.WAITING_GOODBYE.value:
            if intent == CallerIntent.GOODBYE:
                session.goodbye_said_by_customer = True

        # Escalation override (anger or explicit transfer request)
        if intent in (CallerIntent.ANGER, CallerIntent.TRANSFER_REQUEST):
            if current not in (CallPhase.ENDED.value, CallPhase.ESCALATING.value):
                session.phase = CallPhase.ESCALATING.value

        # Frustration pushes to clarifying (not escalating — yet)
        if intent == CallerIntent.FRUSTRATION:
            if current in (CallPhase.ANSWERING.value, CallPhase.DISCOVERY.value):
                session.phase = CallPhase.CLARIFYING.value
