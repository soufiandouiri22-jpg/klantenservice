"""
klantenservice.ai - Admin API Endpoints

Endpoints for platform administrators to manage system-wide settings.
Includes: System Prompts, Global Config, Metrics, Customers, Logs
"""
import asyncio
from datetime import date, datetime, timedelta
from typing import List, Optional, Any
from uuid import UUID
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, and_, case, or_, literal

from app.api.deps import get_db, get_current_user
from app.core.config import get_settings, settings
from app.models.user import User
from app.models.company import Company, BillingInterval
from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.models.call_log import CallLog, CallStatus, CallTranscript
from app.models.training import ExampleAnswer
from app.models.system_prompt import SystemPrompt, DEFAULT_SYSTEM_PROMPTS
from app.models.global_config import GlobalConfig, DEFAULT_CONFIGS
from app.models.usage_log import UsageLog
from app.models.notification import Notification
from app.models.latency_log import LatencyLog
from app.models.context_log import ContextLog
from app.models.voice_session import VoiceSession, PolicyDecisionLog
from app.services.call_cleanup import cleanup_stale_active_calls
from app.schemas.system_prompt import (
    SystemPromptCreate,
    SystemPromptUpdate,
    SystemPromptResponse,
    SystemPromptListResponse,
    SystemPromptPreview,
)
from app.schemas.admin import (
    GlobalConfigResponse,
    GlobalConfigListResponse,
    GlobalConfigByCategoryResponse,
    GlobalConfigUpdate,
    MetricsOverview,
    LatencyMetrics,
    CostMetrics,
    BusinessMetrics,
    CustomerListItem,
    CustomerListResponse,
    CustomerDetail,
    CustomerStats,
    CustomerOverridesUpdate,
    SubscriptionUpdate,
    KillSwitchRequest,
    CallTraceResponse,
    ContextLogResponse,
    LatencyLogResponse,
    TranscriptEntry,
    RecentCallsResponse,
)
from app.services.pii_masker import mask_transcript
from app.models.billing_run import BillingRun, BillingRunStatus
from app.models.call_evaluation import CallEvaluation
from app.schemas.evaluation import (
    EvaluationResponse,
    EvaluationDetailResponse,
    EvaluationListResponse,
    EvaluationSummaryResponse,
    EvaluationSyncRequest,
    TranscriptEntryResponse,
)

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter()


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the current user to be a superadmin.
    """
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alleen platform administrators hebben toegang tot deze functie"
        )
    return current_user


@router.get("/prompts", response_model=SystemPromptListResponse)
async def get_system_prompts(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get all system prompts, optionally filtered by category.
    """
    query = db.query(SystemPrompt)
    
    if category:
        query = query.filter(SystemPrompt.category == category)
    
    prompts = query.order_by(SystemPrompt.display_order, SystemPrompt.created_at).all()
    
    # Add updated_by_name to each prompt
    prompt_responses = []
    for prompt in prompts:
        response = SystemPromptResponse(
            id=prompt.id,
            key=prompt.key,
            name=prompt.name,
            description=prompt.description,
            category=prompt.category,
            content=prompt.content,
            is_active=prompt.is_active,
            display_order=prompt.display_order,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
            updated_by_id=prompt.updated_by_id,
            updated_by_name=prompt.updated_by.full_name if prompt.updated_by else None,
        )
        prompt_responses.append(response)
    
    return SystemPromptListResponse(
        prompts=prompt_responses,
        total=len(prompt_responses)
    )


@router.get("/prompts/preview", response_model=SystemPromptPreview)
async def preview_combined_prompt(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Preview the combined system prompt that will be sent to the AI.
    """
    prompts = db.query(SystemPrompt).filter(
        SystemPrompt.is_active == True
    ).order_by(SystemPrompt.display_order).all()
    
    # Combine all active prompts
    combined_parts = []
    categories = set()
    
    for prompt in prompts:
        combined_parts.append(f"## {prompt.name}\n{prompt.content}")
        categories.add(prompt.category)
    
    combined_prompt = "\n\n".join(combined_parts)
    
    return SystemPromptPreview(
        combined_prompt=combined_prompt,
        active_prompts=len(prompts),
        categories=sorted(list(categories))
    )


@router.get("/prompts/{prompt_id}", response_model=SystemPromptResponse)
async def get_system_prompt(
    prompt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get a specific system prompt by ID.
    """
    prompt = db.query(SystemPrompt).filter(SystemPrompt.id == prompt_id).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt niet gevonden"
        )
    
    return SystemPromptResponse(
        id=prompt.id,
        key=prompt.key,
        name=prompt.name,
        description=prompt.description,
        category=prompt.category,
        content=prompt.content,
        is_active=prompt.is_active,
        display_order=prompt.display_order,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        updated_by_id=prompt.updated_by_id,
        updated_by_name=prompt.updated_by.full_name if prompt.updated_by else None,
    )


@router.post("/prompts", response_model=SystemPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_system_prompt(
    data: SystemPromptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Create a new system prompt.
    """
    # Check if key already exists
    existing = db.query(SystemPrompt).filter(SystemPrompt.key == data.key).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Een prompt met key '{data.key}' bestaat al"
        )
    
    prompt = SystemPrompt(
        key=data.key,
        name=data.name,
        description=data.description,
        category=data.category,
        content=data.content,
        is_active=data.is_active,
        display_order=data.display_order,
        updated_by_id=current_user.id,
    )
    
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    
    return SystemPromptResponse(
        id=prompt.id,
        key=prompt.key,
        name=prompt.name,
        description=prompt.description,
        category=prompt.category,
        content=prompt.content,
        is_active=prompt.is_active,
        display_order=prompt.display_order,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        updated_by_id=prompt.updated_by_id,
        updated_by_name=current_user.full_name,
    )


@router.put("/prompts/{prompt_id}", response_model=SystemPromptResponse)
async def update_system_prompt(
    prompt_id: UUID,
    data: SystemPromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Update an existing system prompt.
    """
    prompt = db.query(SystemPrompt).filter(SystemPrompt.id == prompt_id).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt niet gevonden"
        )
    
    # Check if new key conflicts with existing
    if data.key and data.key != prompt.key:
        existing = db.query(SystemPrompt).filter(SystemPrompt.key == data.key).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Een prompt met key '{data.key}' bestaat al"
            )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prompt, field, value)
    
    prompt.updated_by_id = current_user.id
    
    db.commit()
    db.refresh(prompt)
    
    return SystemPromptResponse(
        id=prompt.id,
        key=prompt.key,
        name=prompt.name,
        description=prompt.description,
        category=prompt.category,
        content=prompt.content,
        is_active=prompt.is_active,
        display_order=prompt.display_order,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        updated_by_id=prompt.updated_by_id,
        updated_by_name=current_user.full_name,
    )


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_prompt(
    prompt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Delete a system prompt.
    """
    prompt = db.query(SystemPrompt).filter(SystemPrompt.id == prompt_id).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt niet gevonden"
        )
    
    db.delete(prompt)
    db.commit()


@router.post("/prompts/seed", response_model=SystemPromptListResponse)
async def seed_default_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Seed the database with default system prompts.
    Only creates prompts that don't already exist (by key).
    """
    created = []
    
    for prompt_data in DEFAULT_SYSTEM_PROMPTS:
        existing = db.query(SystemPrompt).filter(
            SystemPrompt.key == prompt_data["key"]
        ).first()
        
        if not existing:
            prompt = SystemPrompt(
                key=prompt_data["key"],
                name=prompt_data["name"],
                description=prompt_data.get("description"),
                category=prompt_data["category"],
                content=prompt_data["content"],
                is_active=prompt_data.get("is_active", True),
                display_order=prompt_data.get("display_order", 0),
                updated_by_id=current_user.id,
            )
            db.add(prompt)
            created.append(prompt)
    
    db.commit()
    
    # Refresh and build response
    prompt_responses = []
    for prompt in created:
        db.refresh(prompt)
        prompt_responses.append(SystemPromptResponse(
            id=prompt.id,
            key=prompt.key,
            name=prompt.name,
            description=prompt.description,
            category=prompt.category,
            content=prompt.content,
            is_active=prompt.is_active,
            display_order=prompt.display_order,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
            updated_by_id=prompt.updated_by_id,
            updated_by_name=current_user.full_name,
        ))
    
    return SystemPromptListResponse(
        prompts=prompt_responses,
        total=len(prompt_responses)
    )


@router.get("/categories", response_model=List[dict])
async def get_prompt_categories(
    current_user: User = Depends(require_superadmin),
):
    """
    Get list of available prompt categories.
    """
    return [
        {"key": "privacy", "name": "Privacy", "icon": "🔒"},
        {"key": "compliance", "name": "Compliance", "icon": "📋"},
        {"key": "custom", "name": "Overig", "icon": "📝"},
    ]


# ==================== METRICS ENDPOINTS ====================

@router.get("/metrics/overview", response_model=MetricsOverview)
async def get_metrics_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get overview metrics for the admin dashboard.
    """
    cleanup_stale_active_calls(db)

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Active calls
    active_calls = db.query(func.count(CallLog.id)).filter(
        CallLog.status == CallStatus.IN_PROGRESS
    ).scalar() or 0
    
    # Calls today
    calls_today = db.query(func.count(CallLog.id)).filter(
        CallLog.created_at >= today_start
    ).scalar() or 0
    
    # Calls this month
    calls_this_month = db.query(func.count(CallLog.id)).filter(
        CallLog.created_at >= month_start
    ).scalar() or 0
    
    # Errors today
    errors_today = db.query(func.count(CallLog.id)).filter(
        and_(
            CallLog.created_at >= today_start,
            CallLog.error_message.isnot(None)
        )
    ).scalar() or 0
    
    # Error rate
    error_rate = (errors_today / calls_today * 100) if calls_today > 0 else 0
    
    # Unknown questions today
    unknown_today = db.query(func.count(ExampleAnswer.id)).filter(
        and_(
            ExampleAnswer.source == "detected",
            ExampleAnswer.created_at >= today_start
        )
    ).scalar() or 0
    
    unknown_rate = (unknown_today / calls_today * 100) if calls_today > 0 else 0
    
    # Average call duration today
    avg_duration = db.query(func.avg(CallLog.duration_seconds)).filter(
        and_(
            CallLog.created_at >= today_start,
            CallLog.duration_seconds.isnot(None),
            CallLog.duration_seconds > 0,
        )
    ).scalar() or 0
    
    return MetricsOverview(
        active_calls=active_calls,
        calls_today=calls_today,
        calls_this_month=calls_this_month,
        avg_duration_today=int(avg_duration),
        errors_today=errors_today,
        error_rate_today=round(error_rate, 2),
        unknown_questions_today=unknown_today,
        unknown_rate_today=round(unknown_rate, 2),
    )


@router.post("/cleanup-stale-calls")
async def cleanup_stale_calls(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Manually clean up all CallLogs stuck in IN_PROGRESS/RINGING.
    Use max_age_minutes=0 to clean all, or a positive number for the default 30-min threshold.
    """
    cleaned = cleanup_stale_active_calls(db, max_age_minutes=0)
    return {"ok": True, "cleaned": cleaned}


@router.get("/metrics/latency", response_model=LatencyMetrics)
async def get_latency_metrics(
    hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get p50/p95/p99 latency metrics for the last N hours.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    
    logs = db.query(LatencyLog).filter(
        LatencyLog.created_at >= since
    ).all()
    
    if not logs:
        return LatencyMetrics(sample_count=0, period_hours=hours)
    
    # Calculate percentiles
    def percentile(values: list, p: float) -> int:
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    stt_values = [l.stt_latency_ms for l in logs if l.stt_latency_ms]
    orch_values = [l.orchestrator_latency_ms for l in logs if l.orchestrator_latency_ms]
    pod_values = [l.pod_latency_ms for l in logs if l.pod_latency_ms]
    total_values = [l.total_latency_ms for l in logs if l.total_latency_ms]
    
    return LatencyMetrics(
        stt_p50=percentile(stt_values, 50),
        stt_p95=percentile(stt_values, 95),
        stt_p99=percentile(stt_values, 99),
        orchestrator_p50=percentile(orch_values, 50),
        orchestrator_p95=percentile(orch_values, 95),
        orchestrator_p99=percentile(orch_values, 99),
        pod_p50=percentile(pod_values, 50),
        pod_p95=percentile(pod_values, 95),
        pod_p99=percentile(pod_values, 99),
        total_p50=percentile(total_values, 50),
        total_p95=percentile(total_values, 95),
        total_p99=percentile(total_values, 99),
        sample_count=len(logs),
        period_hours=hours,
    )


async def _fetch_elevenlabs_usage(start_unix_ms: int, end_unix_ms: int) -> dict:
    """Fetch character usage from ElevenLabs API."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/usage/character-stats",
                params={
                    "start_unix": start_unix_ms,
                    "end_unix": end_unix_ms,
                },
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            )
            if resp.status_code == 200:
                data = resp.json()
                all_chars = sum(
                    sum(v) if isinstance(v, list) else 0
                    for v in data.get("usage", {}).values()
                )
                return {"characters": all_chars}
    except Exception as e:
        logger.warning(f"[COSTS] ElevenLabs usage fetch failed: {e}")
    return {"characters": 0}


async def _fetch_elevenlabs_subscription() -> dict:
    """Fetch subscription and actual costs from ElevenLabs API.
    Returns actual amount_due from next_invoice + open_invoices (real billing data).
    Fallback: empty dict if API fails.
    """
    if not settings.ELEVENLABS_API_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/user/subscription",
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            )
            if resp.status_code != 200:
                logger.warning(f"[COSTS] ElevenLabs subscription API returned {resp.status_code}")
                return {}
            data = resp.json()
            # Sum: next invoice + open invoices (actual amount owed to ElevenLabs)
            total_cents = 0
            next_inv = data.get("next_invoice") or {}
            total_cents += int(next_inv.get("amount_due_cents", 0) or 0)
            for inv in data.get("open_invoices") or []:
                total_cents += int(inv.get("amount_due_cents", 0) or 0)
            return {
                "cost_cents": total_cents,
                "tier": data.get("tier", ""),
                "character_count": int(data.get("character_count", 0) or 0),
                "character_limit": int(data.get("character_limit", 0) or 0),
                "currency": data.get("currency", "usd"),
            }
    except Exception as e:
        logger.warning(f"[COSTS] ElevenLabs subscription fetch failed: {e}")
    return {}


async def _fetch_twilio_usage(start_date: str, end_date: str) -> dict:
    """Fetch usage records from Twilio API for a date range with breakdown."""
    result = {
        "cost_cents": 0,
        "calls_cost_cents": 0,
        "calls_inbound": 0,
        "calls_inbound_minutes": 0.0,
        "numbers_cost_cents": 0,
        "numbers_count": 0,
        "recordings_cost_cents": 0,
        "media_streams_cost_cents": 0,
        "tts_cost_cents": 0,
    }
    base = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Usage/Records.json"
    auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Inbound calls only (no double counting)
            resp_calls = await client.get(base, params={
                "StartDate": start_date, "EndDate": end_date,
                "Category": "calls-inbound",
            }, auth=auth)
            if resp_calls.status_code == 200:
                for r in resp_calls.json().get("usage_records", []):
                    price = abs(float(r.get("price", "0") or "0"))
                    result["calls_cost_cents"] += int(price * 100)
                    result["calls_inbound"] += int(r.get("count", "0") or "0")
                    result["calls_inbound_minutes"] += float(r.get("usage", "0") or "0")

            # Phone numbers
            resp_nums = await client.get(base, params={
                "StartDate": start_date, "EndDate": end_date,
                "Category": "phonenumbers",
            }, auth=auth)
            if resp_nums.status_code == 200:
                for r in resp_nums.json().get("usage_records", []):
                    price = abs(float(r.get("price", "0") or "0"))
                    result["numbers_cost_cents"] += int(price * 100)
                    result["numbers_count"] += int(r.get("count", "0") or "0")

            # Recordings
            resp_rec = await client.get(base, params={
                "StartDate": start_date, "EndDate": end_date,
                "Category": "recordings",
            }, auth=auth)
            if resp_rec.status_code == 200:
                for r in resp_rec.json().get("usage_records", []):
                    price = abs(float(r.get("price", "0") or "0"))
                    result["recordings_cost_cents"] += int(price * 100)

            # Media Streams
            resp_ms = await client.get(base, params={
                "StartDate": start_date, "EndDate": end_date,
                "Category": "media-stream-minutes",
            }, auth=auth)
            if resp_ms.status_code == 200:
                for r in resp_ms.json().get("usage_records", []):
                    price = abs(float(r.get("price", "0") or "0"))
                    result["media_streams_cost_cents"] += int(price * 100)

            # TTS (Amazon Polly)
            resp_tts = await client.get(base, params={
                "StartDate": start_date, "EndDate": end_date,
                "Category": "tts-amazon-polly",
            }, auth=auth)
            if resp_tts.status_code == 200:
                for r in resp_tts.json().get("usage_records", []):
                    price = abs(float(r.get("price", "0") or "0"))
                    result["tts_cost_cents"] += int(price * 100)

            result["cost_cents"] = (
                result["calls_cost_cents"]
                + result["numbers_cost_cents"]
                + result["recordings_cost_cents"]
                + result["media_streams_cost_cents"]
                + result["tts_cost_cents"]
            )
    except Exception as e:
        logger.warning(f"[COSTS] Twilio usage fetch failed: {e}")
    return result


# Fallback: estimated cost per 1k chars when subscription API unavailable (Starter tier)
ELEVENLABS_COST_PER_1K_CHARS_CENTS_FALLBACK = 30


@router.get("/metrics/costs", response_model=CostMetrics)
async def get_cost_metrics(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get real API cost metrics from ElevenLabs and Twilio.
    
    Accepts optional start_date / end_date (YYYY-MM-DD).
    Defaults: today for the "today" column, first-of-month for the "month" column.
    When both are supplied the "today" fields reflect the custom range and
    "month" fields are unchanged (still calendar month).
    """

    now = datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")
    month_start_str = now.replace(day=1).strftime("%Y-%m-%d")

    if start_date and end_date:
        range_start_str = start_date
        range_end_str = end_date
        range_start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        range_end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        range_start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        range_end_dt = now
        range_start_str = today_str
        range_end_str = today_str

    range_start_ms = int(range_start_dt.timestamp() * 1000)
    range_end_ms = int(range_end_dt.timestamp() * 1000)
    month_start_ms = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    now_ms = int(now.timestamp() * 1000)

    el_range, el_month, tw_range, tw_month, el_sub = await asyncio.gather(
        _fetch_elevenlabs_usage(range_start_ms, range_end_ms),
        _fetch_elevenlabs_usage(month_start_ms, now_ms),
        _fetch_twilio_usage(range_start_str, range_end_str),
        _fetch_twilio_usage(month_start_str, today_str),
        _fetch_elevenlabs_subscription(),
    )

    # ElevenLabs cost: use actual billing from subscription API for current month only
    # (subscription API gives current billing period; for past months we estimate from usage)
    is_current_month = (
        range_start_dt.month == now.month
        and range_start_dt.year == now.year
    )
    if is_current_month and el_sub.get("cost_cents", 0) > 0:
        el_cost_range = el_sub["cost_cents"]
        el_cost_month = el_sub["cost_cents"]
        el_cost_source = "api"
        el_tier = el_sub.get("tier", "")
        el_currency = el_sub.get("currency", "usd")
    else:
        el_cost_range = int(el_range["characters"] / 1000 * ELEVENLABS_COST_PER_1K_CHARS_CENTS_FALLBACK)
        el_cost_month = int(el_month["characters"] / 1000 * ELEVENLABS_COST_PER_1K_CHARS_CENTS_FALLBACK)
        el_cost_source = "estimated"
        el_tier = el_sub.get("tier", "") if el_sub else ""
        el_currency = el_sub.get("currency", "usd") if el_sub else "usd"

    total_range = el_cost_range + tw_range["cost_cents"]
    total_month = el_cost_month + tw_month["cost_cents"]

    return CostMetrics(
        elevenlabs_characters_today=el_range["characters"],
        elevenlabs_characters_month=el_month["characters"],
        elevenlabs_cost_today_cents=el_cost_range,
        elevenlabs_cost_month_cents=el_cost_month,
        elevenlabs_cost_source=el_cost_source,
        elevenlabs_tier=el_tier,
        elevenlabs_currency=el_currency,
        twilio_cost_today_cents=tw_range["cost_cents"],
        twilio_cost_month_cents=tw_month["cost_cents"],
        twilio_calls_today=tw_range["calls_inbound"],
        twilio_calls_month=tw_month["calls_inbound"],
        twilio_minutes_today=round(tw_range["calls_inbound_minutes"], 1),
        twilio_minutes_month=round(tw_month["calls_inbound_minutes"], 1),
        twilio_calls_cost_range_cents=tw_range["calls_cost_cents"],
        twilio_numbers_cost_range_cents=tw_range["numbers_cost_cents"],
        twilio_numbers_count_range=tw_range["numbers_count"],
        twilio_recordings_cost_range_cents=tw_range["recordings_cost_cents"],
        twilio_media_streams_cost_range_cents=tw_range["media_streams_cost_cents"],
        twilio_tts_cost_range_cents=tw_range["tts_cost_cents"],
        twilio_calls_cost_month_cents=tw_month["calls_cost_cents"],
        twilio_numbers_cost_month_cents=tw_month["numbers_cost_cents"],
        twilio_numbers_count_month=tw_month["numbers_count"],
        twilio_recordings_cost_month_cents=tw_month["recordings_cost_cents"],
        twilio_media_streams_cost_month_cents=tw_month["media_streams_cost_cents"],
        twilio_tts_cost_month_cents=tw_month["tts_cost_cents"],
        total_cost_today_cents=total_range,
        total_cost_month_cents=total_month,
    )


@router.get("/analytics")
async def get_analytics(
    period: str = "30d",
    current_user: User = Depends(require_superadmin),
):
    """Fetch website analytics from Plausible Stats API."""
    if not settings.PLAUSIBLE_API_KEY:
        raise HTTPException(status_code=503, detail="Plausible API key niet geconfigureerd")

    site_id = settings.PLAUSIBLE_SITE_ID
    headers = {"Authorization": f"Bearer {settings.PLAUSIBLE_API_KEY}"}
    base = "https://plausible.io/api/v1/stats"

    today = date.today()
    period_map = {
        "7d": today - timedelta(days=6),
        "30d": today - timedelta(days=29),
        "6mo": today - timedelta(days=180),
        "12mo": today - timedelta(days=365),
    }

    if period in period_map:
        plausible_params = {
            "site_id": site_id,
            "period": "custom",
            "date": f"{period_map[period].isoformat()},{today.isoformat()}",
        }
    else:
        plausible_params = {"site_id": site_id, "period": period}

    async with httpx.AsyncClient(timeout=15.0) as client:
        aggregate_req = client.get(
            f"{base}/aggregate",
            params={
                **plausible_params,
                "metrics": "visitors,pageviews,bounce_rate,visit_duration,visits",
            },
            headers=headers,
        )
        timeseries_req = client.get(
            f"{base}/timeseries",
            params={
                **plausible_params,
                "metrics": "visitors,pageviews",
            },
            headers=headers,
        )
        pages_req = client.get(
            f"{base}/breakdown",
            params={
                **plausible_params,
                "property": "event:page",
                "metrics": "visitors,pageviews",
                "limit": 10,
            },
            headers=headers,
        )
        sources_req = client.get(
            f"{base}/breakdown",
            params={
                **plausible_params,
                "property": "visit:source",
                "metrics": "visitors",
                "limit": 10,
            },
            headers=headers,
        )

        agg_resp, ts_resp, pages_resp, sources_resp = await asyncio.gather(
            aggregate_req, timeseries_req, pages_req, sources_req
        )

    result = {"aggregate": {}, "timeseries": [], "top_pages": [], "top_sources": []}

    if agg_resp.status_code == 200:
        result["aggregate"] = agg_resp.json().get("results", {})
    else:
        logger.warning(f"[ANALYTICS] Plausible aggregate failed: {agg_resp.status_code} {agg_resp.text}")

    if ts_resp.status_code == 200:
        result["timeseries"] = ts_resp.json().get("results", [])

    if pages_resp.status_code == 200:
        result["top_pages"] = pages_resp.json().get("results", [])

    if sources_resp.status_code == 200:
        result["top_sources"] = sources_resp.json().get("results", [])

    return result


@router.get("/analytics/realtime")
async def get_realtime_visitors(
    current_user: User = Depends(require_superadmin),
):
    """Fetch current realtime visitors from Plausible."""
    if not settings.PLAUSIBLE_API_KEY:
        return {"visitors": 0}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://plausible.io/api/v1/stats/realtime/visitors",
                params={"site_id": settings.PLAUSIBLE_SITE_ID},
                headers={"Authorization": f"Bearer {settings.PLAUSIBLE_API_KEY}"},
            )
            if resp.status_code == 200:
                return {"visitors": int(resp.text)}
    except Exception as e:
        logger.warning(f"[ANALYTICS] Realtime fetch failed: {e}")
    return {"visitors": 0}


@router.get("/metrics/business", response_model=BusinessMetrics)
async def get_business_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get business metrics including MRR, customer counts, and growth.
    Optimized with SQL aggregation for better performance.
    """
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Total customers (single query)
    total_customers = db.query(func.count(Company.id)).scalar() or 0
    
    # Count by subscription status (single query with case statements)
    status_counts = db.query(
        func.count(case((Company.subscription_status == "active", 1))).label("active"),
        func.count(case((Company.subscription_status == "trialing", 1))).label("trialing"),
        func.count(case((
            or_(
                Company.subscription_status == "pending",
                Company.subscription_status.is_(None),
                Company.subscription_status == ""
            ), 1
        ))).label("pending"),
        func.count(case((
            and_(
                Company.subscription_status == "canceled",
                Company.updated_at >= month_start
            ), 1
        ))).label("churned_this_month"),
    ).first()
    
    active_only = status_counts.active or 0
    trialing_customers = status_counts.trialing or 0
    active_customers = active_only + trialing_customers  # trialing counts as active
    pending_customers = status_counts.pending or 0
    churned_this_month = status_counts.churned_this_month or 0
    
    # Count by plan for active/trialing customers (single query)
    plan_counts = db.query(
        func.count(case((Company.subscription_plan == "starter", 1))).label("starter"),
        func.count(case((Company.subscription_plan == "business", 1))).label("business"),
        func.count(case((Company.subscription_plan == "enterprise", 1))).label("enterprise"),
    ).filter(
        Company.subscription_status.in_(["active", "trialing"])
    ).first()
    
    starter_customers = plan_counts.starter or 0
    business_customers = plan_counts.business or 0
    enterprise_customers = plan_counts.enterprise or 0
    
    # Calculate MRR (only active, not trialing)
    # Monthly prices in cents: starter=€99, business=€499, enterprise=€799
    # Yearly with ~15% discount: starter=€1.008, business=€5.088, enterprise=€8.148
    # MRR for yearly = yearly_price / 12
    MONTHLY_PRICES = {"starter": 9900, "business": 49900, "enterprise": 79900}
    YEARLY_PRICES_MRR = {"starter": 8400, "business": 42400, "enterprise": 67900}  # yearly / 12 (~15% discount)

    active_companies = db.query(
        Company.subscription_plan, Company.billing_interval
    ).filter(
        Company.subscription_status == "active"
    ).all()

    mrr_cents = 0
    for plan, interval in active_companies:
        plan_key = plan.value if hasattr(plan, "value") else str(plan)
        if interval == BillingInterval.yearly:
            mrr_cents += YEARLY_PRICES_MRR.get(plan_key, 0)
        else:
            mrr_cents += MONTHLY_PRICES.get(plan_key, 0)
    
    # New customers in period (single query)
    new_customers_this_month = db.query(func.count(Company.id)).filter(
        Company.created_at >= month_start
    ).scalar() or 0
    
    # Trial to paid conversion rate (2 simple count queries)
    total_ever_trialed = db.query(func.count(Company.id)).filter(
        Company.stripe_subscription_id.isnot(None)
    ).scalar() or 0
    
    total_converted = db.query(func.count(Company.id)).filter(
        Company.subscription_status == "active",
        Company.stripe_subscription_id.isnot(None)
    ).scalar() or 0
    
    trial_to_paid_rate = (total_converted / total_ever_trialed * 100) if total_ever_trialed > 0 else 0.0
    
    return BusinessMetrics(
        total_customers=total_customers,
        active_customers=active_customers,
        trialing_customers=trialing_customers,
        pending_customers=pending_customers,
        starter_customers=starter_customers,
        business_customers=business_customers,
        enterprise_customers=enterprise_customers,
        mrr_cents=mrr_cents,
        arr_cents=mrr_cents * 12,
        new_customers_this_month=new_customers_this_month,
        churned_this_month=churned_this_month,
        trial_to_paid_rate=round(trial_to_paid_rate, 1),
    )


# ==================== CUSTOMER ENDPOINTS ====================

@router.get("/customers", response_model=CustomerListResponse)
async def get_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get all customers with their stats.
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    companies = db.query(Company).all()
    
    result = []
    for company in companies:
        # Get stats for this company
        calls_today = db.query(func.count(CallLog.id)).filter(
            and_(
                CallLog.company_id == company.id,
                CallLog.created_at >= today_start
            )
        ).scalar() or 0
        
        calls_month = db.query(func.count(CallLog.id)).filter(
            and_(
                CallLog.company_id == company.id,
                CallLog.created_at >= month_start
            )
        ).scalar() or 0
        
        errors_today = db.query(func.count(CallLog.id)).filter(
            and_(
                CallLog.company_id == company.id,
                CallLog.created_at >= today_start,
                CallLog.error_message.isnot(None)
            )
        ).scalar() or 0
        
        unknown_today = db.query(func.count(ExampleAnswer.id)).filter(
            and_(
                ExampleAnswer.company_id == company.id,
                ExampleAnswer.source == "detected",
                ExampleAnswer.created_at >= today_start
            )
        ).scalar() or 0
        
        spend_today = db.query(func.sum(UsageLog.total_cost_cents)).filter(
            and_(
                UsageLog.company_id == company.id,
                UsageLog.created_at >= today_start
            )
        ).scalar() or 0
        
        spend_month = db.query(func.sum(UsageLog.total_cost_cents)).filter(
            and_(
                UsageLog.company_id == company.id,
                UsageLog.created_at >= month_start
            )
        ).scalar() or 0
        
        stats = CustomerStats(
            calls_today=calls_today,
            calls_this_month=calls_month,
            errors_today=errors_today,
            error_rate=(errors_today / calls_today * 100) if calls_today > 0 else 0,
            unknown_questions_today=unknown_today,
            unknown_rate=(unknown_today / calls_today * 100) if calls_today > 0 else 0,
            spend_today_cents=spend_today,
            spend_month_cents=spend_month,
        )
        
        result.append(CustomerListItem(
            id=company.id,
            name=company.name,
            slug=company.slug,
            email=company.email,
            subscription_plan=company.subscription_plan.value if company.subscription_plan else "starter",
            subscription_status=company.subscription_status or "active",
            billing_interval=company.billing_interval.value if company.billing_interval else "monthly",
            is_active=company.is_active,
            is_kill_switched=company.is_kill_switched or False,
            created_at=company.created_at,
            stats=stats,
        ))
    
    return CustomerListResponse(customers=result, total=len(result))


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
async def get_customer_detail(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get detailed customer info including hidden admin overrides.
    """
    company = db.query(Company).filter(Company.id == customer_id).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Klant niet gevonden")
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Get stats
    calls_today = db.query(func.count(CallLog.id)).filter(
        and_(CallLog.company_id == company.id, CallLog.created_at >= today_start)
    ).scalar() or 0
    
    calls_month = db.query(func.count(CallLog.id)).filter(
        and_(CallLog.company_id == company.id, CallLog.created_at >= month_start)
    ).scalar() or 0
    
    errors_today = db.query(func.count(CallLog.id)).filter(
        and_(
            CallLog.company_id == company.id,
            CallLog.created_at >= today_start,
            CallLog.error_message.isnot(None)
        )
    ).scalar() or 0
    
    unknown_today = db.query(func.count(ExampleAnswer.id)).filter(
        and_(
            ExampleAnswer.company_id == company.id,
            ExampleAnswer.source == "detected",
            ExampleAnswer.created_at >= today_start
        )
    ).scalar() or 0
    
    spend_today = db.query(func.sum(UsageLog.total_cost_cents)).filter(
        and_(UsageLog.company_id == company.id, UsageLog.created_at >= today_start)
    ).scalar() or 0
    
    spend_month = db.query(func.sum(UsageLog.total_cost_cents)).filter(
        and_(UsageLog.company_id == company.id, UsageLog.created_at >= month_start)
    ).scalar() or 0
    
    stats = CustomerStats(
        calls_today=calls_today,
        calls_this_month=calls_month,
        errors_today=errors_today,
        error_rate=(errors_today / calls_today * 100) if calls_today > 0 else 0,
        unknown_questions_today=unknown_today,
        unknown_rate=(unknown_today / calls_today * 100) if calls_today > 0 else 0,
        spend_today_cents=spend_today,
        spend_month_cents=spend_month,
    )
    
    return CustomerDetail(
        id=company.id,
        name=company.name,
        slug=company.slug,
        email=company.email,
        phone=company.phone,
        subscription_plan=company.subscription_plan.value if company.subscription_plan else "starter",
        subscription_status=company.subscription_status or "active",
        billing_interval=company.billing_interval.value if company.billing_interval else "monthly",
        stripe_customer_id=company.stripe_customer_id,
        is_active=company.is_active,
        is_verified=company.is_verified,
        is_kill_switched=company.is_kill_switched or False,
        feature_flags=company.feature_flags or {},
        admin_overrides=company.admin_overrides or {},
        inferred_business_type=company.inferred_business_type,
        inferred_business_confidence=company.inferred_business_confidence,
        inferred_topics=company.inferred_topics,
        business_type_override=company.business_type_override,
        stats=stats,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


@router.put("/customers/{customer_id}/overrides")
async def update_customer_overrides(
    customer_id: UUID,
    data: CustomerOverridesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Update hidden admin overrides for a customer.
    """
    company = db.query(Company).filter(Company.id == customer_id).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Klant niet gevonden")
    
    if data.admin_overrides is not None:
        company.admin_overrides = data.admin_overrides
    
    if data.feature_flags is not None:
        company.feature_flags = data.feature_flags

    if data.business_type_override is not None:
        company.business_type_override = data.business_type_override or None

    db.commit()
    
    return {"status": "updated", "customer_id": str(customer_id)}


@router.put("/customers/{customer_id}/subscription")
async def update_customer_subscription(
    customer_id: UUID,
    data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Update a customer's subscription plan and/or status.
    """
    from app.models.company import SubscriptionPlan
    
    company = db.query(Company).filter(Company.id == customer_id).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Klant niet gevonden")
    
    old_plan = company.subscription_plan.value if company.subscription_plan else "starter"
    old_status = company.subscription_status or "pending"
    
    # Update plan if provided
    if data.subscription_plan:
        valid_plans = ["starter", "business", "enterprise"]
        if data.subscription_plan not in valid_plans:
            raise HTTPException(
                status_code=400, 
                detail=f"Ongeldig plan. Kies uit: {', '.join(valid_plans)}"
            )
        company.subscription_plan = SubscriptionPlan(data.subscription_plan)
        
        # Update max_ai_workers based on plan
        plan_limits = {
            "starter": 1,
            "business": 5,
            "enterprise": 999,
        }
        company.max_ai_workers = plan_limits.get(data.subscription_plan, 1)
    
    # Update status if provided
    if data.subscription_status:
        valid_statuses = ["active", "trialing", "pending", "canceled"]
        if data.subscription_status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Ongeldige status. Kies uit: {', '.join(valid_statuses)}"
            )
        company.subscription_status = data.subscription_status
    
    db.commit()
    db.refresh(company)
    
    logger.info(
        f"Subscription updated for {company.name} by {current_user.email}: "
        f"plan {old_plan} -> {company.subscription_plan.value}, "
        f"status {old_status} -> {company.subscription_status}"
    )
    
    return {
        "status": "updated",
        "customer_id": str(customer_id),
        "subscription_plan": company.subscription_plan.value,
        "subscription_status": company.subscription_status,
        "max_ai_workers": company.max_ai_workers,
    }


@router.post("/customers/{customer_id}/kill-switch")
async def toggle_kill_switch(
    customer_id: UUID,
    data: KillSwitchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Enable or disable the kill switch for a customer (stops all calls).
    """
    company = db.query(Company).filter(Company.id == customer_id).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Klant niet gevonden")
    
    company.is_kill_switched = data.enabled
    
    # Set all AI workers for this company to OFFLINE (or back to AVAILABLE)
    workers = db.query(AIWorker).filter(AIWorker.company_id == company.id).all()
    worker_count = 0
    for worker in workers:
        if data.enabled:
            # Kill switch ON: set all workers to OFFLINE
            if worker.status != AIWorkerStatus.OFFLINE:
                worker.status = AIWorkerStatus.OFFLINE
                worker.is_active = False
                worker_count += 1
        else:
            # Kill switch OFF: restore workers to AVAILABLE
            if worker.status == AIWorkerStatus.OFFLINE:
                worker.status = AIWorkerStatus.AVAILABLE
                worker.is_active = True
                worker_count += 1
    
    db.commit()
    
    # With ElevenLabs Conversational AI, no warm sessions to tear down.
    # Active calls will be rejected on the next inbound check.
    
    action = "ingeschakeld" if data.enabled else "uitgeschakeld"
    logger.warning(
        f"Kill switch {action} voor {company.name} door {current_user.email}. "
        f"Reden: {data.reason}. {worker_count} workers bijgewerkt."
    )
    
    return {
        "status": "updated",
        "customer_id": str(customer_id),
        "is_kill_switched": data.enabled,
        "workers_affected": worker_count,
    }


@router.delete("/customers/{customer_id}")
async def delete_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Permanently delete a customer and all associated data.
    This action cannot be undone.
    """
    company = db.query(Company).filter(Company.id == customer_id).first()
    
    if not company:
        raise HTTPException(status_code=404, detail="Klant niet gevonden")
    
    company_name = company.name
    company_email = company.email
    
    # Delete all related data (cascades should handle most, but be explicit)
    # notifications and usage_logs have no cascade in Company model, so delete them first
    logger.warning(
        f"DELETING CUSTOMER: {company_name} ({company_email}) by {current_user.email}"
    )
    
    db.query(Notification).filter(Notification.company_id == customer_id).delete()
    db.query(UsageLog).filter(UsageLog.company_id == customer_id).delete()
    db.delete(company)
    db.commit()
    
    logger.info(f"Customer {company_name} deleted successfully")
    
    return {
        "status": "deleted",
        "customer_id": str(customer_id),
        "customer_name": company_name,
    }


# ==================== GLOBAL CONFIG ENDPOINTS ====================

@router.get("/config", response_model=GlobalConfigByCategoryResponse)
async def get_global_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get all global configs grouped by category.
    """
    configs = db.query(GlobalConfig).order_by(GlobalConfig.key).all()
    
    result = {
        "policies": [],
        "model": [],
        "voice": [],
        "thresholds": [],
    }
    
    for config in configs:
        response = GlobalConfigResponse(
            id=config.id,
            key=config.key,
            value=config.value,
            category=config.category,
            description=config.description,
            updated_by_id=config.updated_by_id,
            updated_by_name=config.updated_by.full_name if config.updated_by else None,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
        if config.category in result:
            result[config.category].append(response)
    
    return GlobalConfigByCategoryResponse(**result)


@router.put("/config/{key}")
async def update_global_config(
    key: str,
    data: GlobalConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Update a global config value.
    """
    config = db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Config '{key}' niet gevonden")
    
    if data.value is not None:
        config.value = data.value
    
    if data.description is not None:
        config.description = data.description
    
    config.updated_by_id = current_user.id
    db.commit()
    db.refresh(config)
    
    return GlobalConfigResponse(
        id=config.id,
        key=config.key,
        value=config.value,
        category=config.category,
        description=config.description,
        updated_by_id=config.updated_by_id,
        updated_by_name=current_user.full_name,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/config/seed")
async def seed_global_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Seed default global configs (only creates non-existing keys).
    """
    created = 0
    
    for config_data in DEFAULT_CONFIGS:
        existing = db.query(GlobalConfig).filter(
            GlobalConfig.key == config_data["key"]
        ).first()
        
        if not existing:
            config = GlobalConfig(
                key=config_data["key"],
                value=config_data["value"],
                category=config_data["category"],
                description=config_data.get("description"),
                updated_by_id=current_user.id,
            )
            db.add(config)
            created += 1
    
    db.commit()
    
    return {"status": "seeded", "created": created}


# ==================== VOICE PREVIEW ENDPOINT ====================

from app.core.voices import OPENAI_VOICES, TTS_SUPPORTED_VOICES, VOICE_SAMPLE_TEXT


@router.get("/voices")
async def list_voices(
    current_user: User = Depends(require_superadmin),
):
    """
    List available ElevenLabs voices with metadata.
    """
    return {"voices": OPENAI_VOICES}


@router.get("/voice-preview/{voice_id}")
async def preview_voice(
    voice_id: str,
    current_user: User = Depends(require_superadmin),
):
    """
    Generate a voice preview using ElevenLabs TTS API.
    Returns MP3 audio for browser playback.
    """
    from fastapi.responses import Response
    import httpx

    valid_ids = [v["id"] for v in OPENAI_VOICES]
    if voice_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Ongeldige stem: {voice_id}. Kies uit: {', '.join(valid_ids)}",
        )

    # Use shared voice preview cache
    from app.api.v1.endpoints.ai_workers import _voice_preview_cache

    if voice_id in _voice_preview_cache:
        return Response(
            content=_voice_preview_cache[voice_id],
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'inline; filename="preview-{voice_id}.mp3"',
                "Cache-Control": "public, max-age=86400",
            },
        )

    settings = get_settings()
    if not settings.ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY niet geconfigureerd")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": VOICE_SAMPLE_TEXT,
                    "model_id": "eleven_v3",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
            )
            resp.raise_for_status()

        audio_bytes = resp.content
        if len(audio_bytes) < 1000:
            logger.warning(f"Voice preview suspiciously small ({len(audio_bytes)} bytes), not caching")
            raise HTTPException(status_code=500, detail="Preview audio te kort — probeer opnieuw")
        _voice_preview_cache[voice_id] = audio_bytes  # Cache only complete audio
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'inline; filename="preview-{voice_id}.mp3"',
                "Cache-Control": "public, max-age=86400",
            },
        )
    except Exception as e:
        logger.error(f"Voice preview error for {voice_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Kon preview niet genereren: {str(e)}")


# ==================== LOGS ENDPOINTS ====================

@router.get("/calls/recent", response_model=RecentCallsResponse)
async def get_recent_calls(
    limit: int = 50,
    company_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get recent calls for the logs tab.
    """
    query = db.query(CallLog).order_by(CallLog.created_at.desc())
    
    if company_id:
        query = query.filter(CallLog.company_id == company_id)
    
    calls = query.limit(limit).all()
    
    result = []
    for call in calls:
        result.append({
            "id": str(call.id),
            "company_id": str(call.company_id),
            "company_name": call.company.name if call.company else "Unknown",
            "caller_number": mask_transcript(call.caller_number) if call.caller_number else "",
            "called_number": call.called_number,
            "status": call.status.value if call.status else "unknown",
            "outcome": call.outcome.value if call.outcome else None,
            "duration_seconds": call.duration_seconds or 0,
            "has_error": call.error_message is not None,
            "created_at": call.created_at.isoformat(),
        })
    
    return RecentCallsResponse(calls=result, total=len(result))


@router.get("/calls/{call_id}/trace", response_model=CallTraceResponse)
async def get_call_trace(
    call_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get complete call trace for debugging.
    """
    call = db.query(CallLog).filter(CallLog.id == call_id).first()
    
    if not call:
        raise HTTPException(status_code=404, detail="Oproep niet gevonden")
    
    # Get transcripts (PII masked)
    transcripts_db = db.query(CallTranscript).filter(
        CallTranscript.call_log_id == call_id
    ).order_by(CallTranscript.timestamp).all()
    
    transcripts = []
    for t in transcripts_db:
        transcripts.append(TranscriptEntry(
            speaker=t.speaker,
            message=mask_transcript(t.message, call.customer_name),
            timestamp=t.timestamp,
            confidence=t.confidence,
        ))
    
    # Get context logs
    context_logs_db = db.query(ContextLog).filter(
        ContextLog.call_log_id == call_id
    ).order_by(ContextLog.turn_id).all()
    
    context_logs = []
    total_tool_calls = 0
    for cl in context_logs_db:
        tool_calls = cl.tool_calls or []
        total_tool_calls += len(tool_calls)
        context_logs.append(ContextLogResponse(
            id=cl.id,
            turn_id=cl.turn_id,
            user_transcript=mask_transcript(cl.user_transcript, call.customer_name) if cl.user_transcript else None,
            assistant_transcript=cl.assistant_transcript,
            detected_intent=cl.detected_intent,
            intent_confidence=cl.intent_confidence,
            tool_calls=tool_calls,
            facts=cl.facts,
            instructions=cl.instructions,
            model_used=cl.model_used,
            was_escalated=cl.was_escalated or 0,
            created_at=cl.created_at,
        ))
    
    # Get latency logs
    latency_logs_db = db.query(LatencyLog).filter(
        LatencyLog.call_log_id == call_id
    ).order_by(LatencyLog.turn_id).all()
    
    latency_logs = []
    for ll in latency_logs_db:
        latency_logs.append(LatencyLogResponse(
            id=ll.id,
            turn_id=ll.turn_id,
            stt_latency_ms=ll.stt_latency_ms,
            orchestrator_latency_ms=ll.orchestrator_latency_ms,
            pod_latency_ms=ll.pod_latency_ms,
            tts_latency_ms=ll.tts_latency_ms,
            total_latency_ms=ll.total_latency_ms,
            queue_wait_ms=ll.queue_wait_ms,
            created_at=ll.created_at,
        ))
    
    return CallTraceResponse(
        call_id=call.id,
        company_id=call.company_id,
        company_name=call.company.name if call.company else "Unknown",
        ai_worker_name=call.ai_worker.name if call.ai_worker else None,
        caller_number=mask_transcript(call.caller_number) if call.caller_number else "",
        called_number=call.called_number,
        status=call.status.value if call.status else "unknown",
        outcome=call.outcome.value if call.outcome else None,
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_seconds=call.duration_seconds or 0,
        transcripts=transcripts,
        context_logs=context_logs,
        latency_logs=latency_logs,
        total_turns=len(context_logs),
        total_tool_calls=total_tool_calls,
        error_message=call.error_message,
        hangup_reason=getattr(call, "hangup_reason", None),
        goodbye_handshake_ok=getattr(call, "goodbye_handshake_ok", None),
        ended_by=getattr(call, "ended_by", None),
        policy_violations_count=getattr(call, "policy_violations_count", 0) or 0,
    )


# ════════════════════════════════════════════════════════════════════
# VOICE SESSIONS & POLICY DECISIONS — /admin/voice
# ════════════════════════════════════════════════════════════════════

@router.get("/voice/sessions")
async def list_voice_sessions(
    call_id: Optional[UUID] = None,
    company_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List voice sessions with filters."""
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin required")

    query = db.query(VoiceSession).order_by(VoiceSession.created_at.desc())
    if call_id:
        query = query.filter(VoiceSession.call_log_id == call_id)
    if company_id:
        query = query.filter(VoiceSession.company_id == company_id)

    total = query.count()
    sessions = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "sessions": [
            {
                "id": str(s.id),
                "call_log_id": str(s.call_log_id) if s.call_log_id else None,
                "call_sid": s.call_sid,
                "company_id": str(s.company_id) if s.company_id else None,
                "phase": s.phase,
                "turn_count": s.turn_count,
                "last_customer_intent": s.last_customer_intent,
                "goodbye_said_by_agent": s.goodbye_said_by_agent,
                "goodbye_said_by_customer": s.goodbye_said_by_customer,
                "goodbye_handshake_ok": s.goodbye_handshake_ok,
                "escalation_requested": s.escalation_requested,
                "transfer_executed": s.transfer_executed,
                "low_confidence_count": s.low_confidence_count,
                "repeat_topic_count": s.repeat_topic_count,
                "frustration_count": getattr(s, "frustration_count", 0) or 0,
                "off_topic_block_count": getattr(s, "off_topic_block_count", 0) or 0,
                "output_guardrail_block_count": getattr(s, "output_guardrail_block_count", 0) or 0,
                "language_violation_count": getattr(s, "language_violation_count", 0) or 0,
                "retrieval_skip_count": getattr(s, "retrieval_skip_count", 0) or 0,
                "last_retrieval_score": getattr(s, "last_retrieval_score", None),
                "hangup_reason": s.hangup_reason,
                "ended_by": s.ended_by,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ],
    }


@router.get("/voice/sessions/{session_id}")
async def get_voice_session_detail(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get voice session detail with all policy decisions."""
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin required")

    session = db.query(VoiceSession).filter(VoiceSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Voice session not found")

    decisions = (
        db.query(PolicyDecisionLog)
        .filter(PolicyDecisionLog.voice_session_id == session_id)
        .order_by(PolicyDecisionLog.turn_number, PolicyDecisionLog.created_at)
        .all()
    )

    return {
        "session": {
            "id": str(session.id),
            "call_log_id": str(session.call_log_id) if session.call_log_id else None,
            "call_sid": session.call_sid,
            "company_id": str(session.company_id) if session.company_id else None,
            "phase": session.phase,
            "turn_count": session.turn_count,
            "last_customer_intent": session.last_customer_intent,
            "last_customer_utterance": session.last_customer_utterance,
            "goodbye_said_by_agent": session.goodbye_said_by_agent,
            "goodbye_said_by_customer": session.goodbye_said_by_customer,
            "goodbye_handshake_ok": session.goodbye_handshake_ok,
            "escalation_requested": session.escalation_requested,
            "transfer_executed": session.transfer_executed,
            "low_confidence_count": session.low_confidence_count,
            "repeat_topic_count": session.repeat_topic_count,
            "frustration_count": getattr(session, "frustration_count", 0) or 0,
            "off_topic_block_count": getattr(session, "off_topic_block_count", 0) or 0,
            "output_guardrail_block_count": getattr(session, "output_guardrail_block_count", 0) or 0,
            "language_violation_count": getattr(session, "language_violation_count", 0) or 0,
            "retrieval_count": session.retrieval_count,
            "retrieval_skip_count": getattr(session, "retrieval_skip_count", 0) or 0,
            "last_retrieval_score": getattr(session, "last_retrieval_score", None),
            "end_call_attempts": session.end_call_attempts,
            "hangup_reason": session.hangup_reason,
            "ended_by": session.ended_by,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        },
        "policy_decisions": [
            {
                "id": str(d.id),
                "turn_number": d.turn_number,
                "trigger_tool": d.trigger_tool,
                "trigger_reason": d.trigger_reason,
                "phase_before": d.phase_before,
                "phase_after": d.phase_after,
                "detected_intent": d.detected_intent,
                "intent_confidence": d.intent_confidence,
                "policy_name": d.policy_name,
                "allowed": d.allowed,
                "required_action": d.required_action,
                "reason_code": d.reason_code,
                "instruction_nl": d.instruction_nl,
                "model_complied": d.model_complied,
                "violation": d.violation,
                "violation_type": d.violation_type,
                "retrieval_confidence": getattr(d, "retrieval_confidence", None),
                "retrieval_used": getattr(d, "retrieval_used", None),
                "guardrail_passed": getattr(d, "guardrail_passed", None),
                "guardrail_violations": getattr(d, "guardrail_violations", None),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in decisions
        ],
    }


@router.get("/voice/calls/{call_id}/policy-trace")
async def get_call_policy_trace(
    call_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full policy trace for a call: voice session + all policy decisions.
    Combines with context logs to give a turn-by-turn view.
    """
    if not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="Superadmin required")

    session = db.query(VoiceSession).filter(
        VoiceSession.call_log_id == call_id
    ).first()

    decisions = (
        db.query(PolicyDecisionLog)
        .filter(PolicyDecisionLog.call_log_id == call_id)
        .order_by(PolicyDecisionLog.turn_number, PolicyDecisionLog.created_at)
        .all()
    )

    call = db.query(CallLog).filter(CallLog.id == call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    violations = [d for d in decisions if d.violation]

    # Summary counters (computed from decisions)
    off_topic_blocks = sum(1 for d in decisions if d.policy_name == "scope_guard" and not d.allowed)
    low_confidence_blocks = sum(1 for d in decisions if d.policy_name == "low_confidence" and not d.allowed)
    repeated_failure_triggers = sum(
        1 for d in decisions
        if d.policy_name == "repeated_failure" and d.required_action in ("clarify", "escalate")
    )
    guardrail_blocks = sum(
        1 for d in decisions if getattr(d, "guardrail_passed", None) is False
    )
    language_violations = sum(
        1 for d in decisions
        if getattr(d, "guardrail_violations", None) and "language_violation" in (d.guardrail_violations or "")
    )
    frustration_count = getattr(session, "frustration_count", 0) if session else 0

    return {
        "call_id": str(call_id),
        "call_sid": session.call_sid if session else None,
        "call_status": call.status.value if call.status else None,
        "call_outcome": call.outcome.value if call.outcome else None,
        "hangup_reason": call.hangup_reason,
        "goodbye_handshake_ok": call.goodbye_handshake_ok,
        "ended_by": call.ended_by,
        "policy_violations_count": call.policy_violations_count,
        "session": {
            "phase": session.phase if session else None,
            "turn_count": session.turn_count if session else 0,
            "goodbye_said_by_agent": session.goodbye_said_by_agent if session else None,
            "goodbye_said_by_customer": session.goodbye_said_by_customer if session else None,
            "escalation_requested": session.escalation_requested if session else None,
            "low_confidence_count": session.low_confidence_count if session else 0,
            "repeat_topic_count": session.repeat_topic_count if session else 0,
            "frustration_count": getattr(session, "frustration_count", 0) or 0,
            "off_topic_block_count": getattr(session, "off_topic_block_count", 0) or 0,
            "output_guardrail_block_count": getattr(session, "output_guardrail_block_count", 0) or 0,
            "language_violation_count": getattr(session, "language_violation_count", 0) or 0,
            "retrieval_skip_count": getattr(session, "retrieval_skip_count", 0) or 0,
            "last_retrieval_score": getattr(session, "last_retrieval_score", None),
        } if session else None,
        "summary_counters": {
            "off_topic_blocks": off_topic_blocks,
            "low_confidence_blocks": low_confidence_blocks,
            "repeated_failure_triggers": repeated_failure_triggers,
            "output_guardrail_blocks": guardrail_blocks,
            "language_violations": language_violations,
            "frustration_signals": frustration_count or 0,
            "total_safeguard_interventions": (
                off_topic_blocks + low_confidence_blocks +
                repeated_failure_triggers + guardrail_blocks
            ),
        },
        "decisions": [
            {
                "turn": d.turn_number,
                "tool": d.trigger_tool,
                "reason": d.trigger_reason,
                "intent": d.detected_intent,
                "confidence": d.intent_confidence,
                "policy": d.policy_name,
                "allowed": d.allowed,
                "action": d.required_action,
                "code": d.reason_code,
                "instruction": d.instruction_nl,
                "violation": d.violation,
                "phase": f"{d.phase_before} → {d.phase_after}",
                "retrieval_confidence": getattr(d, "retrieval_confidence", None),
                "retrieval_used": getattr(d, "retrieval_used", None),
                "guardrail_passed": getattr(d, "guardrail_passed", None),
                "guardrail_violations": getattr(d, "guardrail_violations", None),
                "at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in decisions
        ],
        "violations": [
            {
                "turn": v.turn_number,
                "policy": v.policy_name,
                "type": v.violation_type,
                "at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in violations
        ],
        "total_decisions": len(decisions),
        "total_violations": len(violations),
    }


# ---------------------------------------------------------------------------
# Billing Runs
# ---------------------------------------------------------------------------

@router.get("/billing-runs", dependencies=[Depends(require_superadmin)])
async def list_billing_runs(
    db: Session = Depends(get_db),
    company_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List billing runs with optional filters. Errors and stuck runs shown first."""
    from datetime import timedelta

    STUCK_THRESHOLD = timedelta(hours=2)

    query = db.query(BillingRun)
    if company_id:
        query = query.filter(BillingRun.company_id == company_id)
    if status_filter:
        query = query.filter(BillingRun.status == status_filter)

    query = query.order_by(
        case(
            (BillingRun.status == BillingRunStatus.error, 0),
            else_=1,
        ),
        BillingRun.created_at.desc(),
    )
    total = query.count()
    runs = query.offset(offset).limit(limit).all()

    now = datetime.utcnow()
    stuck_cutoff = now - STUCK_THRESHOLD
    stuck_count = db.query(func.count(BillingRun.id)).filter(
        BillingRun.status == BillingRunStatus.calculated,
        BillingRun.created_at < stuck_cutoff,
    ).scalar()

    def _format_run(r):
        is_stuck = (
            r.status == BillingRunStatus.calculated
            and r.created_at
            and r.created_at < stuck_cutoff
        )
        return {
            "id": str(r.id),
            "company_id": str(r.company_id),
            "company_name": r.company.name if r.company else None,
            "stripe_invoice_id": r.stripe_invoice_id,
            "period_start": r.period_start.isoformat(),
            "period_end": r.period_end.isoformat(),
            "minutes_included": r.minutes_included,
            "minutes_used": r.minutes_used,
            "overage_minutes": r.overage_minutes,
            "overage_amount_cents": r.overage_amount_cents,
            "stripe_invoice_item_id": r.stripe_invoice_item_id,
            "status": r.status.value if r.status else None,
            "is_stuck": is_stuck,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }

    return {
        "total": total,
        "stuck_calculated_count": stuck_count,
        "billing_runs": [_format_run(r) for r in runs],
    }


@router.post("/billing-runs/{run_id}/retry", dependencies=[Depends(require_superadmin)])
async def retry_billing_run(
    run_id: UUID,
    db: Session = Depends(get_db),
):
    """Retry a failed billing run. Safe to call multiple times (Stripe idempotency key).
    If the original invoice is finalized, creates a standalone InvoiceItem for the next invoice."""
    import stripe as stripe_mod
    from app.api.v1.endpoints.payments import get_overage_rate

    billing_run = db.query(BillingRun).filter(BillingRun.id == run_id).first()
    if not billing_run:
        raise HTTPException(status_code=404, detail="Billing run not found")

    if billing_run.status not in (BillingRunStatus.error, BillingRunStatus.calculated):
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry runs with status error or calculated, got {billing_run.status.value}",
        )

    if billing_run.overage_minutes <= 0:
        billing_run.status = BillingRunStatus.skipped
        billing_run.error_message = None
        db.commit()
        return {"status": "skipped", "message": "No overage to charge"}

    company = billing_run.company
    if not company:
        raise HTTPException(status_code=400, detail="Company not found for billing run")

    overage_rate = get_overage_rate(company.subscription_plan.value)
    idempotency_key = billing_run.stripe_idempotency_key or f"overage-{billing_run.id}"
    description = f"{billing_run.overage_minutes} extra belminuten à €{overage_rate:.2f}/min"

    try:
        item = stripe_mod.InvoiceItem.create(
            customer=company.stripe_customer_id,
            invoice=billing_run.stripe_invoice_id,
            amount=billing_run.overage_amount_cents,
            currency="eur",
            description=description,
            idempotency_key=idempotency_key,
        )
        billing_run.stripe_invoice_item_id = item.id
        billing_run.status = BillingRunStatus.charged
        billing_run.error_message = None
        db.commit()
        logger.info(
            f"[BILLING RETRY] Successfully charged billing_run {run_id} "
            f"for {company.name}: €{billing_run.overage_amount_cents / 100:.2f}"
        )
        return {"status": "charged", "stripe_invoice_item_id": item.id}
    except stripe_mod.error.InvalidRequestError as e:
        err_lower = str(e).lower()
        if "finalized" in err_lower or "not open" in err_lower:
            logger.warning(
                f"[BILLING RETRY] Invoice finalized for {company.name}, "
                f"creating standalone InvoiceItem for next invoice"
            )
            try:
                fallback_key = f"overage-fallback-{billing_run.id}"
                period_label = (
                    f" (periode {billing_run.period_start.date()}→{billing_run.period_end.date()})"
                    if billing_run.period_start and billing_run.period_end else ""
                )
                item = stripe_mod.InvoiceItem.create(
                    customer=company.stripe_customer_id,
                    amount=billing_run.overage_amount_cents,
                    currency="eur",
                    description=f"{description}{period_label}",
                    idempotency_key=fallback_key,
                )
                billing_run.stripe_invoice_item_id = item.id
                billing_run.status = BillingRunStatus.charged
                billing_run.error_message = "Attached to next invoice (original was finalized)"
                db.commit()
                logger.info(f"[BILLING RETRY] Standalone InvoiceItem created for {company.name}")
                return {"status": "charged_next_invoice", "stripe_invoice_item_id": item.id}
            except stripe_mod.error.StripeError as fallback_err:
                billing_run.error_message = f"Finalized + fallback failed: {fallback_err}"
                db.commit()
                logger.error(f"[BILLING RETRY] Fallback also failed for {run_id}: {fallback_err}")
                raise HTTPException(status_code=502, detail=f"Fallback failed: {fallback_err}")
        else:
            billing_run.error_message = f"Retry failed: {e}"
            db.commit()
            logger.error(f"[BILLING RETRY] Failed for billing_run {run_id}: {e}")
            raise HTTPException(status_code=502, detail=f"Stripe error: {e}")
    except stripe_mod.error.StripeError as e:
        billing_run.error_message = f"Retry failed: {e}"
        db.commit()
        logger.error(f"[BILLING RETRY] Failed for billing_run {run_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe error: {e}")


# ==================== Evaluations ====================

def _evaluation_to_response(ev: CallEvaluation) -> dict:
    """Convert a CallEvaluation with preloaded relationships into a response dict.

    Expects call_log (with ai_worker) and company to be eagerly loaded.
    """
    call = ev.call_log
    worker = call.ai_worker if call else None
    company = ev.company

    return {
        "id": ev.id,
        "call_log_id": ev.call_log_id,
        "company_id": ev.company_id,
        "quality_score": ev.quality_score,
        "hallucination_detected": ev.hallucination_detected,
        "wrong_tool_detected": ev.wrong_tool_detected,
        "customer_helped": ev.customer_helped,
        "needs_review": ev.needs_review,
        "latency_ms": ev.latency_ms,
        "summary": ev.summary,
        "issues": ev.issues or [],
        "tool_usage": ev.tool_usage or [],
        "langsmith_run_id": ev.langsmith_run_id,
        "evaluator_model": ev.evaluator_model,
        "evaluated_at": ev.evaluated_at,
        "created_at": ev.created_at,
        "caller_number": call.caller_number if call else None,
        "called_number": call.called_number if call else None,
        "call_started_at": call.started_at if call else None,
        "call_duration_seconds": call.duration_seconds if call else None,
        "ai_worker_name": worker.name if worker else None,
        "company_name": company.name if company else None,
    }


def _eval_eager_options():
    """Shared eager-load options for evaluation queries."""
    return [
        joinedload(CallEvaluation.call_log).joinedload(CallLog.ai_worker),
        joinedload(CallEvaluation.company),
    ]


@router.get("/evaluations/summary")
async def get_evaluation_summary(
    company_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get aggregate KPI metrics for evaluations in a single query."""
    filters = []
    if company_id:
        filters.append(CallEvaluation.company_id == company_id)
    if date_from:
        filters.append(CallEvaluation.evaluated_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        filters.append(CallEvaluation.evaluated_at <= datetime.combine(date_to, datetime.max.time()))

    row = db.query(
        func.count(CallEvaluation.id).label("total"),
        func.avg(CallEvaluation.quality_score).label("avg_score"),
        func.sum(case((CallEvaluation.hallucination_detected == True, 1), else_=0)).label("hallucinations"),
        func.sum(case((CallEvaluation.wrong_tool_detected == True, 1), else_=0)).label("wrong_tools"),
        func.sum(case((CallEvaluation.customer_helped == True, 1), else_=0)).label("helped"),
        func.sum(case((CallEvaluation.needs_review == True, 1), else_=0)).label("reviews"),
    ).filter(*filters).one()

    total = row.total or 0
    if total == 0:
        return EvaluationSummaryResponse()

    return EvaluationSummaryResponse(
        total_evaluated=total,
        average_score=round(float(row.avg_score), 1) if row.avg_score else None,
        hallucination_rate=round(int(row.hallucinations) / total * 100, 1),
        wrong_tool_rate=round(int(row.wrong_tools) / total * 100, 1),
        customer_helped_rate=round(int(row.helped) / total * 100, 1),
        needs_review_count=int(row.reviews),
    )


@router.get("/evaluations/{evaluation_id}")
async def get_evaluation_detail(
    evaluation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Get detailed evaluation including transcript."""
    ev = (
        db.query(CallEvaluation)
        .options(*_eval_eager_options())
        .filter(CallEvaluation.id == evaluation_id)
        .first()
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    data = _evaluation_to_response(ev)

    transcripts = db.query(CallTranscript).filter(
        CallTranscript.call_log_id == ev.call_log_id
    ).order_by(CallTranscript.timestamp).all()

    data["transcript"] = [
        TranscriptEntryResponse(
            speaker=t.speaker,
            message=t.message,
            timestamp=t.timestamp,
        ).model_dump()
        for t in transcripts
    ]

    return data


@router.get("/evaluations")
async def list_evaluations(
    page: int = 1,
    page_size: int = 20,
    company_id: Optional[UUID] = None,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    hallucination_only: bool = False,
    wrong_tool_only: bool = False,
    needs_review_only: bool = False,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort_by: str = "evaluated_at",
    sort_dir: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """List evaluations with filtering, sorting, pagination."""
    filters = []
    if company_id:
        filters.append(CallEvaluation.company_id == company_id)
    if min_score is not None:
        filters.append(CallEvaluation.quality_score >= min_score)
    if max_score is not None:
        filters.append(CallEvaluation.quality_score <= max_score)
    if hallucination_only:
        filters.append(CallEvaluation.hallucination_detected == True)
    if wrong_tool_only:
        filters.append(CallEvaluation.wrong_tool_detected == True)
    if needs_review_only:
        filters.append(CallEvaluation.needs_review == True)
    if date_from:
        filters.append(CallEvaluation.evaluated_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        filters.append(CallEvaluation.evaluated_at <= datetime.combine(date_to, datetime.max.time()))

    _sortable = {
        "evaluated_at": CallEvaluation.evaluated_at,
        "quality_score": CallEvaluation.quality_score,
        "created_at": CallEvaluation.created_at,
    }
    sort_col = _sortable.get(sort_by, CallEvaluation.evaluated_at)
    order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()

    total = db.query(func.count(CallEvaluation.id)).filter(*filters).scalar() or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    evaluations = (
        db.query(CallEvaluation)
        .options(*_eval_eager_options())
        .filter(*filters)
        .order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_evaluation_to_response(ev) for ev in evaluations]

    return EvaluationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/evaluations/sync")
async def sync_evaluations_endpoint(
    body: EvaluationSyncRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """Trigger batch evaluation of calls that haven't been evaluated yet."""
    from app.services.langsmith_service import sync_evaluations

    company_id = str(body.company_id) if body and body.company_id else None
    limit = body.limit if body else 50

    asyncio.create_task(_run_sync_evaluations(company_id, limit))

    return {
        "status": "started",
        "message": f"Evaluatie gestart voor maximaal {limit} gesprekken.",
    }


async def _run_sync_evaluations(company_id: Optional[str], limit: int):
    """Background task for batch evaluation sync."""
    from app.core.database import SessionLocal
    from app.services.langsmith_service import sync_evaluations

    db = SessionLocal()
    try:
        result = await sync_evaluations(db, company_id=company_id, limit=limit)
        logger.info("[EVAL SYNC] Complete: %s", result)
    except Exception as e:
        logger.error("[EVAL SYNC] Failed: %s", e, exc_info=True)
    finally:
        db.close()
