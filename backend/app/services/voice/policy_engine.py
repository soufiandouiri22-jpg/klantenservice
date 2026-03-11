"""
Policy Engine — deterministic rule enforcement for voice calls.

Evaluates policies based on conversation state and caller intent.
Returns machine-readable decisions with Dutch instructions for the AI.

Every policy evaluation is logged to the policy_decisions table.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.voice_session import VoiceSession, PolicyDecisionLog, CallPhase
from .intent_classifier import CallerIntent

logger = logging.getLogger(__name__)


@dataclass
class PolicyResult:
    """Machine-readable policy decision."""
    allowed: bool
    policy_name: str
    required_action: str       # "proceed", "wait", "escalate", "clarify", "reprompt", "block"
    reason_code: str
    instruction_nl: str = ""   # Dutch instruction for the AI
    phase_after: str = ""      # new phase to transition to (empty = no change)

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "policy_name": self.policy_name,
            "required_action": self.required_action,
            "reason_code": self.reason_code,
            "instruction_nl": self.instruction_nl,
        }


# ── Individual policy functions ────────────────────────────────────


def _policy_goodbye_handshake(
    session: VoiceSession,
    intent: CallerIntent,
) -> PolicyResult:
    """
    Rule: Do not end the call until the customer has also said goodbye.
    """
    customer_goodbye = session.goodbye_said_by_customer or intent == CallerIntent.GOODBYE

    if customer_goodbye:
        return PolicyResult(
            allowed=True,
            policy_name="goodbye_handshake",
            required_action="proceed",
            reason_code="customer_said_goodbye",
            instruction_nl="De klant heeft afscheid genomen. Je mag het gesprek nu beëindigen met end_call.",
            phase_after=CallPhase.ENDED.value,
        )

    # Customer hasn't said goodbye yet
    agent_already_said_bye = session.goodbye_said_by_agent
    attempts = (session.end_call_attempts or 0) + 1

    if attempts >= 3:
        return PolicyResult(
            allowed=True,
            policy_name="goodbye_handshake",
            required_action="proceed",
            reason_code="max_attempts_reached",
            instruction_nl="Je hebt al meerdere keren afscheid genomen. Je mag het gesprek nu beëindigen.",
            phase_after=CallPhase.ENDED.value,
        )

    if agent_already_said_bye:
        return PolicyResult(
            allowed=False,
            policy_name="goodbye_handshake",
            required_action="wait",
            reason_code="customer_not_goodbye",
            instruction_nl=(
                "De klant heeft nog niet gedag gezegd. "
                "Wacht stil tot de klant reageert. Zeg NIETS meer. "
                "Als de klant iets zegt, reageer dan kort en neem opnieuw afscheid."
            ),
            phase_after=CallPhase.WAITING_GOODBYE.value,
        )

    return PolicyResult(
        allowed=False,
        policy_name="goodbye_handshake",
        required_action="wait",
        reason_code="agent_not_goodbye",
        instruction_nl=(
            "Neem eerst afscheid van de klant. Zeg bijvoorbeeld 'Fijne dag!' "
            "en wacht dan tot de klant ook afscheid neemt."
        ),
        phase_after=CallPhase.CLOSING.value,
    )


def _policy_escalation(
    session: VoiceSession,
    intent: CallerIntent,
) -> PolicyResult:
    """
    Rule: Escalate when customer is angry, requests a human, or
    repeated failures have occurred.
    """
    if intent == CallerIntent.TRANSFER_REQUEST:
        return PolicyResult(
            allowed=True,
            policy_name="escalation",
            required_action="escalate",
            reason_code="customer_requested_human",
            instruction_nl=(
                "De klant wil graag met een medewerker spreken. "
                "Zeg: 'Ik verbind u door met een collega.' en gebruik transfer_call."
            ),
            phase_after=CallPhase.ESCALATING.value,
        )

    if intent == CallerIntent.ANGER:
        low_conf = (session.low_confidence_count or 0) >= 1
        repeat = (session.repeat_topic_count or 0) >= 1

        if low_conf or repeat:
            return PolicyResult(
                allowed=True,
                policy_name="escalation",
                required_action="escalate",
                reason_code="anger_plus_failure",
                instruction_nl=(
                    "De klant is gefrustreerd en je hebt eerder het antwoord niet kunnen vinden. "
                    "Bied aan om door te verbinden: 'Het spijt me. Zal ik u doorverbinden met een collega die u verder kan helpen?'"
                ),
                phase_after=CallPhase.ESCALATING.value,
            )

        return PolicyResult(
            allowed=False,
            policy_name="escalation",
            required_action="clarify",
            reason_code="anger_detected",
            instruction_nl=(
                "De klant klinkt gefrustreerd. Toon begrip: 'Ik begrijp dat dit vervelend is.' "
                "Probeer het probleem op te lossen. Als dat niet lukt, bied doorverbinden aan."
            ),
        )

    if (session.low_confidence_count or 0) >= 3:
        return PolicyResult(
            allowed=True,
            policy_name="escalation",
            required_action="escalate",
            reason_code="repeated_low_confidence",
            instruction_nl=(
                "Je hebt meerdere keren het antwoord niet kunnen vinden. "
                "Bied aan: 'Ik kan u hier helaas niet goed mee helpen. "
                "Zal ik een collega vragen om u terug te bellen?'"
            ),
            phase_after=CallPhase.ESCALATING.value,
        )

    return PolicyResult(
        allowed=False,
        policy_name="escalation",
        required_action="proceed",
        reason_code="no_escalation_needed",
    )


def _policy_low_confidence(
    session: VoiceSession,
    intent: CallerIntent,
    retrieval_confidence: float,
) -> PolicyResult:
    """
    Rule: If retrieval confidence is low, ask for clarification
    instead of risking hallucination.
    """
    if retrieval_confidence >= 0.4:
        return PolicyResult(
            allowed=True,
            policy_name="low_confidence",
            required_action="proceed",
            reason_code="confidence_ok",
        )

    if retrieval_confidence >= 0.2:
        return PolicyResult(
            allowed=True,
            policy_name="low_confidence",
            required_action="proceed",
            reason_code="confidence_marginal",
            instruction_nl=(
                "Je bent niet helemaal zeker van dit antwoord. "
                "Vermeld dat je het even gaat nakijken of bied aan om een collega te laten terugbellen."
            ),
        )

    return PolicyResult(
        allowed=False,
        policy_name="low_confidence",
        required_action="clarify",
        reason_code="confidence_too_low",
        instruction_nl=(
            "Je hebt geen betrouwbaar antwoord gevonden. VERZIN NIETS. "
            "Zeg eerlijk: 'Ik heb het antwoord niet direct bij de hand. "
            "Zal ik een notitie maken zodat een collega u terugbelt met het antwoord?'"
        ),
    )


def _policy_repeated_failure(
    session: VoiceSession,
    intent: CallerIntent,
) -> PolicyResult:
    """
    Rule: If the same topic keeps failing, escalate or reframe.
    """
    repeats = session.repeat_topic_count or 0

    if repeats < 2:
        return PolicyResult(
            allowed=True,
            policy_name="repeated_failure",
            required_action="proceed",
            reason_code="within_threshold",
        )

    if repeats < 4:
        return PolicyResult(
            allowed=False,
            policy_name="repeated_failure",
            required_action="clarify",
            reason_code="topic_repeated",
            instruction_nl=(
                "De klant heeft dit onderwerp al meerdere keren aangekaart. "
                "Probeer de vraag anders te benaderen of vraag de klant specifiek "
                "wat er nog onduidelijk is."
            ),
        )

    return PolicyResult(
        allowed=True,
        policy_name="repeated_failure",
        required_action="escalate",
        reason_code="topic_loop_detected",
        instruction_nl=(
            "Dit onderwerp is al meerdere keren besproken zonder oplossing. "
            "Bied aan om een collega te laten terugbellen met een definitief antwoord."
        ),
        phase_after=CallPhase.ESCALATING.value,
    )


def _policy_off_topic(
    session: VoiceSession,
    intent: CallerIntent,
) -> PolicyResult:
    """
    Rule: Block off-topic requests. Redirect to company scope.
    """
    if intent != CallerIntent.OFF_TOPIC:
        return PolicyResult(
            allowed=True,
            policy_name="scope_guard",
            required_action="proceed",
            reason_code="on_topic",
        )

    return PolicyResult(
        allowed=False,
        policy_name="scope_guard",
        required_action="block",
        reason_code="off_topic",
        instruction_nl=(
            "Dit onderwerp valt buiten je werkgebied. "
            "Zeg vriendelijk: 'Daar kan ik u helaas niet mee helpen, "
            "maar ik help u graag met vragen over onze diensten!'"
        ),
    )


def _policy_silence(
    session: VoiceSession,
    intent: CallerIntent,
) -> PolicyResult:
    """
    Rule: Reprompt on silence. Escalate after repeated silence.
    """
    if intent != CallerIntent.SILENCE:
        return PolicyResult(
            allowed=True,
            policy_name="silence_handler",
            required_action="proceed",
            reason_code="not_silent",
        )

    turn = session.turn_count or 0
    if turn <= 1:
        return PolicyResult(
            allowed=False,
            policy_name="silence_handler",
            required_action="reprompt",
            reason_code="initial_silence",
            instruction_nl="Hallo, bent u daar? Waarmee kan ik u helpen?",
        )

    return PolicyResult(
        allowed=False,
        policy_name="silence_handler",
        required_action="reprompt",
        reason_code="mid_call_silence",
        instruction_nl="Ik hoorde u even niet. Kunt u dat herhalen?",
    )


# ── Policy Engine (orchestrator) ───────────────────────────────────


# Map trigger reasons to the policies they invoke
_REASON_POLICIES = {
    "ending_call": [_policy_goodbye_handshake],
    "escalation": [_policy_escalation],
    "low_confidence": [_policy_low_confidence],
    "repeated_failure": [_policy_repeated_failure],
    "off_topic": [_policy_off_topic],
    "silence": [_policy_silence],
}


class PolicyEngine:
    """
    Evaluate one or more policies for a given trigger reason.

    Each evaluation is logged to the policy_decisions table.
    """

    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self,
        session: VoiceSession,
        intent: CallerIntent,
        trigger_tool: str,
        trigger_reason: str,
        intent_confidence: float = 0.0,
        retrieval_confidence: float = 1.0,
    ) -> PolicyResult:
        """
        Run all policies for the given reason. Return the most restrictive result.
        """
        policies = _REASON_POLICIES.get(trigger_reason, [])

        if not policies:
            return self._evaluate_auto(session, intent, trigger_tool,
                                       retrieval_confidence)

        phase_before = session.phase

        results: list[PolicyResult] = []
        for policy_fn in policies:
            if policy_fn == _policy_low_confidence:
                result = policy_fn(session, intent, retrieval_confidence)
            else:
                result = policy_fn(session, intent)
            results.append(result)

        # Pick most restrictive (first non-allowed, or last)
        final = next((r for r in results if not r.allowed), results[-1])

        # Apply phase transition
        if final.phase_after:
            session.phase = final.phase_after

        # Log
        self._log_decision(
            session=session,
            trigger_tool=trigger_tool,
            trigger_reason=trigger_reason,
            phase_before=phase_before,
            intent=intent,
            intent_confidence=intent_confidence,
            result=final,
        )

        return final

    def evaluate_all(
        self,
        session: VoiceSession,
        intent: CallerIntent,
        trigger_tool: str,
        intent_confidence: float = 0.0,
        retrieval_confidence: float = 1.0,
    ) -> Optional[PolicyResult]:
        """
        Run all applicable auto-triggered policies (called on every tool invocation).
        Returns the most restrictive result, or None if all pass.
        """
        return self._evaluate_auto(
            session, intent, trigger_tool, retrieval_confidence,
        )

    def _evaluate_auto(
        self,
        session: VoiceSession,
        intent: CallerIntent,
        trigger_tool: str,
        retrieval_confidence: float,
    ) -> Optional[PolicyResult]:
        """
        Auto-triggered policies that run on every tool call regardless of reason.
        """
        phase_before = session.phase
        checks = []

        # Always check escalation signals
        esc = _policy_escalation(session, intent)
        if esc.required_action == "escalate":
            checks.append(esc)

        # Always check off-topic
        ot = _policy_off_topic(session, intent)
        if not ot.allowed:
            checks.append(ot)

        # Always check silence
        sil = _policy_silence(session, intent)
        if not sil.allowed:
            checks.append(sil)

        # Check repeated failure
        rf = _policy_repeated_failure(session, intent)
        if not rf.allowed or rf.required_action == "escalate":
            checks.append(rf)

        if not checks:
            return None

        final = checks[0]

        if final.phase_after:
            session.phase = final.phase_after

        self._log_decision(
            session=session,
            trigger_tool=trigger_tool,
            trigger_reason="auto",
            phase_before=phase_before,
            intent=intent,
            intent_confidence=0.0,
            result=final,
        )

        return final

    def _log_decision(
        self,
        session: VoiceSession,
        trigger_tool: str,
        trigger_reason: str,
        phase_before: str,
        intent: CallerIntent,
        intent_confidence: float,
        result: PolicyResult,
    ) -> None:
        try:
            log = PolicyDecisionLog(
                id=uuid4(),
                voice_session_id=session.id,
                call_log_id=session.call_log_id,
                turn_number=session.turn_count or 0,
                trigger_tool=trigger_tool,
                trigger_reason=trigger_reason,
                phase_before=phase_before,
                phase_after=result.phase_after or session.phase,
                detected_intent=intent.value,
                intent_confidence=intent_confidence,
                policy_name=result.policy_name,
                allowed=result.allowed,
                required_action=result.required_action,
                reason_code=result.reason_code,
                instruction_nl=result.instruction_nl or None,
            )
            self.db.add(log)
            self.db.flush()
        except Exception:
            logger.warning("Failed to log policy decision", exc_info=True)

        logger.info(
            "[policy] call=%s tool=%s reason=%s policy=%s allowed=%s action=%s code=%s",
            session.call_sid, trigger_tool, trigger_reason,
            result.policy_name, result.allowed,
            result.required_action, result.reason_code,
        )
