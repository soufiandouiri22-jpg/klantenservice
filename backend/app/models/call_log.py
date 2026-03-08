"""
klantenservice.ai - Call Log & Transcript Models
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Enum as SQLEnum, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class CallStatus(str, Enum):
    RINGING = "ringing"         # Call is ringing
    IN_PROGRESS = "in_progress" # Call is active
    COMPLETED = "completed"     # Call ended normally
    MISSED = "missed"           # No AI worker available
    VOICEMAIL = "voicemail"     # Went to voicemail
    FAILED = "failed"           # Technical failure
    ABANDONED = "abandoned"     # Caller hung up in queue


class CallOutcome(str, Enum):
    HANDLED = "handled"  # Call was handled by AI
    APPOINTMENT_MADE = "appointment_made"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    INFO_PROVIDED = "info_provided"
    NOTE_LEFT = "note_left"
    CALLBACK_REQUESTED = "callback_requested"
    TRANSFERRED = "transferred"
    VOICEMAIL_LEFT = "voicemail_left"
    NO_ACTION = "no_action"


class CallLog(Base):
    """
    Call Log model - represents a phone call.
    """
    __tablename__ = "call_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    ai_worker_id = Column(UUID(as_uuid=True), ForeignKey("ai_workers.id"), nullable=True)
    phone_number_id = Column(UUID(as_uuid=True), ForeignKey("phone_numbers.id"), nullable=True)
    
    # Call details
    twilio_call_sid = Column(String(50), unique=True, nullable=True, index=True)
    caller_number = Column(String(20), nullable=False)
    called_number = Column(String(20), nullable=False)
    
    # Status & Outcome
    status = Column(SQLEnum(CallStatus, values_callable=lambda x: [e.value for e in x]), default=CallStatus.RINGING)
    outcome = Column(SQLEnum(CallOutcome, values_callable=lambda x: [e.value for e in x]), nullable=True)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    answered_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)
    queue_wait_seconds = Column(Integer, default=0)
    
    # Recording
    recording_url = Column(String(500), nullable=True)
    recording_duration_seconds = Column(Integer, nullable=True)
    recording_consent_given = Column(Boolean, default=False)
    elevenlabs_conversation_id = Column(String(100), nullable=True)  # Demo calls: fetch audio via API
    
    # AI Analysis
    sentiment = Column(String(20), nullable=True)  # positive, neutral, negative
    topics = Column(JSON, default=list)  # Detected topics
    summary = Column(Text, nullable=True)  # AI-generated summary
    
    # Customer info (if detected)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    
    # Technical info
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="call_logs")
    ai_worker = relationship("AIWorker", back_populates="call_logs")
    phone_number = relationship("PhoneNumber", back_populates="call_logs")
    transcripts = relationship("CallTranscript", back_populates="call_log", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="call_log")
    internal_notes = relationship("InternalNote", back_populates="call_log")
    
    def __repr__(self):
        return f"<CallLog {self.caller_number} -> {self.called_number}>"
    
    @property
    def is_active(self) -> bool:
        return self.status in [CallStatus.RINGING, CallStatus.IN_PROGRESS]


class CallTranscript(Base):
    """
    Call Transcript model - represents the conversation transcript.
    Stored as individual messages for analysis.
    """
    __tablename__ = "call_transcripts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), nullable=False)
    
    # Message details
    speaker = Column(String(20), nullable=False)  # "caller" or "ai"
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Speech-to-text confidence
    confidence = Column(Float, nullable=True)
    
    # Tool calls (if AI used a tool)
    tool_calls = Column(JSON, nullable=True)  # e.g., {"tool": "get_availability", "params": {...}}
    
    # Relationships
    call_log = relationship("CallLog", back_populates="transcripts")
    
    def __repr__(self):
        return f"<CallTranscript {self.speaker}: {self.message[:30]}...>"


# Import Float
from sqlalchemy import Float
