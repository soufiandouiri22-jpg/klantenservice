"""
klantenservice.ai - Phone Number Model
"""
from datetime import datetime, time
from sqlalchemy import Column, String, DateTime, Boolean, Time, ForeignKey, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class PhoneNumber(Base):
    """
    Phone Number model - represents a phone number assigned to a company.
    Phone numbers are connected to Twilio and route to AI workers.
    """
    __tablename__ = "phone_numbers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    ai_worker_id = Column(UUID(as_uuid=True), ForeignKey("ai_workers.id"), nullable=True)  # Linked AI worker
    
    # Phone number details
    number = Column(String(20), unique=True, nullable=False, index=True)  # AI/Twilio number
    business_number = Column(String(20), nullable=True, index=True)  # Customer's actual business number (e.g., kapper's number)
    friendly_name = Column(String(100), nullable=True)  # e.g., "Kapsalon De Schaar"
    
    # Provider for forwarding instructions
    provider = Column(String(50), nullable=True)  # e.g., "kpn", "vodafone", "t-mobile", "ziggo", "odido"
    
    # Setup status
    setup_completed = Column(Boolean, default=False)  # Has the user completed the setup wizard?
    forwarding_verified = Column(Boolean, default=False)  # Has forwarding been tested successfully?
    
    # Twilio integration (hidden from user)
    twilio_sid = Column(String(50), nullable=True)
    
    # Business hours (stored as JSON for flexibility with different days)
    business_hours = Column(JSON, default=lambda: {
        "monday": {"open": "09:00", "close": "17:00", "enabled": True},
        "tuesday": {"open": "09:00", "close": "17:00", "enabled": True},
        "wednesday": {"open": "09:00", "close": "17:00", "enabled": True},
        "thursday": {"open": "09:00", "close": "17:00", "enabled": True},
        "friday": {"open": "09:00", "close": "17:00", "enabled": True},
        "saturday": {"open": "10:00", "close": "14:00", "enabled": False},
        "sunday": {"open": "00:00", "close": "00:00", "enabled": False},
    })
    
    # Queue settings
    queue_enabled = Column(Boolean, default=True)
    max_queue_size = Column(Integer, default=5)
    max_wait_time_seconds = Column(Integer, default=300)  # 5 minutes
    
    # Voicemail settings
    voicemail_enabled = Column(Boolean, default=True)
    voicemail_greeting = Column(String(500), nullable=True)
    voicemail_email = Column(String(255), nullable=True)  # Send voicemail transcripts to
    
    # SMS confirmation settings
    sms_confirmation_enabled = Column(Boolean, default=False)
    sms_confirmation_template = Column(
        String(500),
        default="Uw afspraak bij {bedrijfsnaam} is bevestigd op {datum} om {tijd}. Tot dan!"
    )

    # After hours settings
    after_hours_message = Column(
        String(500),
        default="Wij zijn momenteel gesloten. Probeert u het op een later moment nog eens."
    )
    after_hours_voicemail = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="phone_numbers")
    ai_worker = relationship("AIWorker", back_populates="phone_numbers")
    call_logs = relationship("CallLog", back_populates="phone_number")
    
    def __repr__(self):
        return f"<PhoneNumber {self.number}>"
    
    def is_within_business_hours(self, check_time: datetime = None) -> bool:
        """Check if current time (Amsterdam timezone) is within business hours."""
        from zoneinfo import ZoneInfo
        ams = ZoneInfo("Europe/Amsterdam")

        if check_time is None:
            check_time = datetime.now(ams)
        elif check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=ams)

        day_name = check_time.strftime("%A").lower()
        day_hours = self.business_hours.get(day_name, {})

        if not day_hours.get("enabled", False):
            return False

        open_time = datetime.strptime(day_hours.get("open", "09:00"), "%H:%M").time()
        close_time = datetime.strptime(day_hours.get("close", "17:00"), "%H:%M").time()
        current_time = check_time.time()

        return open_time <= current_time <= close_time


# Import Integer
from sqlalchemy import Integer
