"""
klantenservice.ai - Call Evaluation Model
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class CallEvaluation(Base):
    __tablename__ = "call_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), nullable=False, unique=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    quality_score = Column(Integer, nullable=False)
    hallucination_detected = Column(Boolean, default=False, nullable=False)
    wrong_tool_detected = Column(Boolean, default=False, nullable=False)
    customer_helped = Column(Boolean, default=True, nullable=False)
    needs_review = Column(Boolean, default=False, nullable=False)

    latency_ms = Column(Integer, nullable=True)
    summary = Column(Text, nullable=True)
    issues = Column(JSON, default=list)
    tool_usage = Column(JSON, default=list)

    langsmith_run_id = Column(String(100), nullable=True)
    evaluator_model = Column(String(50), default="gpt-4o-mini")

    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    call_log = relationship("CallLog", backref="evaluation", uselist=False)
    company = relationship("Company")

    def __repr__(self):
        return f"<CallEvaluation call={self.call_log_id} score={self.quality_score}>"
