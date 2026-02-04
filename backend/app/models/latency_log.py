"""
klantenservice.ai - Latency Log Model

Tracks latency metrics per turn for performance monitoring.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class LatencyLog(Base):
    """
    Latency Log model - tracks timing per turn.
    
    Used for:
    - p95/p99 latency calculations
    - Identifying bottlenecks
    - Performance monitoring
    """
    __tablename__ = "latency_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Links
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), nullable=False, index=True)
    turn_id = Column(Integer, nullable=False)
    
    # Latencies in milliseconds
    stt_latency_ms = Column(Integer, nullable=True)  # Speech-to-text (Whisper)
    orchestrator_latency_ms = Column(Integer, nullable=True)  # LLM + tool calls
    pod_latency_ms = Column(Integer, nullable=True)  # PersonaPlex processing
    tts_latency_ms = Column(Integer, nullable=True)  # Text-to-speech (if separate)
    
    # Total end-to-end latency
    total_latency_ms = Column(Integer, nullable=True)
    
    # Queue wait time (if applicable)
    queue_wait_ms = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    call_log = relationship("CallLog", backref="latency_logs")
    
    def __repr__(self):
        return f"<LatencyLog turn={self.turn_id} total={self.total_latency_ms}ms>"
