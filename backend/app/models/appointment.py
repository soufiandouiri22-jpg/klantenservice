"""
klantenservice.ai - Appointment Model
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class AppointmentStatus(str, Enum):
    HELD = "held"           # Temporarily reserved (during call)
    CONFIRMED = "confirmed" # Confirmed appointment
    CANCELLED = "cancelled" # Cancelled by customer or business
    COMPLETED = "completed" # Appointment took place
    NO_SHOW = "no_show"     # Customer didn't show up


class Appointment(Base):
    """
    Appointment model - represents an appointment made by the AI.
    """
    __tablename__ = "appointments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    calendar_integration_id = Column(UUID(as_uuid=True), ForeignKey("calendar_integrations.id"), nullable=True)
    call_log_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"), nullable=True)
    
    # External calendar event ID
    external_event_id = Column(String(255), nullable=True)
    
    # Appointment details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    appointment_type = Column(String(100), nullable=True)  # consultation, meeting, etc.
    
    # Timing
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    
    # Customer info
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(20), nullable=True)
    customer_email = Column(String(255), nullable=True)
    
    # Status
    status = Column(SQLEnum(AppointmentStatus, values_callable=lambda x: [e.value for e in x]), default=AppointmentStatus.CONFIRMED)
    
    # Hold mechanism (for temporary reservations during calls)
    held_until = Column(DateTime, nullable=True)  # When the hold expires
    
    # Reminders
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime, nullable=True)
    
    # Cancellation
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by = Column(String(50), nullable=True)  # "customer", "business", "ai"
    cancellation_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="appointments")
    calendar_integration = relationship("CalendarIntegration", back_populates="appointments")
    call_log = relationship("CallLog", back_populates="appointments")
    
    def __repr__(self):
        return f"<Appointment {self.title} @ {self.starts_at}>"
    
    @property
    def is_upcoming(self) -> bool:
        return self.starts_at > datetime.utcnow() and self.status == AppointmentStatus.CONFIRMED
    
    @property
    def is_held(self) -> bool:
        """Check if appointment is in held state and still valid."""
        if self.status != AppointmentStatus.HELD:
            return False
        if self.held_until and datetime.utcnow() > self.held_until:
            return False
        return True
