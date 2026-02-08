"""
klantenservice.ai - Calendar Integration Schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID

from app.models.calendar_integration import CalendarProvider


class AppointmentType(BaseModel):
    """Appointment type configuration."""
    id: str
    name: str
    duration_minutes: int = 30


class AvailableHours(BaseModel):
    """Available hours for a single day."""
    start: str = "09:00"
    end: str = "17:00"
    enabled: bool = True


class AvailabilityRules(BaseModel):
    """Availability rules for calendar."""
    default_appointment_duration_minutes: int = 30
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 15
    min_notice_hours: int = 1
    max_advance_days: int = 60
    slot_duration_minutes: int = 30
    available_hours: Optional[Dict[str, AvailableHours]] = None
    break_times: List[Dict[str, str]] = []


class CalendarIntegrationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CalendarIntegrationCreate(CalendarIntegrationBase):
    """Schema for creating a calendar integration."""
    ai_worker_id: Optional[UUID] = None
    provider: CalendarProvider
    # CalDAV specific
    caldav_url: Optional[str] = None
    caldav_username: Optional[str] = None
    caldav_password: Optional[str] = None


class CalendarIntegrationUpdate(BaseModel):
    """Schema for updating a calendar integration."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    availability_rules: Optional[AvailabilityRules] = None
    appointment_types: Optional[List[AppointmentType]] = None
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None


class CalendarIntegrationResponse(CalendarIntegrationBase):
    """Schema for calendar integration response."""
    id: UUID
    company_id: UUID
    ai_worker_id: Optional[UUID] = None
    provider: CalendarProvider
    external_calendar_name: Optional[str]
    availability_rules: Dict[str, Any]
    appointment_types: List[Dict[str, Any]]
    last_sync_at: Optional[datetime]
    sync_error: Optional[str]
    is_active: bool
    is_primary: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AvailabilitySlot(BaseModel):
    """An available time slot."""
    start: datetime
    end: datetime
    duration_minutes: int


class AvailabilityRequest(BaseModel):
    """Request for available time slots."""
    start_date: datetime
    end_date: datetime
    duration_minutes: int = 30
    appointment_type: Optional[str] = None


class AvailabilityResponse(BaseModel):
    """Response with available time slots."""
    slots: List[AvailabilitySlot]
    calendar_id: UUID
    calendar_name: str


class HoldSlotRequest(BaseModel):
    """Request to temporarily hold a slot."""
    slot: AvailabilitySlot
    hold_duration_seconds: int = Field(default=300, le=600)  # Max 10 minutes


class HoldSlotResponse(BaseModel):
    """Response for held slot."""
    hold_id: UUID
    slot: AvailabilitySlot
    expires_at: datetime


class OAuthCallbackParams(BaseModel):
    """OAuth callback parameters."""
    code: str
    state: str
