"""
klantenservice.ai - Notification Model
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class NotificationType(str, Enum):
    DETECTED_QUESTION = "detected_question"     # New unanswered question detected
    CALL_ERROR = "call_error"                   # Call failed or had errors
    NOTE_ACTION = "note_action"                 # Note requires action
    WEBSITE_INDEXED = "website_indexed"         # Website indexing completed
    WEBSITE_FAILED = "website_failed"           # Website indexing failed
    APPOINTMENT_NEW = "appointment_new"         # New appointment created
    APPOINTMENT_CANCELLED = "appointment_cancelled"  # Appointment cancelled


class Notification(Base):
    """
    Notification model - in-app notifications for dashboard users.
    """
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    # Notification content
    type = Column(SQLEnum(NotificationType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)  # Link to relevant page

    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Notification {self.type} for company {self.company_id}>"
