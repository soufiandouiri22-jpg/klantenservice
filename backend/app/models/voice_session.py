"""
klantenservice.ai – Voice Session & Policy Decision Models

VoiceSession tracks per-call conversation state (phase, intents, flags).
PolicyDecision logs every policy checkpoint evaluation during a call.
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, Float,
    ForeignKey, Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class CallPhase(str, Enum):
    GREETING = "greeting"
    DISCOVERY = "discovery"
    ANSWERING = "answering"
    CLARIFYING = "clarifying"
    ACTION = "action"
    CLOSING = "closing"
    WAITING_GOODBYE = "waiting_goodbye"
    ESCALATING = "escalating"
    ENDED = "ended"


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), unique=True)
    call_sid = Column(String(50), unique=True, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"))

    phase = Column(String(30), default=CallPhase.GREETING.value)
    turn_count = Column(Integer, default=0)

    last_customer_intent = Column(String(30), nullable=True)
    last_customer_utterance = Column(Text, nullable=True)

    goodbye_said_by_agent = Column(Boolean, default=False)
    goodbye_said_by_customer = Column(Boolean, default=False)
    escalation_requested = Column(Boolean, default=False)
    transfer_executed = Column(Boolean, default=False)

    low_confidence_count = Column(Integer, default=0)
    repeat_topic_count = Column(Integer, default=0)
    frustration_count = Column(Integer, default=0)
    off_topic_block_count = Column(Integer, default=0)
    output_guardrail_block_count = Column(Integer, default=0)
    language_violation_count = Column(Integer, default=0)
    retrieval_count = Column(Integer, default=0)
    retrieval_skip_count = Column(Integer, default=0)
    end_call_attempts = Column(Integer, default=0)
    last_retrieval_score = Column(Float, nullable=True)

    goodbye_handshake_ok = Column(Boolean, nullable=True)
    hangup_reason = Column(String(50), nullable=True)
    ended_by = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    call_log = relationship("CallLog", backref="voice_session", uselist=False)
    policy_decisions = relationship("PolicyDecisionLog", back_populates="voice_session", cascade="all, delete-orphan")


class PolicyDecisionLog(Base):
    __tablename__ = "policy_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    voice_session_id = Column(UUID(as_uuid=True), ForeignKey("voice_sessions.id"), index=True)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), index=True)
    turn_number = Column(Integer)

    trigger_tool = Column(String(50))
    trigger_reason = Column(String(50), nullable=True)

    phase_before = Column(String(30))
    phase_after = Column(String(30))
    detected_intent = Column(String(30), nullable=True)
    intent_confidence = Column(Float, nullable=True)

    policy_name = Column(String(50))
    allowed = Column(Boolean)
    required_action = Column(String(50))
    reason_code = Column(String(50))
    instruction_nl = Column(Text, nullable=True)

    retrieval_confidence = Column(Float, nullable=True)
    retrieval_used = Column(Boolean, nullable=True)

    model_complied = Column(Boolean, nullable=True)
    violation = Column(Boolean, default=False)
    violation_type = Column(String(50), nullable=True)

    guardrail_passed = Column(Boolean, nullable=True)
    guardrail_violations = Column(Text, nullable=True)
    guardrail_safe_text = Column(Text, nullable=True)
    guardrail_original_text = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    voice_session = relationship("VoiceSession", back_populates="policy_decisions")
