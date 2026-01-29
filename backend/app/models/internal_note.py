"""
klantenservice.ai - Internal Note Model
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class NotePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class InternalNote(Base):
    """
    Internal Note model - notes left by the AI for the business.
    These are visible in the dashboard and can trigger notifications.
    """
    __tablename__ = "internal_notes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), nullable=True)
    
    # Note content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    
    # Categorization
    category = Column(String(100), nullable=True)  # e.g., "Klacht", "Vraag", "Terugbellen"
    tags = Column(JSON, default=list)
    
    # Priority
    priority = Column(SQLEnum(NotePriority, values_callable=lambda x: [e.value for e in x]), default=NotePriority.NORMAL)
    
    # Customer info
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    customer_email = Column(String(255), nullable=True)
    
    # Action required
    action_required = Column(Boolean, default=False)
    action_description = Column(Text, nullable=True)
    action_due_at = Column(DateTime, nullable=True)
    
    # Resolution
    is_resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Notifications
    notification_sent = Column(Boolean, default=False)
    notification_sent_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="internal_notes")
    call_log = relationship("CallLog", back_populates="internal_notes")
    
    def __repr__(self):
        return f"<InternalNote {self.title}>"
