"""
klantenservice.ai - AI Worker Endpoints
"""
import logging
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID, uuid4

from app.core.database import get_db
from app.core.config import get_settings
from app.core.voices import CUSTOMER_VOICES, TTS_SUPPORTED_VOICES, VOICE_SAMPLE_TEXT
from app.models.user import User
from app.models.company import Company
from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.models.call_log import CallLog
from app.schemas.ai_worker import AIWorkerCreate, AIWorkerUpdate, AIWorkerResponse, AIWorkerStats
from app.api.deps import get_current_user, get_current_company, get_current_company_with_subscription, require_manager

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Voice endpoints (must be before /{worker_id} to avoid path conflicts) ──

@router.get("/voices")
async def list_customer_voices(
    current_user: User = Depends(get_current_user),
):
    """
    List voices available for customers to choose.
    Only returns voices that support TTS preview (no Realtime-only voices).
    """
    return {"voices": CUSTOMER_VOICES}


@router.get("/voice-preview/{voice_id}")
async def preview_customer_voice(
    voice_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a voice preview using OpenAI TTS API.
    Only available for TTS-supported voices.
    """
    from fastapi.responses import Response
    import openai

    if voice_id not in TTS_SUPPORTED_VOICES:
        valid_ids = [v["id"] for v in CUSTOMER_VOICES]
        raise HTTPException(
            status_code=400,
            detail=f"Ongeldige stem: {voice_id}. Kies uit: {', '.join(valid_ids)}",
        )

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY niet geconfigureerd")

    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.audio.speech.create(
            model="tts-1-hd",
            voice=voice_id,
            input=VOICE_SAMPLE_TEXT,
            response_format="mp3",
        )

        audio_bytes = response.content
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


# ── AI Worker CRUD endpoints ──────────────────────────────────────

@router.get("", response_model=List[AIWorkerResponse])
async def list_ai_workers(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all AI workers for the current company.
    """
    workers = db.query(AIWorker).filter(AIWorker.company_id == company.id).all()
    return workers


@router.post("", response_model=AIWorkerResponse, status_code=status.HTTP_201_CREATED)
async def create_ai_worker(
    data: AIWorkerCreate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company_with_subscription),  # Requires active subscription
    db: Session = Depends(get_db)
):
    """
    Create a new AI worker.
    Requires manager, admin, or owner role.
    Requires active subscription or trial.
    """
    # Check worker limit based on subscription plan
    current_count = db.query(AIWorker).filter(
        AIWorker.company_id == company.id
    ).count()
    
    if current_count >= company.ai_worker_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"U heeft het maximum aantal AI-medewerkers ({company.ai_worker_limit}) bereikt. Upgrade uw abonnement voor meer medewerkers.",
        )
    
    worker = AIWorker(
        id=uuid4(),
        company_id=company.id,
        name=data.name,
        role_title=data.role_title,
        tone_of_voice=data.tone_of_voice,
        address_form=data.address_form,
        behavior_settings=data.behavior_settings.model_dump() if data.behavior_settings else {},
        can_make_appointments=data.can_make_appointments,
        can_cancel_appointments=data.can_cancel_appointments,
        can_view_prices=data.can_view_prices,
        can_leave_notes=data.can_leave_notes,
        status=AIWorkerStatus.AVAILABLE,
        is_active=True,
    )
    
    db.add(worker)
    db.commit()
    db.refresh(worker)
    
    return worker


@router.get("/{worker_id}", response_model=AIWorkerResponse)
async def get_ai_worker(
    worker_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get a specific AI worker.
    """
    worker = db.query(AIWorker).filter(
        AIWorker.id == worker_id,
        AIWorker.company_id == company.id
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI-medewerker niet gevonden",
        )
    
    return worker


@router.patch("/{worker_id}", response_model=AIWorkerResponse)
async def update_ai_worker(
    worker_id: UUID,
    data: AIWorkerUpdate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update an AI worker.
    Requires manager, admin, or owner role.
    """
    worker = db.query(AIWorker).filter(
        AIWorker.id == worker_id,
        AIWorker.company_id == company.id
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI-medewerker niet gevonden",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Handle behavior_settings separately
    if "behavior_settings" in update_data and update_data["behavior_settings"]:
        update_data["behavior_settings"] = update_data["behavior_settings"].model_dump() if hasattr(update_data["behavior_settings"], 'model_dump') else update_data["behavior_settings"]
    
    for field, value in update_data.items():
        setattr(worker, field, value)
    
    db.commit()
    db.refresh(worker)
    
    return worker


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ai_worker(
    worker_id: UUID,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Delete an AI worker.
    Requires manager, admin, or owner role.
    """
    worker = db.query(AIWorker).filter(
        AIWorker.id == worker_id,
        AIWorker.company_id == company.id
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI-medewerker niet gevonden",
        )
    
    # Check if worker is currently in a call
    if worker.status == AIWorkerStatus.BUSY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-medewerker is momenteel in gesprek en kan niet worden verwijderd",
        )
    
    db.delete(worker)
    db.commit()


@router.get("/{worker_id}/stats", response_model=AIWorkerStats)
async def get_ai_worker_stats(
    worker_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get statistics for an AI worker.
    """
    worker = db.query(AIWorker).filter(
        AIWorker.id == worker_id,
        AIWorker.company_id == company.id
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI-medewerker niet gevonden",
        )
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    # Calls today
    calls_today = db.query(CallLog).filter(
        CallLog.ai_worker_id == worker_id,
        CallLog.started_at >= today_start
    ).count()
    
    # Calls this week
    calls_week = db.query(CallLog).filter(
        CallLog.ai_worker_id == worker_id,
        CallLog.started_at >= week_start
    ).count()
    
    # Calls this month
    calls_month = db.query(CallLog).filter(
        CallLog.ai_worker_id == worker_id,
        CallLog.started_at >= month_start
    ).count()
    
    # Average call duration
    avg_duration = db.query(func.avg(CallLog.duration_seconds)).filter(
        CallLog.ai_worker_id == worker_id,
        CallLog.duration_seconds > 0
    ).scalar() or 0
    
    # Sentiment breakdown
    sentiment_counts = db.query(
        CallLog.sentiment,
        func.count(CallLog.id)
    ).filter(
        CallLog.ai_worker_id == worker_id,
        CallLog.sentiment.isnot(None)
    ).group_by(CallLog.sentiment).all()
    
    sentiment_breakdown = {s: c for s, c in sentiment_counts}
    
    return AIWorkerStats(
        calls_today=calls_today,
        calls_this_week=calls_week,
        calls_this_month=calls_month,
        appointments_made_today=0,  # TODO: Implement
        average_call_duration_seconds=int(avg_duration),
        busiest_hour=None,  # TODO: Implement
        sentiment_breakdown=sentiment_breakdown,
    )


@router.post("/{worker_id}/toggle-status")
async def toggle_ai_worker_status(
    worker_id: UUID,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Toggle AI worker active status.
    """
    worker = db.query(AIWorker).filter(
        AIWorker.id == worker_id,
        AIWorker.company_id == company.id
    ).first()
    
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI-medewerker niet gevonden",
        )
    
    # Cannot deactivate if in call
    if worker.status == AIWorkerStatus.BUSY and worker.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-medewerker is momenteel in gesprek",
        )
    
    worker.is_active = not worker.is_active
    if not worker.is_active:
        worker.status = AIWorkerStatus.OFFLINE
    else:
        worker.status = AIWorkerStatus.AVAILABLE
    
    db.commit()
    
    return {
        "id": str(worker.id),
        "is_active": worker.is_active,
        "status": worker.status.value,
    }
