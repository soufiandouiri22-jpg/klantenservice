"""
klantenservice.ai - Evaluation API Schemas
"""
from datetime import datetime
from typing import List, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field


class EvaluationIssue(BaseModel):
    type: str
    description: str
    severity: str = "medium"


class EvaluationResponse(BaseModel):
    id: UUID
    call_log_id: UUID
    company_id: UUID
    quality_score: int
    hallucination_detected: bool
    wrong_tool_detected: bool
    customer_helped: bool
    needs_review: bool
    latency_ms: Optional[int] = None
    summary: Optional[str] = None
    issues: List[Any] = []
    tool_usage: List[Any] = []
    langsmith_run_id: Optional[str] = None
    evaluator_model: Optional[str] = None
    evaluated_at: datetime
    created_at: datetime

    # Joined from CallLog
    caller_number: Optional[str] = None
    called_number: Optional[str] = None
    call_started_at: Optional[datetime] = None
    call_duration_seconds: Optional[int] = None
    ai_worker_name: Optional[str] = None
    company_name: Optional[str] = None

    class Config:
        from_attributes = True


class TranscriptEntryResponse(BaseModel):
    speaker: str
    message: str
    timestamp: Optional[datetime] = None


class EvaluationDetailResponse(EvaluationResponse):
    transcript: List[TranscriptEntryResponse] = []


class EvaluationListResponse(BaseModel):
    items: List[EvaluationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EvaluationSummaryResponse(BaseModel):
    total_evaluated: int = 0
    average_score: Optional[float] = None
    hallucination_rate: Optional[float] = None
    wrong_tool_rate: Optional[float] = None
    customer_helped_rate: Optional[float] = None
    needs_review_count: int = 0


class EvaluationSyncRequest(BaseModel):
    company_id: Optional[UUID] = None
    limit: int = Field(default=50, ge=1, le=500)
