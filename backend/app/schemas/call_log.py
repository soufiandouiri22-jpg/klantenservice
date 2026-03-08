"""
klantenservice.ai - Call Log Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from uuid import UUID

from app.models.call_log import CallStatus, CallOutcome


class CallLogBase(BaseModel):
    caller_number: str
    called_number: str


class CallLogResponse(CallLogBase):
    """Schema for call log response."""
    id: UUID
    company_id: UUID
    ai_worker_id: Optional[UUID]
    phone_number_id: Optional[UUID]
    twilio_call_sid: Optional[str]
    status: CallStatus
    outcome: Optional[CallOutcome]
    started_at: datetime
    answered_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: int
    queue_wait_seconds: int
    recording_url: Optional[str]
    elevenlabs_conversation_id: Optional[str] = None
    recording_consent_given: bool
    sentiment: Optional[str]
    topics: List[str]
    summary: Optional[str]
    customer_name: Optional[str]
    customer_email: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class CallLogListResponse(BaseModel):
    """Paginated list of call logs."""
    items: List[CallLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CallTranscriptResponse(BaseModel):
    """Schema for call transcript response."""
    id: UUID
    call_log_id: UUID
    speaker: str
    message: str
    timestamp: datetime
    confidence: Optional[float]
    tool_calls: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


class CallDetailResponse(CallLogResponse):
    """Detailed call response with transcripts."""
    transcripts: List[CallTranscriptResponse]
    ai_worker_name: Optional[str]
    phone_number_friendly_name: Optional[str]


class CallStatsResponse(BaseModel):
    """Call statistics."""
    total_calls: int
    completed_calls: int
    missed_calls: int
    voicemails: int
    average_duration_seconds: int
    average_wait_time_seconds: int
    appointments_made: int
    notes_created: int
    sentiment_breakdown: Dict[str, int]
    calls_by_hour: Dict[int, int]
    calls_by_day: Dict[str, int]


class CallFilterParams(BaseModel):
    """Filter parameters for call logs."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[CallStatus] = None
    outcome: Optional[CallOutcome] = None
    ai_worker_id: Optional[UUID] = None
    phone_number_id: Optional[UUID] = None
    sentiment: Optional[str] = None
    search: Optional[str] = None  # Search in caller number, customer name
