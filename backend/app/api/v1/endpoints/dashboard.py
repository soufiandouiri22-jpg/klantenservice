"""
klantenservice.ai - Dashboard Endpoints
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db

AMS_TZ = ZoneInfo("Europe/Amsterdam")
from app.models.user import User
from app.models.company import Company
from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.models.call_log import CallLog, CallStatus, CallOutcome
from app.models.appointment import Appointment, AppointmentStatus
from app.models.internal_note import InternalNote
from app.schemas.company import CompanyStats
from app.api.deps import get_current_user, get_current_company

router = APIRouter()


@router.get("/stats", response_model=CompanyStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get dashboard statistics for the current company.
    """
    now_ams = datetime.now(AMS_TZ)
    today_start = now_ams.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    today_end = today_start + timedelta(days=1)
    week_start = today_start - timedelta(days=now_ams.weekday())
    week_end = week_start + timedelta(days=7)
    month_start = now_ams.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    # AI Workers stats
    total_workers = db.query(AIWorker).filter(
        AIWorker.company_id == company.id
    ).count()

    active_workers = db.query(AIWorker).filter(
        AIWorker.company_id == company.id,
        AIWorker.is_active == True,
        AIWorker.status == AIWorkerStatus.AVAILABLE
    ).count()

    # Active calls
    active_calls = db.query(CallLog).filter(
        CallLog.company_id == company.id,
        CallLog.status.in_([CallStatus.RINGING, CallStatus.IN_PROGRESS])
    ).count()

    # Calls today
    calls_today = db.query(CallLog).filter(
        CallLog.company_id == company.id,
        CallLog.started_at >= today_start,
        CallLog.started_at < today_end
    ).count()

    # Monthly call base query
    month_calls_q = db.query(CallLog).filter(
        CallLog.company_id == company.id,
        CallLog.started_at >= month_start,
    )

    calls_this_month = month_calls_q.count()

    calls_answered_month = month_calls_q.filter(
        CallLog.status == CallStatus.COMPLETED
    ).count()

    calls_missed_month = month_calls_q.filter(
        CallLog.status.in_([CallStatus.MISSED, CallStatus.ABANDONED, CallStatus.FAILED])
    ).count()

    avg_duration = month_calls_q.filter(
        CallLog.duration_seconds > 0
    ).with_entities(func.avg(CallLog.duration_seconds)).scalar() or 0

    # Appointments made by AI this month
    appointments_made_by_ai_month = month_calls_q.filter(
        CallLog.outcome == CallOutcome.APPOINTMENT_MADE
    ).count()

    # Sentiment breakdown (all time for this company, only calls with sentiment)
    sentiment_counts = db.query(
        CallLog.sentiment, func.count(CallLog.id)
    ).filter(
        CallLog.company_id == company.id,
        CallLog.sentiment.isnot(None),
    ).group_by(CallLog.sentiment).all()
    sentiment_map = {s: c for s, c in sentiment_counts}

    # Appointments today
    appointments_today = db.query(Appointment).filter(
        Appointment.company_id == company.id,
        Appointment.starts_at >= today_start,
        Appointment.starts_at < today_end,
        Appointment.status == AppointmentStatus.CONFIRMED
    ).count()

    # Appointments this week
    appointments_week = db.query(Appointment).filter(
        Appointment.company_id == company.id,
        Appointment.starts_at >= week_start,
        Appointment.starts_at < week_end,
        Appointment.status == AppointmentStatus.CONFIRMED
    ).count()

    # Unresolved notes
    unresolved_notes = db.query(InternalNote).filter(
        InternalNote.company_id == company.id,
        InternalNote.is_resolved == False
    ).count()

    return CompanyStats(
        active_ai_workers=active_workers,
        total_ai_workers=total_workers,
        active_calls=active_calls,
        calls_today=calls_today,
        calls_this_month=calls_this_month,
        calls_answered_month=calls_answered_month,
        calls_missed_month=calls_missed_month,
        avg_duration_seconds=int(avg_duration),
        appointments_today=appointments_today,
        appointments_this_week=appointments_week,
        appointments_made_by_ai_month=appointments_made_by_ai_month,
        unresolved_notes=unresolved_notes,
        sentiment_positive=sentiment_map.get("positive", 0),
        sentiment_neutral=sentiment_map.get("neutral", 0),
        sentiment_negative=sentiment_map.get("negative", 0),
    )


@router.get("/recent-calls")
async def get_recent_calls(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get recent calls for dashboard.
    """
    calls = db.query(CallLog).filter(
        CallLog.company_id == company.id
    ).order_by(CallLog.started_at.desc()).limit(limit).all()
    
    return [
        {
            "id": str(call.id),
            "caller_number": call.caller_number,
            "status": call.status.value,
            "outcome": call.outcome.value if call.outcome else None,
            "duration_seconds": call.duration_seconds,
            "customer_name": call.customer_name,
            "started_at": call.started_at.isoformat(),
            "summary": call.summary,
        }
        for call in calls
    ]


@router.get("/upcoming-appointments")
async def get_upcoming_appointments(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get upcoming appointments for dashboard.
    """
    now = datetime.now(AMS_TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    appointments = db.query(Appointment).filter(
        Appointment.company_id == company.id,
        Appointment.starts_at >= now,
        Appointment.status == AppointmentStatus.CONFIRMED
    ).order_by(Appointment.starts_at).limit(limit).all()
    
    return [
        {
            "id": str(apt.id),
            "title": apt.title,
            "customer_name": apt.customer_name,
            "starts_at": apt.starts_at.isoformat(),
            "ends_at": apt.ends_at.isoformat(),
            "duration_minutes": apt.duration_minutes,
        }
        for apt in appointments
    ]


@router.get("/action-items")
async def get_action_items(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get action items (unresolved notes with action required) for dashboard.
    """
    notes = db.query(InternalNote).filter(
        InternalNote.company_id == company.id,
        InternalNote.is_resolved == False,
        InternalNote.action_required == True
    ).order_by(InternalNote.created_at.desc()).limit(limit).all()
    
    return [
        {
            "id": str(note.id),
            "title": note.title,
            "priority": note.priority.value,
            "customer_name": note.customer_name,
            "customer_phone": note.customer_phone,
            "action_description": note.action_description,
            "action_due_at": note.action_due_at.isoformat() if note.action_due_at else None,
            "created_at": note.created_at.isoformat(),
        }
        for note in notes
    ]


@router.get("/ai-workers-status")
async def get_ai_workers_status(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get status of all AI workers for dashboard.
    """
    workers = db.query(AIWorker).filter(
        AIWorker.company_id == company.id
    ).all()
    
    return [
        {
            "id": str(worker.id),
            "name": worker.name,
            "role_title": worker.role_title,
            "status": worker.status.value,
            "is_active": worker.is_active,
            "total_calls_handled": worker.total_calls_handled,
            "last_call_at": worker.last_call_at.isoformat() if worker.last_call_at else None,
        }
        for worker in workers
    ]
