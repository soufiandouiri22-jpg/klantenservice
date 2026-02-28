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
from app.api.deps import get_current_user, get_current_company, require_admin, require_manager
from app.services import google_calendar_service as gcal
from app.services import outlook_calendar_service as outlook
from app.services import zoom_meeting_service as zoom_svc
from app.services import teams_meeting_service as teams_svc
from app.services import google_meet_service as gmeet_svc

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


# ── OAuth Flow (specific routes MUST come before /{provider} catch-all) ──


@router.get("/oauth/zoom/url")
async def get_zoom_oauth_url(
    calendar_id: UUID = Query(..., description="Calendar integration ID"),
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get Zoom OAuth URL so the user can connect their Zoom account for meeting links."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    state = json.dumps({"calendar_id": str(calendar.id), "company_id": str(company.id)})
    auth_url = zoom_svc.build_auth_url(state)
    return {"auth_url": auth_url}


@router.get("/oauth/teams/url")
async def get_teams_oauth_url(
    calendar_id: UUID = Query(..., description="Calendar integration ID"),
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get Microsoft Teams OAuth URL so the user can connect their Teams account."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    state = json.dumps({"calendar_id": str(calendar.id), "company_id": str(company.id)})
    auth_url = teams_svc.build_auth_url(state)
    return {"auth_url": auth_url}


@router.get("/oauth/gmeet/url")
async def get_gmeet_oauth_url(
    calendar_id: UUID = Query(..., description="Calendar integration ID"),
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get Google OAuth URL for standalone Google Meet (non-Google calendar providers)."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    state = json.dumps({"calendar_id": str(calendar.id), "company_id": str(company.id)})
    auth_url = gmeet_svc.build_auth_url(state)
    return {"auth_url": auth_url}


@router.get("/oauth/{provider}/url")
async def get_oauth_url(
    provider: CalendarProvider,
    calendar_id: UUID = Query(..., description="Calendar integration ID to connect"),
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get OAuth authorization URL for calendar providers (Google, Microsoft)."""
    if provider == CalendarProvider.CALDAV:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CalDAV gebruikt geen OAuth",
        )

    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    state = json.dumps({"calendar_id": str(calendar.id), "company_id": str(company.id)})

    if provider == CalendarProvider.GOOGLE:
        auth_url = gcal.build_auth_url(state)
    elif provider == CalendarProvider.MICROSOFT:
        auth_url = outlook.build_auth_url(state)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onbekende provider",
        )

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


@router.get("/oauth/microsoft/callback")
async def microsoft_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Microsoft OAuth callback. Microsoft redirects here after user consent.
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
        token_data = await outlook.exchange_code_for_tokens(code)
    except Exception as e:
        logger.error(f"Microsoft token exchange failed: {e}")
        raise HTTPException(status_code=400, detail="Kon geen toegang krijgen tot Microsoft Outlook")

    calendar.access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.token_expires_at = datetime.utcnow() + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.refresh_token_encrypted = encrypt_value(token_data["refresh_token"])

    try:
        access_token = token_data["access_token"]
        calendars = await outlook.list_outlook_calendars(access_token)
        primary = next((c for c in calendars if c["primary"]), calendars[0] if calendars else None)
        if primary:
            calendar.external_calendar_id = primary["id"]
            calendar.external_calendar_name = primary["summary"]
    except Exception as e:
        logger.warning(f"Could not fetch Outlook calendar list: {e}")

    calendar.last_sync_at = datetime.utcnow()
    calendar.sync_error = None
    calendar.is_active = True
    db.commit()

    logger.info(f"Microsoft Outlook connected for integration {calendar.id}")

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(
        url=f"{frontend_url}/dashboard/calendar?microsoft_connected=true&calendar_id={calendar.id}"
    )


# ── Zoom Meeting Provider OAuth ──────────────────────────


@router.get("/oauth/zoom/callback")
async def zoom_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Zoom OAuth callback — exchanges code for tokens and stores them."""
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
        token_data = await zoom_svc.exchange_code_for_tokens(code)
    except Exception as e:
        logger.error(f"Zoom token exchange failed: {e}")
        raise HTTPException(status_code=400, detail="Kon geen toegang krijgen tot Zoom")

    zoom_svc.store_zoom_tokens(calendar, token_data, db)
    calendar.meeting_link_provider = "zoom"
    db.commit()

    logger.info(f"Zoom connected for calendar {calendar.id}")

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(
        url=f"{frontend_url}/dashboard/calendar?zoom_connected=true&calendar_id={calendar.id}"
    )


@router.delete("/{calendar_id}/zoom")
async def disconnect_zoom(
    calendar_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Disconnect Zoom from a calendar integration."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    calendar.zoom_access_token_encrypted = None
    calendar.zoom_refresh_token_encrypted = None
    calendar.zoom_token_expires_at = None
    if calendar.meeting_link_provider == "zoom":
        calendar.meeting_link_provider = "none"
    db.commit()
    return {"message": "Zoom ontkoppeld"}


# ── Microsoft Teams Meeting Provider OAuth ───────────────


@router.get("/oauth/teams/callback")
async def teams_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Microsoft Teams OAuth callback — exchanges code for tokens and stores them."""
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
        token_data = await teams_svc.exchange_code_for_tokens(code)
    except Exception as e:
        logger.error(f"Teams token exchange failed: {e}")
        raise HTTPException(status_code=400, detail="Kon geen toegang krijgen tot Microsoft Teams")

    teams_svc.store_teams_tokens(calendar, token_data, db)
    calendar.meeting_link_provider = "teams"
    db.commit()

    logger.info(f"Teams connected for calendar {calendar.id}")

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(
        url=f"{frontend_url}/dashboard/calendar?teams_connected=true&calendar_id={calendar.id}"
    )


@router.delete("/{calendar_id}/teams")
async def disconnect_teams(
    calendar_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Disconnect Microsoft Teams from a calendar integration."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    calendar.teams_access_token_encrypted = None
    calendar.teams_refresh_token_encrypted = None
    calendar.teams_token_expires_at = None
    if calendar.meeting_link_provider == "teams":
        calendar.meeting_link_provider = "none"
    db.commit()
    return {"message": "Microsoft Teams ontkoppeld"}


# ── Standalone Google Meet OAuth ─────────────────────────


@router.get("/oauth/gmeet/callback")
async def gmeet_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Google Meet standalone OAuth callback — for non-Google calendar providers."""
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
        token_data = await gmeet_svc.exchange_code_for_tokens(code)
    except Exception as e:
        logger.error(f"Google Meet token exchange failed: {e}")
        raise HTTPException(status_code=400, detail="Kon geen toegang krijgen tot Google Meet")

    gmeet_svc.store_gmeet_tokens(calendar, token_data, db)
    calendar.meeting_link_provider = "google_meet"
    db.commit()

    logger.info(f"Google Meet (standalone) connected for calendar {calendar.id}")

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(
        url=f"{frontend_url}/dashboard/calendar?gmeet_connected=true&calendar_id={calendar.id}"
    )


@router.delete("/{calendar_id}/gmeet")
async def disconnect_gmeet(
    calendar_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Disconnect standalone Google Meet from a calendar integration."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    calendar.gmeet_access_token_encrypted = None
    calendar.gmeet_refresh_token_encrypted = None
    calendar.gmeet_token_expires_at = None
    if calendar.meeting_link_provider == "google_meet":
        calendar.meeting_link_provider = "none"
    db.commit()
    return {"message": "Google Meet ontkoppeld"}


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

    has_existing = (
        db.query(CalendarIntegration)
        .filter(CalendarIntegration.company_id == company.id)
        .first()
    )

    calendar = CalendarIntegration(
        id=uuid4(),
        company_id=company.id,
        ai_worker_id=data.ai_worker_id,
        name=data.name,
        provider=data.provider,
        is_active=True,
        is_primary=not has_existing,
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


# ── Calendar List (from provider) ─────────────────────────


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


@router.get("/{calendar_id}/microsoft-calendars")
async def list_microsoft_calendars_endpoint(
    calendar_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all Outlook calendars the user has access to (after OAuth)."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)
    access_token = await outlook.get_valid_access_token(calendar, db)
    calendars = await outlook.list_outlook_calendars(access_token)
    return {"calendars": calendars}


@router.patch("/{calendar_id}/select-calendar")
async def select_calendar(
    calendar_id: UUID,
    external_calendar_id: str = Query(..., description="Calendar ID to use"),
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Select which calendar to use for this integration (Google or Microsoft)."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)

    if calendar.provider == CalendarProvider.MICROSOFT:
        access_token = await outlook.get_valid_access_token(calendar, db)
        calendars = await outlook.list_outlook_calendars(access_token)
    else:
        access_token = await gcal.get_valid_access_token(calendar, db)
        calendars = await gcal.list_google_calendars(access_token)

    selected = next((c for c in calendars if c["id"] == external_calendar_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Agenda niet gevonden")

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
    """Get available time slots from the connected calendar."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)

    if not calendar.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agenda is nog niet gekoppeld. Doorloop eerst de OAuth-stap.",
        )

    try:
        svc = outlook if calendar.provider == CalendarProvider.MICROSOFT else gcal
        slots_raw = await svc.get_availability_for_range(
            calendar=calendar,
            db=db,
            start_date=request.start_date,
            end_date=request.end_date,
            duration_minutes=request.duration_minutes,
        )
    except Exception as e:
        logger.error(f"Availability check failed for calendar {calendar_id}: {e}")
        raise HTTPException(status_code=502, detail="Kon beschikbaarheid niet ophalen")

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
    current_user: User = Depends(require_manager),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Book an appointment in the connected calendar."""
    calendar = _get_calendar_or_404(calendar_id, company.id, db)

    if not calendar.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agenda is nog niet gekoppeld.",
        )

    try:
        svc = outlook if calendar.provider == CalendarProvider.MICROSOFT else gcal
        event = await svc.book_appointment(
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
        raise HTTPException(status_code=502, detail="Kon afspraak niet aanmaken")

    if calendar.provider == CalendarProvider.MICROSOFT:
        return {
            "message": "Afspraak ingepland",
            "event_id": event.get("id"),
            "html_link": event.get("webLink"),
            "meet_link": event.get("meeting_link") or None,
            "start": event.get("start"),
            "end": event.get("end"),
        }

    return {
        "message": "Afspraak ingepland",
        "event_id": event.get("id"),
        "html_link": event.get("htmlLink"),
        "meet_link": event.get("hangoutLink") or event.get("meeting_link") or None,
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
        if calendar.provider == CalendarProvider.MICROSOFT:
            access_token = await outlook.get_valid_access_token(calendar, db)
            calendars = await outlook.list_outlook_calendars(access_token)
        else:
            access_token = await gcal.get_valid_access_token(calendar, db)
            calendars = await gcal.list_google_calendars(access_token)

        calendar.last_sync_at = datetime.utcnow()
        calendar.sync_error = None
        db.commit()

        return {
            "message": "Synchronisatie gelukt",
            "calendar_id": str(calendar.id),
            "last_sync_at": calendar.last_sync_at.isoformat(),
            "calendars_found": len(calendars),
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
