"""
klantenservice.ai - Usage Log Model

Tracks API usage (LLM tokens, STT seconds) for cost monitoring.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


# Cost rates (in cents per unit)
COST_RATES = {
    # OpenAI pricing (approximate, in cents)
    "gpt-4o-mini": {"input": 0.015, "output": 0.06},  # per 1K tokens
    "gpt-4o": {"input": 0.25, "output": 1.0},  # per 1K tokens
    "gpt-3.5-turbo": {"input": 0.05, "output": 0.15},  # per 1K tokens
    "whisper-1": 0.6,  # per minute
}


class UsageLog(Base):
    """
    Usage Log model - tracks API usage per call/turn.
    
    Used for:
    - Cost monitoring per company
    - Platform-wide usage metrics
    - Daily/monthly reports
    """
    __tablename__ = "usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Links
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), nullable=True, index=True)
    turn_id = Column(Integer, nullable=True)  # Which turn in the conversation
    
    # STT Usage
    stt_seconds = Column(Float, default=0)  # Whisper seconds
    stt_model = Column(String(50), default="whisper-1")
    
    # LLM Usage
    llm_input_tokens = Column(Integer, default=0)
    llm_output_tokens = Column(Integer, default=0)
    llm_model = Column(String(50))  # gpt-4o-mini, gpt-4o, etc.
    
    # Calculated costs (in cents for precision)
    stt_cost_cents = Column(Integer, default=0)
    llm_cost_cents = Column(Integer, default=0)
    total_cost_cents = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    company = relationship("Company", backref="usage_logs")
    call_log = relationship("CallLog", backref="usage_logs")
    
    def __repr__(self):
        return f"<UsageLog company={self.company_id} cost={self.total_cost_cents}c>"
    
    def calculate_costs(self):
        """Calculate costs based on usage and rates."""
        # STT cost
        if self.stt_seconds and self.stt_model in ["whisper-1"]:
            minutes = self.stt_seconds / 60
            self.stt_cost_cents = int(minutes * COST_RATES["whisper-1"] * 100)
        
        # LLM cost
        if self.llm_model and self.llm_model in COST_RATES:
            rates = COST_RATES[self.llm_model]
            input_cost = (self.llm_input_tokens / 1000) * rates["input"]
            output_cost = (self.llm_output_tokens / 1000) * rates["output"]
            self.llm_cost_cents = int((input_cost + output_cost) * 100)
        
        self.total_cost_cents = self.stt_cost_cents + self.llm_cost_cents
