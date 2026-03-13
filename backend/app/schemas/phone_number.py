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
    """Schema for starting the phone setup wizard - user enters their business number."""
    business_number: str = Field(..., min_length=10, max_length=20, description="The customer's actual business phone number")
    ai_worker_id: Optional[UUID] = None  # Link to an AI worker


class PhoneNumberUpdate(BaseModel):
    """Schema for updating a phone number."""
    friendly_name: Optional[str] = Field(None, max_length=100)
    business_number: Optional[str] = Field(None, max_length=20)
    provider: Optional[str] = Field(None, max_length=50)
    setup_completed: Optional[bool] = None
    forwarding_verified: Optional[bool] = None
    ai_worker_id: Optional[UUID] = None  # Link to an AI worker
    business_hours: Optional[AllBusinessHours] = None
    queue_enabled: Optional[bool] = None
    max_queue_size: Optional[int] = Field(None, ge=1, le=50)
    max_wait_time_seconds: Optional[int] = Field(None, ge=30, le=900)
    voicemail_enabled: Optional[bool] = None
    voicemail_greeting: Optional[str] = None
    voicemail_email: Optional[str] = None
    sms_confirmation_enabled: Optional[bool] = None
    sms_confirmation_template: Optional[str] = None
    email_confirmation_enabled: Optional[bool] = None
    email_confirmation_template: Optional[str] = None
    sms_callback_template: Optional[str] = None
    transfer_enabled: Optional[bool] = None
    transfer_number: Optional[str] = Field(None, max_length=20)
    after_hours_message: Optional[str] = None
    after_hours_voicemail: Optional[bool] = None
    is_active: Optional[bool] = None


class PhoneNumberResponse(PhoneNumberBase):
    """Schema for phone number response."""
    id: UUID
    company_id: UUID
    ai_worker_id: Optional[UUID] = None
    number: str  # AI/Twilio number (hidden from user in UI)
    business_number: Optional[str] = None  # Customer's actual business number
    provider: Optional[str] = None
    setup_completed: bool = False
    forwarding_verified: bool = False
    business_hours: Dict[str, Any]
    queue_enabled: bool
    max_queue_size: int
    max_wait_time_seconds: int
    voicemail_enabled: bool
    voicemail_greeting: Optional[str]
    voicemail_email: Optional[str]
    sms_confirmation_enabled: bool
    sms_confirmation_template: Optional[str]
    email_confirmation_enabled: bool = False
    email_confirmation_template: Optional[str] = None
    sms_callback_template: Optional[str] = None
    transfer_enabled: bool = False
    transfer_number: Optional[str] = None
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


class AvailableNumber(BaseModel):
    """Schema for an available Twilio phone number."""
    phone_number: str
    friendly_name: str
    locality: Optional[str] = None  # City/region
    region: Optional[str] = None
    capabilities: Dict[str, bool] = {}  # voice, sms, mms
    monthly_cost: str = "€1.00"  # Approximate cost


class AvailableNumbersResponse(BaseModel):
    """Schema for listing available numbers."""
    numbers: list[AvailableNumber]
    country: str = "NL"


class PurchaseNumberRequest(BaseModel):
    """Schema for purchasing a phone number."""
    phone_number: str = Field(..., description="The phone number to purchase (E.164 format)")
    friendly_name: Optional[str] = Field(None, max_length=100)
    ai_worker_id: Optional[UUID] = None  # Optionally link to an AI worker immediately


class PurchaseNumberResponse(BaseModel):
    """Schema for purchase response."""
    success: bool
    phone_number: PhoneNumberResponse
    twilio_sid: str
    message: str
