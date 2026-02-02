"""
klantenservice.ai - Calendar Integration Endpoints
"""
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.database import get_db
from app.core.security import encrypt_value, decrypt_value
from app.models.user import User
from app.models.company import Company
from app.models.calendar_integration import CalendarIntegration, CalendarProvider
from app.schemas.calendar import (
    CalendarIntegrationCreate,
    CalendarIntegrationUpdate,
    CalendarIntegrationResponse,
    AvailabilityRequest,
    AvailabilityResponse,
    AvailabilitySlot,
    HoldSlotRequest,
    HoldSlotResponse,
)
from app.api.deps import get_current_user, get_current_company, require_admin

router = APIRouter()


@router.get("", response_model=List[CalendarIntegrationResponse])
async def list_calendars(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all calendar integrations for the current company.
    """
    calendars = db.query(CalendarIntegration).filter(
        CalendarIntegration.company_id == company.id
    ).all()
    return calendars


@router.post("", response_model=CalendarIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar(
    data: CalendarIntegrationCreate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Create a new calendar integration.
    For OAuth providers (Google, Microsoft), this initiates the OAuth flow.
    """
    calendar = CalendarIntegration(
        id=uuid4(),
        company_id=company.id,
        name=data.name,
        provider=data.provider,
        is_active=True,
    )
    
    # Handle CalDAV credentials
    if data.provider == CalendarProvider.CALDAV:
        if not all([data.caldav_url, data.caldav_username, data.caldav_password]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CalDAV vereist URL, gebruikersnaam en wachtwoord",
            )
        calendar.caldav_url = data.caldav_url
        calendar.caldav_username = data.caldav_username
        calendar.caldav_password_encrypted = encrypt_value(data.caldav_password)
    
    db.add(calendar)
    db.commit()
    db.refresh(calendar)
    
    return calendar


@router.get("/oauth/{provider}/url")
async def get_oauth_url(
    provider: CalendarProvider,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
):
    """
    Get OAuth authorization URL for calendar provider.
    """
    if provider == CalendarProvider.CALDAV:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CalDAV gebruikt geen OAuth",
        )
    
    # In production, generate proper OAuth URLs
    # This is a placeholder
    base_urls = {
        CalendarProvider.GOOGLE: "https://accounts.google.com/o/oauth2/v2/auth",
        CalendarProvider.MICROSOFT: "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    }
    
    return {
        "provider": provider.value,
        "auth_url": base_urls.get(provider),
        "message": "Redirect de gebruiker naar deze URL om de agenda te koppelen",
    }


@router.get("/{calendar_id}", response_model=CalendarIntegrationResponse)
async def get_calendar(
    calendar_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get a specific calendar integration.
    """
    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == calendar_id,
        CalendarIntegration.company_id == company.id
    ).first()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agenda-integratie niet gevonden",
        )
    
    return calendar


@router.patch("/{calendar_id}", response_model=CalendarIntegrationResponse)
async def update_calendar(
    calendar_id: UUID,
    data: CalendarIntegrationUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update a calendar integration.
    """
    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == calendar_id,
        CalendarIntegration.company_id == company.id
    ).first()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agenda-integratie niet gevonden",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    
    # If setting as primary, unset other primaries
    if update_data.get("is_primary"):
        db.query(CalendarIntegration).filter(
            CalendarIntegration.company_id == company.id,
            CalendarIntegration.id != calendar_id
        ).update({"is_primary": False})
    
    for field, value in update_data.items():
        if field == "availability_rules" and value:
            value = value.model_dump() if hasattr(value, 'model_dump') else value
        if field == "appointment_types" and value:
            value = [v.model_dump() if hasattr(v, 'model_dump') else v for v in value]
        setattr(calendar, field, value)
    
    db.commit()
    db.refresh(calendar)
    
    return calendar


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar(
    calendar_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Delete a calendar integration.
    """
    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == calendar_id,
        CalendarIntegration.company_id == company.id
    ).first()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agenda-integratie niet gevonden",
        )
    
    db.delete(calendar)
    db.commit()


@router.post("/{calendar_id}/availability", response_model=AvailabilityResponse)
async def get_availability(
    calendar_id: UUID,
    request: AvailabilityRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get available time slots from calendar.
    """
    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == calendar_id,
        CalendarIntegration.company_id == company.id
    ).first()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agenda-integratie niet gevonden",
        )
    
    # TODO: Implement actual calendar availability check
    # This is a mock implementation
    slots = []
    current = request.start_date
    while current < request.end_date:
        if current.weekday() < 5 and 9 <= current.hour < 17:  # Weekdays 9-17
            slots.append(AvailabilitySlot(
                start=current,
                end=current + timedelta(minutes=request.duration_minutes),
                duration_minutes=request.duration_minutes,
            ))
        current += timedelta(minutes=30)
    
    return AvailabilityResponse(
        slots=slots[:20],  # Limit results
        calendar_id=calendar.id,
        calendar_name=calendar.name,
    )


@router.post("/{calendar_id}/hold", response_model=HoldSlotResponse)
async def hold_slot(
    calendar_id: UUID,
    request: HoldSlotRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Temporarily hold a time slot (used during phone calls).
    """
    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == calendar_id,
        CalendarIntegration.company_id == company.id
    ).first()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agenda-integratie niet gevonden",
        )
    
    # TODO: Implement actual slot holding
    hold_id = uuid4()
    expires_at = datetime.utcnow() + timedelta(seconds=request.hold_duration_seconds)
    
    return HoldSlotResponse(
        hold_id=hold_id,
        slot=request.slot,
        expires_at=expires_at,
    )


@router.post("/{calendar_id}/sync")
async def sync_calendar(
    calendar_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Manually trigger calendar sync.
    """
    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == calendar_id,
        CalendarIntegration.company_id == company.id
    ).first()
    
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agenda-integratie niet gevonden",
        )
    
    # TODO: Implement actual sync
    calendar.last_sync_at = datetime.utcnow()
    db.commit()
    
    return {
        "message": "Synchronisatie gestart",
        "calendar_id": str(calendar.id),
        "last_sync_at": calendar.last_sync_at.isoformat(),
    }
