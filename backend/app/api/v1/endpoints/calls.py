"""
klantenservice.ai - Call Log Endpoints
"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
import httpx
import logging

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.call_log import CallLog, CallTranscript, CallStatus, CallOutcome
from app.models.ai_worker import AIWorker
from app.models.phone_number import PhoneNumber
from app.schemas.call_log import (
    CallLogResponse,
    CallLogListResponse,
    CallDetailResponse,
    CallTranscriptResponse,
    CallStatsResponse,
)
from app.api.deps import get_current_user, get_current_company

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=CallLogListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[CallStatus] = None,
    outcome: Optional[CallOutcome] = None,
    ai_worker_id: Optional[UUID] = None,
    phone_number_id: Optional[UUID] = None,
    sentiment: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List call logs with filters and pagination.
    """
    query = db.query(CallLog).filter(CallLog.company_id == company.id)
    
    if start_date:
        query = query.filter(CallLog.started_at >= start_date)
    if end_date:
        query = query.filter(CallLog.started_at <= end_date)
    if status:
        query = query.filter(CallLog.status == status)
    if outcome:
        query = query.filter(CallLog.outcome == outcome)
    if ai_worker_id:
        query = query.filter(CallLog.ai_worker_id == ai_worker_id)
    if phone_number_id:
        query = query.filter(CallLog.phone_number_id == phone_number_id)
    if sentiment:
        query = query.filter(CallLog.sentiment == sentiment)
    if search:
        query = query.filter(
            (CallLog.caller_number.ilike(f"%{search}%")) |
            (CallLog.customer_name.ilike(f"%{search}%"))
        )
    
    total = query.count()
    total_pages = (total + page_size - 1) // page_size
    
    calls = query.order_by(CallLog.started_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    return CallLogListResponse(
        items=calls,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/stats", response_model=CallStatsResponse)
async def get_call_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get call statistics.
    """
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()
    
    base_query = db.query(CallLog).filter(
        CallLog.company_id == company.id,
        CallLog.started_at >= start_date,
        CallLog.started_at <= end_date
    )
    
    total_calls = base_query.count()
    
    completed_calls = base_query.filter(CallLog.status == CallStatus.COMPLETED).count()
    missed_calls = base_query.filter(CallLog.status == CallStatus.MISSED).count()
    voicemails = base_query.filter(CallLog.status == CallStatus.VOICEMAIL).count()
    
    avg_duration = base_query.filter(
        CallLog.duration_seconds > 0
    ).with_entities(func.avg(CallLog.duration_seconds)).scalar() or 0
    
    avg_wait_time = base_query.filter(
        CallLog.queue_wait_seconds > 0
    ).with_entities(func.avg(CallLog.queue_wait_seconds)).scalar() or 0
    
    appointments_made = base_query.filter(
        CallLog.outcome == CallOutcome.APPOINTMENT_MADE
    ).count()
    
    notes_created = base_query.filter(
        CallLog.outcome == CallOutcome.NOTE_LEFT
    ).count()
    
    # Sentiment breakdown
    sentiment_counts = base_query.filter(
        CallLog.sentiment.isnot(None)
    ).with_entities(
        CallLog.sentiment,
        func.count(CallLog.id)
    ).group_by(CallLog.sentiment).all()
    sentiment_breakdown = {s: c for s, c in sentiment_counts}
    
    # Calls by hour (simplified)
    calls_by_hour = {}
    for hour in range(24):
        count = base_query.filter(
            func.extract('hour', CallLog.started_at) == hour
        ).count()
        if count > 0:
            calls_by_hour[hour] = count
    
    # Calls by day of week
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    calls_by_day = {}
    for i, day in enumerate(days):
        count = base_query.filter(
            func.extract('dow', CallLog.started_at) == i
        ).count()
        if count > 0:
            calls_by_day[day] = count
    
    return CallStatsResponse(
        total_calls=total_calls,
        completed_calls=completed_calls,
        missed_calls=missed_calls,
        voicemails=voicemails,
        average_duration_seconds=int(avg_duration),
        average_wait_time_seconds=int(avg_wait_time),
        appointments_made=appointments_made,
        notes_created=notes_created,
        sentiment_breakdown=sentiment_breakdown,
        calls_by_hour=calls_by_hour,
        calls_by_day=calls_by_day,
    )


@router.get("/{call_id}", response_model=CallDetailResponse)
async def get_call(
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get detailed call information including transcript.
    """
    call = db.query(CallLog).filter(
        CallLog.id == call_id,
        CallLog.company_id == company.id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gesprek niet gevonden",
        )
    
    # Get AI worker name
    ai_worker_name = None
    if call.ai_worker_id:
        worker = db.query(AIWorker).filter(AIWorker.id == call.ai_worker_id).first()
        if worker:
            ai_worker_name = worker.name
    
    # Get phone number friendly name
    phone_friendly_name = None
    if call.phone_number_id:
        phone = db.query(PhoneNumber).filter(PhoneNumber.id == call.phone_number_id).first()
        if phone:
            phone_friendly_name = phone.friendly_name
    
    # Get transcripts
    transcripts = db.query(CallTranscript).filter(
        CallTranscript.call_log_id == call_id
    ).order_by(CallTranscript.timestamp).all()
    
    return CallDetailResponse(
        **{k: v for k, v in call.__dict__.items() if not k.startswith('_')},
        transcripts=transcripts,
        ai_worker_name=ai_worker_name,
        phone_number_friendly_name=phone_friendly_name,
    )


@router.get("/{call_id}/transcript", response_model=List[CallTranscriptResponse])
async def get_call_transcript(
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get call transcript only.
    """
    call = db.query(CallLog).filter(
        CallLog.id == call_id,
        CallLog.company_id == company.id
    ).first()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gesprek niet gevonden",
        )
    
    transcripts = db.query(CallTranscript).filter(
        CallTranscript.call_log_id == call_id
    ).order_by(CallTranscript.timestamp).all()
    
    return transcripts


@router.get("/active/current")
async def get_active_calls(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get currently active calls.
    """
    calls = db.query(CallLog).filter(
        CallLog.company_id == company.id,
        CallLog.status.in_([CallStatus.RINGING, CallStatus.IN_PROGRESS])
    ).all()
    
    result = []
    for call in calls:
        worker_name = None
        if call.ai_worker_id:
            worker = db.query(AIWorker).filter(AIWorker.id == call.ai_worker_id).first()
            if worker:
                worker_name = worker.name
        
        result.append({
            "id": str(call.id),
            "caller_number": call.caller_number,
            "called_number": call.called_number,
            "status": call.status.value,
            "ai_worker_name": worker_name,
            "started_at": call.started_at.isoformat(),
            "duration_seconds": (datetime.utcnow() - call.started_at).seconds if call.answered_at else 0,
        })
    
    return result


@router.get("/{call_id}/recording")
async def get_call_recording(
    call_id: UUID,
    token: str = Query(..., description="JWT access token (needed because <audio> can't send headers)"),
    db: Session = Depends(get_db),
):
    """Proxy Twilio recording audio so the frontend can play it without Twilio auth."""
    from app.core.security import decode_token

    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Ongeldige token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="Gebruiker niet gevonden")

    company = db.query(Company).filter(Company.id == user.company_id).first()
    if not company:
        raise HTTPException(status_code=403, detail="Geen bedrijf gekoppeld")

    call = db.query(CallLog).filter(
        CallLog.id == call_id,
        CallLog.company_id == company.id,
    ).first()

    if not call:
        raise HTTPException(status_code=404, detail="Gesprek niet gevonden")
    if not call.recording_url:
        raise HTTPException(status_code=404, detail="Geen opname beschikbaar")

    audio_url = call.recording_url
    if not audio_url.endswith(".mp3"):
        audio_url += ".mp3"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            audio_url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Kon opname niet ophalen")

    return StreamingResponse(
        iter([resp.content]),
        media_type="audio/mpeg",
        headers={"Content-Disposition": f"inline; filename=recording-{call_id}.mp3"},
    )
