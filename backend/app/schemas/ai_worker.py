"""
klantenservice.ai - AI Worker Schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.ai_worker import AIWorkerStatus, AddressForm


class BehaviorSettings(BaseModel):
    """Behavior settings for AI worker."""
    apologize_on_complaints: bool = True
    always_offer_alternatives: bool = True
    never_guess: bool = True
    confirm_appointments: bool = True
    summarize_at_end: bool = True


class AIWorkerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role_title: str = Field(default="Klantenservice medewerker", max_length=100)
    tone_of_voice: Optional[str] = None


class AIWorkerCreate(AIWorkerBase):
    """Schema for creating a new AI worker."""
    address_form: AddressForm = AddressForm.FORMAL
    behavior_settings: Optional[BehaviorSettings] = None
    can_make_appointments: bool = True
    can_cancel_appointments: bool = False
    can_view_prices: bool = True
    can_leave_notes: bool = True


class AIWorkerUpdate(BaseModel):
    """Schema for updating an AI worker."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role_title: Optional[str] = Field(None, max_length=100)
    tone_of_voice: Optional[str] = None
    address_form: Optional[AddressForm] = None
    behavior_settings: Optional[BehaviorSettings] = None
    can_make_appointments: Optional[bool] = None
    can_cancel_appointments: Optional[bool] = None
    can_view_prices: Optional[bool] = None
    can_leave_notes: Optional[bool] = None
    is_active: Optional[bool] = None


class AIWorkerResponse(AIWorkerBase):
    """Schema for AI worker response."""
    id: UUID
    company_id: UUID
    address_form: AddressForm
    behavior_settings: Dict[str, Any]
    can_make_appointments: bool
    can_cancel_appointments: bool
    can_view_prices: bool
    can_leave_notes: bool
    status: AIWorkerStatus
    is_active: bool
    total_calls_handled: int
    total_appointments_made: int
    average_call_duration_seconds: int
    last_call_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AIWorkerStats(BaseModel):
    """Statistics for an AI worker."""
    calls_today: int
    calls_this_week: int
    calls_this_month: int
    appointments_made_today: int
    average_call_duration_seconds: int
    busiest_hour: Optional[int]
    sentiment_breakdown: Dict[str, int]  # {"positive": 10, "neutral": 5, "negative": 2}
