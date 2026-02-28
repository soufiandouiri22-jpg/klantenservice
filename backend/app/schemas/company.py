"""
klantenservice.ai - Company Schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

from app.models.company import SubscriptionPlan


class CompanyBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    kvk_number: Optional[str] = None
    btw_number: Optional[str] = None


class CompanyCreate(CompanyBase):
    """Schema for creating a new company."""
    pass


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    kvk_number: Optional[str] = None
    btw_number: Optional[str] = None
    disclosure_message: Optional[str] = None
    timezone: Optional[str] = None
    data_retention_days: Optional[int] = Field(None, ge=30, le=365)
    call_recording_enabled: Optional[bool] = None
    call_recording_consent_required: Optional[bool] = None


class CompanyResponse(CompanyBase):
    """Schema for company response."""
    id: UUID
    slug: str
    subscription_plan: SubscriptionPlan
    subscription_status: str
    max_ai_workers: int
    disclosure_message: str
    timezone: str
    data_retention_days: int
    call_recording_enabled: bool
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CompanyStats(BaseModel):
    """Company dashboard statistics."""
    active_ai_workers: int
    total_ai_workers: int
    active_calls: int
    calls_today: int
    calls_this_month: int
    calls_answered_month: int
    calls_missed_month: int
    avg_duration_seconds: int
    appointments_today: int
    appointments_this_week: int
    appointments_made_by_ai_month: int
    unresolved_notes: int
    sentiment_positive: int
    sentiment_neutral: int
    sentiment_negative: int
