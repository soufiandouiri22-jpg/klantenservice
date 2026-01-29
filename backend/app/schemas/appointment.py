"""
klantenservice.ai - Appointment Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID

from app.models.appointment import AppointmentStatus


class AppointmentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    appointment_type: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_phone: Optional[str] = None
    customer_email: Optional[EmailStr] = None


class AppointmentCreate(AppointmentBase):
    """Schema for creating an appointment."""
    calendar_integration_id: UUID


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    customer_name: Optional[str] = Field(None, min_length=1, max_length=255)
    customer_phone: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    status: Optional[AppointmentStatus] = None


class AppointmentResponse(AppointmentBase):
    """Schema for appointment response."""
    id: UUID
    company_id: UUID
    calendar_integration_id: Optional[UUID]
    call_log_id: Optional[UUID]
    external_event_id: Optional[str]
    duration_minutes: int
    status: AppointmentStatus
    reminder_sent: bool
    cancelled_at: Optional[datetime]
    cancelled_by: Optional[str]
    cancellation_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    """Paginated list of appointments."""
    items: List[AppointmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AppointmentCancelRequest(BaseModel):
    """Request to cancel an appointment."""
    reason: Optional[str] = None


class AppointmentRescheduleRequest(BaseModel):
    """Request to reschedule an appointment."""
    new_starts_at: datetime
    new_ends_at: datetime
    reason: Optional[str] = None


class AppointmentFilterParams(BaseModel):
    """Filter parameters for appointments."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[AppointmentStatus] = None
    calendar_integration_id: Optional[UUID] = None
    search: Optional[str] = None  # Search in customer name, title
