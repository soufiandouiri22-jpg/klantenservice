"""
klantenservice.ai - Calendar Integration Endpoints

Handles Google Calendar OAuth flow, availability checking, and appointment booking.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import encrypt_value
from app.models.user import User
from app.models.company import Company
from app.models.ai_worker import AIWorker
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
from app.services import google_calendar_service as gcal

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


# ── OAuth Flow (MUST come before /{calendar_id} routes) ──


@router.get("/oauth/{provider}/url")
async def get_oauth_url(
    provider: CalendarProvider,
    calendar_id: UUID = Query(..., description="Calendar integration ID to connect"),
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get OAuth authorization URL. Redirect the user's browser to this URL."""
    if provider == CalendarProvider.CALDAV:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CalDAV gebruikt geen OAuth",
        )

    if provider != CalendarProvider.GOOGLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alleen Google Calendar wordt momenteel ondersteund",
        )

    calendar = _get_calendar_or_404(calendar_id, company.id, db)

    state = json.dumps({"calendar_id": str(calendar.id), "company_id": str(company.id)})
    auth_url = gcal.build_auth_url(state)

    return {"auth_url": auth_url, "provider": provider.value}


@router.get("/oauth/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Google OAuth callback. Google redirects here after user consent.
    Exchanges the code for tokens and stores them encrypted.
    """
    try:
        state_data = json.loads(state)
        calendar_id = UUID(state_data["calendar_id"])
    except (json.JSONDecodeError, KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Ongeldige state parameter")

    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == calendar_id
    ).first()
    if not calendar:
        raise HTTPException(status_code=404, detail="Agenda-integratie niet gevonden")

    try:
        token_data = await gcal.exchange_code_for_tokens(code)
    except Exception as e:
        logger.error(f"Google token exchange failed: {e}")
        raise HTTPException(status_code=400, detail="Kon geen toegang krijgen tot Google Calendar")

    calendar.access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.token_expires_at = datetime.utcnow() + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.refresh_token_encrypted = encrypt_value(token_data["refresh_token"])

    try:
        access_token = token_data["access_token"]
        calendars = await gcal.list_google_calendars(access_token)
        primary = next((c for c in calendars if c["primary"]), calendars[0] if calendars else None)
        if primary:
            calendar.external_calendar_id = primary["id"]
            calendar.external_calendar_name = primary["summary"]
    except Exception as e:
        logger.warning(f"Could not fetch calendar list: {e}")

    calendar.last_sync_at = datetime.utcnow()
    calendar.sync_error = None
    calendar.is_active = True
    db.commit()

    logger.info(f"Google Calendar connected for integration {calendar.id}")

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(
        url=f"{frontend_url}/dashboard/calendar?connected=true&calendar_id={calendar.id}"
    )


# ── CRUD ──────────────────────────────────────────────────


@router.get("", response_model=List[CalendarIntegrationResponse])
async def list_calendars(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all calendar integrations for the current company."""
    calendars = (
        db.query(CalendarIntegration)
        .filter(CalendarIntegration.company_id == company.id)
        .all()
    )
    return calendars


@router.post(
    "", response_model=CalendarIntegrationResponse, status_code=status.HTTP_201_CREATED
)
async def create_calendar(
    data: CalendarIntegrationCreate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a new calendar integration (pre-OAuth — record created, then user connects)."""
    if not data.ai_worker_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecteer een AI-medewerker om deze agenda aan te koppelen.",
        )

    ai_worker = (
        db.query(AIWorker)
        .filter(AIWorker.id == data.ai_worker_id, AIWorker.company_id == company.id)
        .first()
    )
    if not ai_worker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-medewerker niet gevonden.",
        )

    existing_link = (
        db.query(CalendarIntegration)
        .filter(
            CalendarIntegration.ai_worker_id == data.ai_worker_id,
            CalendarIntegration.company_id == company.id,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"AI-medewerker '{ai_worker.name}' heeft al een agenda gekoppeld ({existing_link.name}). Ontkoppel deze eerst.",
        )

    calendar = CalendarIntegration(
        id=uuid4(),
        company_id=company.id,
        ai_worker_id=data.ai_worker_id,
        name=data.name,
        provider=data.provider,
        is_active=True,
    )

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


@router.get("/{calendar_id}", response_model=CalendarIntegrationResponse)
async def get_calendar(
    calendar_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get a specific calendar integration."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    return calendar


@router.patch("/{calendar_id}", response_model=CalendarIntegrationResponse)
async def update_calendar(
    calendar_id: UUID,
    data: CalendarIntegrationUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update a calendar integration."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    update_data = data.model_dump(exclude_unset=True)

    if update_data.get("is_primary"):
        db.query(CalendarIntegration).filter(
            CalendarIntegration.company_id == company.id,
            CalendarIntegration.id != calendar_id,
        ).update({"is_primary": False})

    for field, value in update_data.items():
        if field == "availability_rules" and value:
            value = value.model_dump() if hasattr(value, "model_dump") else value
        if field == "appointment_types" and value:
            value = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
        setattr(calendar, field, value)

    db.commit()
    db.refresh(calendar)
    return calendar


@router.delete("/{calendar_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar(
    calendar_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Delete a calendar integration."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    db.delete(calendar)
    db.commit()


# ── Calendar List (from Google) ───────────────────────────


@router.get("/{calendar_id}/google-calendars")
async def list_google_calendars_endpoint(
    calendar_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all Google Calendars the user has access to (after OAuth)."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    access_token = await gcal.get_valid_access_token(calendar, db)
    calendars = await gcal.list_google_calendars(access_token)
    return {"calendars": calendars}


@router.patch("/{calendar_id}/select-calendar")
async def select_google_calendar(
    calendar_id: UUID,
    external_calendar_id: str = Query(..., description="Google Calendar ID to use"),
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Select which Google Calendar to use for this integration."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    access_token = await gcal.get_valid_access_token(calendar, db)

    calendars = await gcal.list_google_calendars(access_token)
    selected = next((c for c in calendars if c["id"] == external_calendar_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Google Calendar niet gevonden")

    calendar.external_calendar_id = selected["id"]
    calendar.external_calendar_name = selected["summary"]
    db.commit()

    return {"message": "Agenda geselecteerd", "calendar_name": selected["summary"]}


# ── Availability ──────────────────────────────────────────


@router.post("/{calendar_id}/availability", response_model=AvailabilityResponse)
async def get_availability(
    calendar_id: UUID,
    request: AvailabilityRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get available time slots from the connected Google Calendar."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)

    if not calendar.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agenda is nog niet gekoppeld met Google. Doorloop eerst de OAuth-stap.",
        )

    try:
        slots_raw = await gcal.get_availability_for_range(
            calendar=calendar,
            db=db,
            start_date=request.start_date,
            end_date=request.end_date,
            duration_minutes=request.duration_minutes,
        )
    except Exception as e:
        logger.error(f"Availability check failed for calendar {calendar_id}: {e}")
        raise HTTPException(status_code=502, detail="Kon beschikbaarheid niet ophalen bij Google")

    slots = [
        AvailabilitySlot(
            start=datetime.fromisoformat(s["start"]),
            end=datetime.fromisoformat(s["end"]),
            duration_minutes=s["duration_minutes"],
        )
        for s in slots_raw
    ]

    return AvailabilityResponse(
        slots=slots,
        calendar_id=calendar.id,
        calendar_name=calendar.external_calendar_name or calendar.name,
    )


# ── Booking ───────────────────────────────────────────────


@router.post("/{calendar_id}/book")
async def book_appointment(
    calendar_id: UUID,
    summary: str = Query(..., description="Afspraak titel"),
    start: datetime = Query(..., description="Start tijd (ISO 8601)"),
    end: datetime = Query(..., description="Eind tijd (ISO 8601)"),
    description: str = Query("", description="Beschrijving"),
    attendee_email: str = Query("", description="E-mail van de klant"),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Book an appointment in the connected Google Calendar."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)

    if not calendar.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agenda is nog niet gekoppeld met Google.",
        )

    try:
        event = await gcal.book_appointment(
            calendar=calendar,
            db=db,
            summary=summary,
            start=start,
            end=end,
            description=description,
            attendee_email=attendee_email,
        )
    except Exception as e:
        logger.error(f"Booking failed for calendar {calendar_id}: {e}")
        raise HTTPException(status_code=502, detail="Kon afspraak niet aanmaken in Google Calendar")

    return {
        "message": "Afspraak ingepland",
        "event_id": event.get("id"),
        "html_link": event.get("htmlLink"),
        "start": event.get("start"),
        "end": event.get("end"),
    }


# ── Hold Slot ─────────────────────────────────────────────


@router.post("/{calendar_id}/hold", response_model=HoldSlotResponse)
async def hold_slot(
    calendar_id: UUID,
    request: HoldSlotRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Temporarily hold a time slot (used during phone calls)."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    hold_id = uuid4()
    expires_at = datetime.utcnow() + timedelta(seconds=request.hold_duration_seconds)

    return HoldSlotResponse(
        hold_id=hold_id,
        slot=request.slot,
        expires_at=expires_at,
    )


# ── Sync ──────────────────────────────────────────────────


@router.post("/{calendar_id}/sync")
async def sync_calendar(
    calendar_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Manually trigger calendar sync — verifies connection is still valid."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)

    if not calendar.access_token_encrypted:
        raise HTTPException(status_code=400, detail="Agenda is nog niet gekoppeld.")

    try:
        access_token = await gcal.get_valid_access_token(calendar, db)
        calendars = await gcal.list_google_calendars(access_token)
        calendar.last_sync_at = datetime.utcnow()
        calendar.sync_error = None
        db.commit()

        return {
            "message": "Synchronisatie gelukt",
            "calendar_id": str(calendar.id),
            "last_sync_at": calendar.last_sync_at.isoformat(),
            "google_calendars_found": len(calendars),
        }
    except Exception as e:
        calendar.sync_error = str(e)
        db.commit()
        logger.error(f"Calendar sync failed: {e}")
        raise HTTPException(status_code=502, detail=f"Synchronisatie mislukt: {e}")


# ── Helpers ───────────────────────────────────────────────


def _get_calendar_or_404(
    calendar_id: UUID, company_id: UUID, db: Session
) -> CalendarIntegration:
    calendar = (
        db.query(CalendarIntegration)
        .filter(
            CalendarIntegration.id == calendar_id,
            CalendarIntegration.company_id == company_id,
        )
        .first()
    )
    if not calendar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agenda-integratie niet gevonden",
        )
    return calendar
