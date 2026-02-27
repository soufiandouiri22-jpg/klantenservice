"""
klantenservice.ai - Appointment Endpoints
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.appointment import Appointment, AppointmentStatus
from app.models.calendar_integration import CalendarIntegration, CalendarProvider
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    AppointmentListResponse,
    AppointmentCancelRequest,
    AppointmentRescheduleRequest,
)
from app.api.deps import get_current_user, get_current_company, require_manager

logger = logging.getLogger(__name__)
router = APIRouter()


async def _sync_create_event(calendar: CalendarIntegration, db: Session, appointment: Appointment):
    """Create an event in the external calendar and store the event ID."""
    if not calendar.access_token_encrypted:
        return
    try:
        if calendar.provider == CalendarProvider.MICROSOFT:
            from app.services import outlook_calendar_service as svc
        else:
            from app.services import google_calendar_service as svc
        event = await svc.book_appointment(
            calendar=calendar,
            db=db,
            summary=appointment.title,
            start=appointment.starts_at,
            end=appointment.ends_at,
            description=appointment.description or "",
            attendee_email=appointment.customer_email or "",
        )
        appointment.external_event_id = event.get("id")
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to create external calendar event: {e}")


async def _sync_delete_event(calendar: CalendarIntegration, db: Session, external_event_id: str):
    """Delete an event from the external calendar."""
    if not calendar.access_token_encrypted or not external_event_id:
        return
    try:
        if calendar.provider == CalendarProvider.MICROSOFT:
            from app.services import outlook_calendar_service as svc
        else:
            from app.services import google_calendar_service as svc
        access_token = await svc.get_valid_access_token(calendar, db)
        cal_id = calendar.external_calendar_id or "primary"
        await svc.delete_event(access_token, cal_id, external_event_id)
    except Exception as e:
        logger.warning(f"Failed to delete external calendar event: {e}")


@router.get("", response_model=AppointmentListResponse)
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[AppointmentStatus] = None,
    calendar_id: Optional[UUID] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List appointments with filters and pagination.
    """
    query = db.query(Appointment).filter(Appointment.company_id == company.id)
    
    if start_date:
        query = query.filter(Appointment.starts_at >= start_date)
    if end_date:
        query = query.filter(Appointment.starts_at <= end_date)
    if status:
        query = query.filter(Appointment.status == status)
    if calendar_id:
        query = query.filter(Appointment.calendar_integration_id == calendar_id)
    if search:
        query = query.filter(
            (Appointment.customer_name.ilike(f"%{search}%")) |
            (Appointment.title.ilike(f"%{search}%"))
        )
    
    total = query.count()
    total_pages = (total + page_size - 1) // page_size
    
    appointments = query.order_by(Appointment.starts_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    return AppointmentListResponse(
        items=appointments,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    data: AppointmentCreate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Create a new appointment manually.
    """
    # Verify calendar exists and belongs to company
    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == data.calendar_integration_id,
        CalendarIntegration.company_id == company.id
    ).first()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agenda niet gevonden",
        )
    
    duration = int((data.ends_at - data.starts_at).total_seconds() / 60)
    
    appointment = Appointment(
        id=uuid4(),
        company_id=company.id,
        calendar_integration_id=data.calendar_integration_id,
        title=data.title,
        description=data.description,
        appointment_type=data.appointment_type,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        duration_minutes=duration,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        customer_email=data.customer_email,
        status=AppointmentStatus.CONFIRMED,
    )
    
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    await _sync_create_event(calendar, db, appointment)

    if data.customer_phone:
        try:
            from app.models.phone_number import PhoneNumber
            from app.services.sms_service import send_appointment_confirmation_sms

            phone_cfg = db.query(PhoneNumber).filter(
                PhoneNumber.company_id == company.id,
                PhoneNumber.is_active == True,
                PhoneNumber.sms_confirmation_enabled == True,
            ).first()

            if phone_cfg:
                day_names = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
                day_name = day_names[data.starts_at.weekday()]
                starts_at_readable = f"{day_name} {data.starts_at.day} {data.starts_at.strftime('%B')} om {data.starts_at.strftime('%H:%M')}"
                send_appointment_confirmation_sms(
                    to=data.customer_phone,
                    company_name=company.name or "ons bedrijf",
                    starts_at_readable=starts_at_readable,
                    custom_template=phone_cfg.sms_confirmation_template,
                )
        except Exception as e:
            logger.error(f"Failed to send confirmation SMS: {e}", exc_info=True)

    return appointment


@router.get("/upcoming")
async def get_upcoming_appointments(
    days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get upcoming appointments for the next N days.
    """
    now = datetime.now(ZoneInfo("Europe/Amsterdam")).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_date = now + timedelta(days=days)
    
    appointments = db.query(Appointment).filter(
        Appointment.company_id == company.id,
        Appointment.starts_at >= now,
        Appointment.starts_at <= end_date,
        Appointment.status == AppointmentStatus.CONFIRMED
    ).order_by(Appointment.starts_at).all()
    
    return appointments


@router.get("/today")
async def get_today_appointments(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get today's appointments.
    """
    now_ams = datetime.now(ZoneInfo("Europe/Amsterdam"))
    today_start = now_ams.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    today_end = today_start + timedelta(days=1)
    
    appointments = db.query(Appointment).filter(
        Appointment.company_id == company.id,
        Appointment.starts_at >= today_start,
        Appointment.starts_at < today_end,
        Appointment.status == AppointmentStatus.CONFIRMED
    ).order_by(Appointment.starts_at).all()
    
    return appointments


@router.get("/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get a specific appointment.
    """
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.company_id == company.id
    ).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Afspraak niet gevonden",
        )
    
    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: UUID,
    data: AppointmentUpdate,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update an appointment.
    """
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.company_id == company.id
    ).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Afspraak niet gevonden",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Recalculate duration if times changed
    if "starts_at" in update_data or "ends_at" in update_data:
        starts = update_data.get("starts_at", appointment.starts_at)
        ends = update_data.get("ends_at", appointment.ends_at)
        update_data["duration_minutes"] = int((ends - starts).total_seconds() / 60)
    
    for field, value in update_data.items():
        setattr(appointment, field, value)
    
    db.commit()
    db.refresh(appointment)

    if appointment.calendar_integration_id and appointment.external_event_id:
        calendar = db.query(CalendarIntegration).filter(
            CalendarIntegration.id == appointment.calendar_integration_id
        ).first()
        if calendar:
            await _sync_delete_event(calendar, db, appointment.external_event_id)
            await _sync_create_event(calendar, db, appointment)

    return appointment


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: UUID,
    data: AppointmentCancelRequest,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Cancel an appointment.
    """
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.company_id == company.id
    ).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Afspraak niet gevonden",
        )
    
    if appointment.status == AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Afspraak is al geannuleerd",
        )
    
    old_event_id = appointment.external_event_id

    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = datetime.utcnow()
    appointment.cancelled_by = "business"
    appointment.cancellation_reason = data.reason

    db.commit()

    if appointment.calendar_integration_id and old_event_id:
        calendar = db.query(CalendarIntegration).filter(
            CalendarIntegration.id == appointment.calendar_integration_id
        ).first()
        if calendar:
            await _sync_delete_event(calendar, db, old_event_id)

    return {"message": "Afspraak geannuleerd"}


@router.post("/{appointment_id}/reschedule")
async def reschedule_appointment(
    appointment_id: UUID,
    data: AppointmentRescheduleRequest,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Reschedule an appointment.
    """
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.company_id == company.id
    ).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Afspraak niet gevonden",
        )
    
    if appointment.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alleen bevestigde afspraken kunnen worden verzet",
        )
    
    old_event_id = appointment.external_event_id

    appointment.starts_at = data.new_starts_at
    appointment.ends_at = data.new_ends_at
    appointment.duration_minutes = int((data.new_ends_at - data.new_starts_at).total_seconds() / 60)

    db.commit()
    db.refresh(appointment)

    if appointment.calendar_integration_id:
        calendar = db.query(CalendarIntegration).filter(
            CalendarIntegration.id == appointment.calendar_integration_id
        ).first()
        if calendar:
            if old_event_id:
                await _sync_delete_event(calendar, db, old_event_id)
            await _sync_create_event(calendar, db, appointment)

    return appointment


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(
    appointment_id: UUID,
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Delete an appointment.
    """
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.company_id == company.id
    ).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Afspraak niet gevonden",
        )
    
    old_event_id = appointment.external_event_id
    cal_id = appointment.calendar_integration_id

    db.delete(appointment)
    db.commit()

    if cal_id and old_event_id:
        calendar = db.query(CalendarIntegration).filter(
            CalendarIntegration.id == cal_id
        ).first()
        if calendar:
            await _sync_delete_event(calendar, db, old_event_id)
