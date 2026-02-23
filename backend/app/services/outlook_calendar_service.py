"""
klantenservice.ai - Microsoft Outlook Calendar Service

Handles OAuth2 flow, token management, and Microsoft Graph Calendar API operations.
Uses the same Azure App Registration as the Teams meeting service but with calendar scopes.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encrypt_value, decrypt_value
from app.models.calendar_integration import CalendarIntegration

logger = logging.getLogger(__name__)
settings = get_settings()

MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_API = "https://graph.microsoft.com/v1.0"

SCOPES = "offline_access Calendars.ReadWrite"

AMS_TZ = ZoneInfo("Europe/Amsterdam")


def get_oauth_redirect_uri() -> str:
    if settings.APP_ENV == "production":
        return "https://api.klantenservice.ai/api/v1/calendars/oauth/microsoft/callback"
    return "http://localhost:8000/api/v1/calendars/oauth/microsoft/callback"


def build_auth_url(state: str) -> str:
    """Build Microsoft OAuth2 authorization URL for Outlook Calendar."""
    params = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "redirect_uri": get_oauth_redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "prompt": "consent",
    }
    return f"{MS_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MS_TOKEN_URL,
            data={
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": get_oauth_redirect_uri(),
                "scope": SCOPES,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired Microsoft access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MS_TOKEN_URL,
            data={
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": SCOPES,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_access_token(calendar: CalendarIntegration, db: Session) -> str:
    """Get a valid access token, refreshing if expired."""
    if not calendar.access_token_encrypted:
        raise ValueError("No access token stored for this calendar")

    if not calendar.is_token_expired:
        return decrypt_value(calendar.access_token_encrypted)

    if not calendar.refresh_token_encrypted:
        raise ValueError("No refresh token — user must re-authorize")

    refresh_token = decrypt_value(calendar.refresh_token_encrypted)
    token_data = await refresh_access_token(refresh_token)

    calendar.access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.token_expires_at = datetime.utcnow() + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.refresh_token_encrypted = encrypt_value(token_data["refresh_token"])

    db.commit()
    logger.info(f"Refreshed Outlook token for calendar {calendar.id}")
    return token_data["access_token"]


def _auth_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


async def list_outlook_calendars(access_token: str) -> list[dict]:
    """List all Outlook calendars the user has access to."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/me/calendars",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        items = resp.json().get("value", [])
        return [
            {
                "id": cal["id"],
                "summary": cal.get("name", ""),
                "primary": cal.get("isDefaultCalendar", False),
                "color": cal.get("hexColor", ""),
            }
            for cal in items
        ]


async def get_events(
    access_token: str,
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
) -> list[dict]:
    """Get events from an Outlook Calendar in a time range using calendarView."""
    fmt = "%Y-%m-%dT%H:%M:%S"
    params = {
        "startDateTime": time_min.strftime(fmt),
        "endDateTime": time_max.strftime(fmt),
        "$top": 250,
        "$select": "subject,start,end,isCancelled,showAs",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API}/me/calendars/{calendar_id}/calendarView",
            headers=_auth_headers(access_token),
            params=params,
        )
        resp.raise_for_status()
        raw_events = resp.json().get("value", [])

    normalized = []
    for ev in raw_events:
        if ev.get("isCancelled"):
            continue
        if ev.get("showAs") == "free":
            continue
        normalized.append({
            "start": {"dateTime": ev["start"]["dateTime"], "timeZone": ev["start"].get("timeZone", "UTC")},
            "end": {"dateTime": ev["end"]["dateTime"], "timeZone": ev["end"].get("timeZone", "UTC")},
        })
    return normalized


async def create_event(
    access_token: str,
    calendar_id: str,
    summary: str,
    start: datetime,
    end: datetime,
    description: str = "",
    attendee_email: str = "",
    timezone: str = "Europe/Amsterdam",
) -> dict:
    """Create a new event in an Outlook Calendar."""
    event_body: dict = {
        "subject": summary,
        "start": {"dateTime": start.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": timezone},
        "end": {"dateTime": end.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": timezone},
    }
    if description:
        event_body["body"] = {"contentType": "Text", "content": description}
    if attendee_email:
        event_body["attendees"] = [
            {
                "emailAddress": {"address": attendee_email},
                "type": "required",
            }
        ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_API}/me/calendars/{calendar_id}/events",
            headers=_auth_headers(access_token),
            json=event_body,
        )
        resp.raise_for_status()
        return resp.json()


async def delete_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
) -> None:
    """Delete an event from an Outlook Calendar."""
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{GRAPH_API}/me/calendars/{calendar_id}/events/{event_id}",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()


async def get_availability_for_range(
    calendar: CalendarIntegration,
    db: Session,
    start_date: datetime,
    end_date: datetime,
    duration_minutes: int = 30,
) -> list[dict]:
    """Get all available slots across a date range for an Outlook calendar."""
    from app.services.google_calendar_service import compute_available_slots

    access_token = await get_valid_access_token(calendar, db)
    cal_id = calendar.external_calendar_id
    if not cal_id:
        raise ValueError("No Outlook calendar selected")

    events = await get_events(access_token, cal_id, start_date, end_date)
    rules = calendar.availability_rules or {}

    all_slots = []
    current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    while current_date <= end:
        day_events = [
            e for e in events
            if e.get("start", {}).get("dateTime", "").startswith(current_date.strftime("%Y-%m-%d"))
        ]
        day_slots = compute_available_slots(day_events, rules, current_date, duration_minutes)
        all_slots.extend(day_slots)
        current_date += timedelta(days=1)

    max_advance = rules.get("max_advance_days", 60)
    cutoff = datetime.now(AMS_TZ).replace(tzinfo=None) + timedelta(days=max_advance)
    all_slots = [s for s in all_slots if datetime.fromisoformat(s["start"]) <= cutoff]

    return all_slots


async def book_appointment(
    calendar: CalendarIntegration,
    db: Session,
    summary: str,
    start: datetime,
    end: datetime,
    description: str = "",
    attendee_email: str = "",
) -> dict:
    """Book an appointment by creating an Outlook Calendar event, optionally with a meeting link."""
    from app.services import zoom_meeting_service as zoom_svc
    from app.services import teams_meeting_service as teams_svc
    from app.services import google_meet_service as gmeet_svc

    provider = getattr(calendar, "meeting_link_provider", "none")
    external_link = None

    if provider == "zoom" and calendar.zoom_access_token_encrypted:
        duration = int((end - start).total_seconds() / 60)
        external_link = await zoom_svc.create_meeting_for_calendar(
            calendar=calendar,
            db=db,
            topic=summary,
            start_time=start,
            duration_minutes=duration,
        )
    elif provider == "teams" and calendar.teams_access_token_encrypted:
        external_link = await teams_svc.create_meeting_for_calendar(
            calendar=calendar,
            db=db,
            subject=summary,
            start_time=start,
            end_time=end,
        )
    elif provider == "google_meet" and calendar.gmeet_access_token_encrypted:
        external_link = await gmeet_svc.create_meeting_for_calendar(
            calendar=calendar,
            db=db,
            summary=summary,
            start=start,
            end=end,
        )

    if external_link:
        labels = {"zoom": "Zoom", "teams": "Microsoft Teams", "google_meet": "Google Meet"}
        label = labels.get(provider, "Meeting")
        description = f"{description}\n\n{label}: {external_link}".strip()

    access_token = await get_valid_access_token(calendar, db)
    cal_id = calendar.external_calendar_id
    if not cal_id:
        raise ValueError("No Outlook calendar selected")

    event = await create_event(
        access_token=access_token,
        calendar_id=cal_id,
        summary=summary,
        start=start,
        end=end,
        description=description,
        attendee_email=attendee_email,
    )

    meeting_link = external_link or ""
    logger.info(f"Booked Outlook appointment: {event.get('id')} on calendar {calendar.id} meeting={meeting_link or 'none'}")

    if external_link:
        event["meeting_link"] = external_link
    return event
