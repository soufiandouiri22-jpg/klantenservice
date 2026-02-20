"""
klantenservice.ai - Context Log Model

Tracks orchestrator decisions and context injections for debugging.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class ContextLog(Base):
    """
    Context Log model - tracks orchestrator decisions per turn.
    
    Used for:
    - Debugging call issues
    - Understanding AI decisions
    - Auditing tool usage
    """
    __tablename__ = "context_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Links
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), nullable=False, index=True)
    turn_id = Column(Integer, nullable=False)
    
    # Transcripts
    user_transcript = Column(Text, nullable=True)  # What the user said (from STT)
    assistant_transcript = Column(Text, nullable=True)  # What the AI said
    
    # Orchestrator decision
    detected_intent = Column(String(100), nullable=True)  # e.g., "book_appointment", "get_prices"
    intent_confidence = Column(Integer, nullable=True)  # 0-100
    
    # Tool calls made
    tool_calls = Column(JSON, default=list)  # [{name, arguments, result, latency_ms}]
    
    # Context injection sent to the voice agent
    facts = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    
    # Model used for this turn
    model_used = Column(String(50), nullable=True)
    
    # Whether this was escalated/flagged
    was_escalated = Column(Integer, default=0)  # 0=no, 1=unknown question, 2=complaint, 3=low confidence
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    call_log = relationship("CallLog", backref="context_logs")
    
    def __repr__(self):
        return f"<ContextLog turn={self.turn_id} intent={self.detected_intent}>"
