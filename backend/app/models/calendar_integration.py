"""
klantenservice.ai - Calendar Integration Model
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class CalendarProvider(str, Enum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    CALDAV = "caldav"


class CalendarIntegration(Base):
    """
    Calendar Integration model - represents a connected calendar.
    Supports Google Calendar, Microsoft Outlook, and CalDAV.
    """
    __tablename__ = "calendar_integrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    ai_worker_id = Column(UUID(as_uuid=True), ForeignKey("ai_workers.id"), nullable=True)
    
    # Integration details
    name = Column(String(100), nullable=False)  # e.g., "Hoofdagenda", "Team Agenda"
    provider = Column(SQLEnum(CalendarProvider, values_callable=lambda x: [e.value for e in x]), nullable=False)
    
    # OAuth tokens (encrypted)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    
    # CalDAV specific
    caldav_url = Column(String(500), nullable=True)
    caldav_username = Column(String(255), nullable=True)
    caldav_password_encrypted = Column(Text, nullable=True)
    
    # Calendar ID (from provider)
    external_calendar_id = Column(String(255), nullable=True)
    external_calendar_name = Column(String(255), nullable=True)
    
    # Availability rules
    availability_rules = Column(JSON, default=lambda: {
        "default_appointment_duration_minutes": 30,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 15,
        "min_notice_hours": 1,  # Minimum notice for booking
        "max_advance_days": 60,  # How far in advance can book
        "available_hours": {
            "monday": {"start": "09:00", "end": "17:00", "enabled": True},
            "tuesday": {"start": "09:00", "end": "17:00", "enabled": True},
            "wednesday": {"start": "09:00", "end": "17:00", "enabled": True},
            "thursday": {"start": "09:00", "end": "17:00", "enabled": True},
            "friday": {"start": "09:00", "end": "17:00", "enabled": True},
            "saturday": {"start": "09:00", "end": "12:00", "enabled": False},
            "sunday": {"start": "09:00", "end": "12:00", "enabled": False},
        },
        "slot_duration_minutes": 30,
        "break_times": [],  # e.g., [{"start": "12:00", "end": "13:00"}]
    })
    
    # Appointment types this calendar handles
    appointment_types = Column(JSON, default=lambda: [
        {"id": "consultation", "name": "Consult", "duration_minutes": 30},
        {"id": "meeting", "name": "Afspraak", "duration_minutes": 60},
    ])
    
    # Meeting link provider (none, google_meet, zoom, teams)
    meeting_link_provider = Column(String(20), default="none")
    
    # Zoom OAuth tokens (stored separately from calendar provider tokens)
    zoom_access_token_encrypted = Column(Text, nullable=True)
    zoom_refresh_token_encrypted = Column(Text, nullable=True)
    zoom_token_expires_at = Column(DateTime, nullable=True)
    
    # Microsoft Teams OAuth tokens (for OnlineMeetings API)
    teams_access_token_encrypted = Column(Text, nullable=True)
    teams_refresh_token_encrypted = Column(Text, nullable=True)
    teams_token_expires_at = Column(DateTime, nullable=True)

    # Sync status
    last_sync_at = Column(DateTime, nullable=True)
    sync_error = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_primary = Column(Boolean, default=False)  # Primary calendar for new appointments
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="calendar_integrations")
    ai_worker = relationship("AIWorker", back_populates="calendar_integrations")
    appointments = relationship("Appointment", back_populates="calendar_integration")
    
    def __repr__(self):
        return f"<CalendarIntegration {self.name} ({self.provider})>"
    
    @property
    def is_token_expired(self) -> bool:
        """Check if the OAuth token is expired."""
        if not self.token_expires_at:
            return True
        return datetime.utcnow() >= self.token_expires_at

    @property
    def zoom_connected(self) -> bool:
        return self.zoom_access_token_encrypted is not None

    @property
    def teams_connected(self) -> bool:
        return self.teams_access_token_encrypted is not None
