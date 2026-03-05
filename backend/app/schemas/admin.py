"""
klantenservice.ai - Admin API Schemas

Pydantic schemas for the admin dashboard endpoints.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


# ==================== Global Config Schemas ====================

class GlobalConfigBase(BaseModel):
    key: str
    value: Any
    category: str
    description: Optional[str] = None


class GlobalConfigCreate(GlobalConfigBase):
    pass


class GlobalConfigUpdate(BaseModel):
    value: Optional[Any] = None
    description: Optional[str] = None


class GlobalConfigResponse(GlobalConfigBase):
    id: UUID
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GlobalConfigListResponse(BaseModel):
    configs: List[GlobalConfigResponse]
    total: int


class GlobalConfigByCategoryResponse(BaseModel):
    policies: List[GlobalConfigResponse]
    model: List[GlobalConfigResponse]
    voice: List[GlobalConfigResponse]
    thresholds: List[GlobalConfigResponse]


# ==================== Metrics Schemas ====================

class MetricsOverview(BaseModel):
    # Active calls
    active_calls: int = 0
    calls_today: int = 0
    calls_this_month: int = 0
    
    # Average call duration (seconds) for today
    avg_duration_today: int = 0
    
    # Errors
    errors_today: int = 0
    error_rate_today: float = 0.0  # percentage
    
    # Unknown questions
    unknown_questions_today: int = 0
    unknown_rate_today: float = 0.0


class LatencyMetrics(BaseModel):
    # p50, p95, p99 latencies in ms
    stt_p50: int = 0
    stt_p95: int = 0
    stt_p99: int = 0
    
    orchestrator_p50: int = 0
    orchestrator_p95: int = 0
    orchestrator_p99: int = 0
    
    pod_p50: int = 0
    pod_p95: int = 0
    pod_p99: int = 0
    
    total_p50: int = 0
    total_p95: int = 0
    total_p99: int = 0
    
    # Sample count for these stats
    sample_count: int = 0
    period_hours: int = 24


class CostMetrics(BaseModel):
    # ElevenLabs
    elevenlabs_characters_today: int = 0
    elevenlabs_characters_month: int = 0
    elevenlabs_cost_today_cents: int = 0
    elevenlabs_cost_month_cents: int = 0

    # Twilio (totals)
    twilio_cost_today_cents: int = 0
    twilio_cost_month_cents: int = 0
    twilio_calls_today: int = 0
    twilio_calls_month: int = 0
    twilio_minutes_today: float = 0
    twilio_minutes_month: float = 0

    # Twilio breakdown (selected range)
    twilio_calls_cost_range_cents: int = 0
    twilio_numbers_cost_range_cents: int = 0
    twilio_numbers_count_range: int = 0
    twilio_recordings_cost_range_cents: int = 0
    twilio_media_streams_cost_range_cents: int = 0
    twilio_tts_cost_range_cents: int = 0

    # Twilio breakdown (monthly)
    twilio_calls_cost_month_cents: int = 0
    twilio_numbers_cost_month_cents: int = 0
    twilio_numbers_count_month: int = 0
    twilio_recordings_cost_month_cents: int = 0
    twilio_media_streams_cost_month_cents: int = 0
    twilio_tts_cost_month_cents: int = 0

    # Totals
    total_cost_today_cents: int = 0
    total_cost_month_cents: int = 0


class BusinessMetrics(BaseModel):
    # Customer counts
    total_customers: int = 0
    active_customers: int = 0  # trialing or active
    trialing_customers: int = 0
    pending_customers: int = 0  # registered but not subscribed
    
    # Customers by plan
    starter_customers: int = 0
    business_customers: int = 0
    enterprise_customers: int = 0
    
    # Revenue metrics (in cents)
    mrr_cents: int = 0  # Monthly Recurring Revenue
    arr_cents: int = 0  # Annual Recurring Revenue (MRR * 12)
    
    # Growth metrics
    new_customers_this_month: int = 0
    churned_this_month: int = 0
    
    # Conversion
    trial_to_paid_rate: float = 0.0  # percentage


# ==================== Customer Schemas ====================

class CustomerStats(BaseModel):
    calls_today: int = 0
    calls_this_month: int = 0
    errors_today: int = 0
    error_rate: float = 0.0
    unknown_questions_today: int = 0
    unknown_rate: float = 0.0
    spend_today_cents: int = 0
    spend_month_cents: int = 0


class CustomerListItem(BaseModel):
    id: UUID
    name: str
    slug: str
    email: str
    subscription_plan: str
    subscription_status: str
    billing_interval: str = "monthly"
    is_active: bool
    is_kill_switched: bool
    created_at: datetime
    stats: CustomerStats

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    customers: List[CustomerListItem]
    total: int


class AdminOverrides(BaseModel):
    """Hidden admin overrides for a customer."""
    force_language: Optional[str] = None  # e.g., "nl-NL"
    force_u_form: Optional[bool] = None  # Force formal address
    orchestrator_model_override: Optional[str] = None  # e.g., "gpt-4o"
    rag_threshold_override: Optional[float] = None
    audio_segment_ms_override: Optional[int] = None
    max_calls_per_minute: Optional[int] = None
    disable_auto_booking: Optional[bool] = None  # Only suggestions, no bookings


class FeatureFlags(BaseModel):
    """Feature flags for a customer."""
    enable_voice_cloning: bool = False
    enable_advanced_analytics: bool = False
    enable_api_access: bool = False
    enable_custom_prompts: bool = False


class CustomerDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    email: str
    phone: Optional[str]
    
    # Subscription
    subscription_plan: str
    subscription_status: str
    billing_interval: str = "monthly"
    stripe_customer_id: Optional[str]
    trial_used: bool = False
    
    # Status
    is_active: bool
    is_verified: bool
    is_kill_switched: bool
    
    # Admin controls
    feature_flags: Dict[str, Any]
    admin_overrides: Dict[str, Any]
    
    # Stats
    stats: CustomerStats
    
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerOverridesUpdate(BaseModel):
    admin_overrides: Optional[Dict[str, Any]] = None
    feature_flags: Optional[Dict[str, Any]] = None


class SubscriptionUpdate(BaseModel):
    subscription_plan: Optional[str] = None  # starter, business, enterprise
    subscription_status: Optional[str] = None  # active, trialing, pending, canceled
    trial_used: Optional[bool] = None


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None


# ==================== Call Trace/Logs Schemas ====================

class ToolCallLog(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    latency_ms: Optional[int] = None


class ContextLogResponse(BaseModel):
    id: UUID
    turn_id: int
    user_transcript: Optional[str]
    assistant_transcript: Optional[str]
    detected_intent: Optional[str]
    intent_confidence: Optional[int]
    tool_calls: List[ToolCallLog]
    facts: Optional[str]
    instructions: Optional[str]
    model_used: Optional[str]
    was_escalated: int
    created_at: datetime

    class Config:
        from_attributes = True


class LatencyLogResponse(BaseModel):
    id: UUID
    turn_id: int
    stt_latency_ms: Optional[int]
    orchestrator_latency_ms: Optional[int]
    pod_latency_ms: Optional[int]
    tts_latency_ms: Optional[int]
    total_latency_ms: Optional[int]
    queue_wait_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TranscriptEntry(BaseModel):
    speaker: str  # "caller" or "ai"
    message: str
    timestamp: datetime
    confidence: Optional[float] = None


class CallTraceResponse(BaseModel):
    """Complete call trace for debugging."""
    call_id: UUID
    company_id: UUID
    company_name: str
    ai_worker_name: Optional[str]
    
    # Call info
    caller_number: str
    called_number: str
    status: str
    outcome: Optional[str]
    
    # Timing
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: int
    
    # Transcripts (PII masked)
    transcripts: List[TranscriptEntry]
    
    # Context logs per turn
    context_logs: List[ContextLogResponse]
    
    # Latency logs per turn
    latency_logs: List[LatencyLogResponse]
    
    # Summary
    total_turns: int
    total_tool_calls: int
    error_message: Optional[str]

    class Config:
        from_attributes = True


class RecentCallsResponse(BaseModel):
    """List of recent calls for the logs tab."""
    calls: List[Dict[str, Any]]  # Simplified call info
    total: int
