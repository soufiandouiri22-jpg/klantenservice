"""
klantenservice.ai - Phone Number Schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class BusinessHours(BaseModel):
    """Business hours for a single day."""
    open: str = "09:00"
    close: str = "17:00"
    enabled: bool = True


class AllBusinessHours(BaseModel):
    """Business hours for all days of the week."""
    monday: BusinessHours = BusinessHours()
    tuesday: BusinessHours = BusinessHours()
    wednesday: BusinessHours = BusinessHours()
    thursday: BusinessHours = BusinessHours()
    friday: BusinessHours = BusinessHours()
    saturday: BusinessHours = BusinessHours(open="10:00", close="14:00", enabled=False)
    sunday: BusinessHours = BusinessHours(open="00:00", close="00:00", enabled=False)


class PhoneNumberBase(BaseModel):
    friendly_name: Optional[str] = Field(None, max_length=100)


class PhoneNumberCreate(PhoneNumberBase):
    """Schema for creating/assigning a phone number."""
    number: str = Field(..., min_length=10, max_length=20)


class PhoneNumberUpdate(BaseModel):
    """Schema for updating a phone number."""
    friendly_name: Optional[str] = Field(None, max_length=100)
    business_hours: Optional[AllBusinessHours] = None
    queue_enabled: Optional[bool] = None
    max_queue_size: Optional[int] = Field(None, ge=1, le=50)
    max_wait_time_seconds: Optional[int] = Field(None, ge=30, le=900)
    voicemail_enabled: Optional[bool] = None
    voicemail_greeting: Optional[str] = None
    voicemail_email: Optional[str] = None
    after_hours_message: Optional[str] = None
    after_hours_voicemail: Optional[bool] = None
    is_active: Optional[bool] = None


class PhoneNumberResponse(PhoneNumberBase):
    """Schema for phone number response."""
    id: UUID
    company_id: UUID
    number: str
    business_hours: Dict[str, Any]
    queue_enabled: bool
    max_queue_size: int
    max_wait_time_seconds: int
    voicemail_enabled: bool
    voicemail_greeting: Optional[str]
    voicemail_email: Optional[str]
    after_hours_message: str
    after_hours_voicemail: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PhoneNumberStats(BaseModel):
    """Statistics for a phone number."""
    calls_today: int
    calls_this_week: int
    calls_this_month: int
    average_wait_time_seconds: int
    missed_calls_today: int
    voicemails_today: int
