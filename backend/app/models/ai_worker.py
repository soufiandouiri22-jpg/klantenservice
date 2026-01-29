"""
klantenservice.ai - AI Worker Model
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class AIWorkerStatus(str, Enum):
    AVAILABLE = "available"     # Ready to take calls
    BUSY = "busy"               # Currently in a call
    OFFLINE = "offline"         # Disabled by admin
    MAINTENANCE = "maintenance" # System maintenance


class AddressForm(str, Enum):
    FORMAL = "u"      # U-vorm (formeel)
    INFORMAL = "jij"  # Jij-vorm (informeel)


class AIWorker(Base):
    """
    AI Worker model - represents a virtual AI employee.
    Each AI worker can handle one call at a time.
    """
    __tablename__ = "ai_workers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    
    # Identity
    name = Column(String(100), nullable=False)  # e.g., "Anna", "Thomas"
    role_title = Column(String(100), default="Klantenservice medewerker")
    avatar_url = Column(String(500), nullable=True)
    
    # Voice & Language
    voice_id = Column(String(100), nullable=True)  # TTS voice identifier
    language = Column(String(10), default="nl-NL")
    
    # Behavior Settings
    address_form = Column(SQLEnum(AddressForm, values_callable=lambda x: [e.value for e in x]), default=AddressForm.FORMAL)
    tone_of_voice = Column(Text, nullable=True)  # Free text description
    
    # Behavior toggles (stored as JSON for flexibility)
    behavior_settings = Column(JSON, default=lambda: {
        "apologize_on_complaints": True,
        "always_offer_alternatives": True,
        "never_guess": True,
        "confirm_appointments": True,
        "summarize_at_end": True,
    })
    
    # Permissions
    can_make_appointments = Column(Boolean, default=True)
    can_cancel_appointments = Column(Boolean, default=False)
    can_view_prices = Column(Boolean, default=True)
    can_leave_notes = Column(Boolean, default=True)
    
    # Status
    status = Column(SQLEnum(AIWorkerStatus, values_callable=lambda x: [e.value for e in x]), default=AIWorkerStatus.AVAILABLE)
    current_call_id = Column(UUID(as_uuid=True), nullable=True)  # Active call reference
    
    # Statistics (cached, updated periodically)
    total_calls_handled = Column(Integer, default=0)
    total_appointments_made = Column(Integer, default=0)
    average_call_duration_seconds = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_call_at = Column(DateTime, nullable=True)
    
    # Active status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    company = relationship("Company", back_populates="ai_workers")
    call_logs = relationship("CallLog", back_populates="ai_worker")
    
    def __repr__(self):
        return f"<AIWorker {self.name}>"
    
    @property
    def is_available(self) -> bool:
        return self.status == AIWorkerStatus.AVAILABLE and self.is_active
    
    def start_call(self, call_id: uuid.UUID):
        """Mark worker as busy with a call."""
        self.status = AIWorkerStatus.BUSY
        self.current_call_id = call_id
    
    def end_call(self):
        """Mark worker as available after a call."""
        self.status = AIWorkerStatus.AVAILABLE
        self.current_call_id = None
        self.last_call_at = datetime.utcnow()
        self.total_calls_handled += 1


# Import Integer
from sqlalchemy import Integer
