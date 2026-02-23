"""
klantenservice.ai - Google Calendar Service

Handles OAuth2 flow, token management, and Google Calendar API operations.
Used by the calendar endpoints and the AI voice agent's scheduling tools.
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

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
SCOPES = "https://www.googleapis.com/auth/calendar"

AMS_TZ = ZoneInfo("Europe/Amsterdam")


def get_oauth_redirect_uri() -> str:
    if settings.APP_ENV == "production":
        return "https://api.klantenservice.ai/api/v1/calendars/oauth/google/callback"
    return "http://localhost:8000/api/v1/calendars/oauth/google/callback"


def build_auth_url(state: str) -> str:
    """Build Google OAuth2 authorization URL."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": get_oauth_redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": get_oauth_redirect_uri(),
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
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
    logger.info(f"Refreshed Google token for calendar {calendar.id}")
    return token_data["access_token"]


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def list_google_calendars(access_token: str) -> list[dict]:
    """List all calendars the user has access to."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GOOGLE_CALENDAR_API}/users/me/calendarList",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [
            {
                "id": cal["id"],
                "summary": cal.get("summary", ""),
                "primary": cal.get("primary", False),
                "backgroundColor": cal.get("backgroundColor", ""),
            }
            for cal in items
        ]


async def get_events(
    access_token: str,
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
) -> list[dict]:
    """Get events from a Google Calendar in a time range."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events",
            headers=_auth_headers(access_token),
            params={
                "timeMin": time_min.isoformat() + "Z" if time_min.tzinfo is None else time_min.isoformat(),
                "timeMax": time_max.isoformat() + "Z" if time_max.tzinfo is None else time_max.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 250,
            },
        )
        resp.raise_for_status()
        return resp.json().get("items", [])


async def create_event(
    access_token: str,
    calendar_id: str,
    summary: str,
    start: datetime,
    end: datetime,
    description: str = "",
    attendee_email: str = "",
    timezone: str = "Europe/Amsterdam",
    add_google_meet: bool = False,
) -> dict:
    """Create a new event in a Google Calendar, optionally with a Google Meet link."""
    import uuid as _uuid

    event_body: dict = {
        "summary": summary,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
    }
    if description:
        event_body["description"] = description
    if attendee_email:
        event_body["attendees"] = [{"email": attendee_email}]
    if add_google_meet:
        event_body["conferenceData"] = {
            "createRequest": {
                "requestId": str(_uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    params = {}
    if add_google_meet:
        params["conferenceDataVersion"] = "1"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events",
            headers=_auth_headers(access_token),
            json=event_body,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


async def delete_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
) -> None:
    """Delete/cancel an event from a Google Calendar."""
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events/{event_id}",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()


def compute_available_slots(
    events: list[dict],
    availability_rules: dict,
    date: datetime,
    duration_minutes: int,
) -> list[dict]:
    """
    Compute available time slots for a given date based on existing events
    and the calendar's availability rules.
    """
    day_name = date.strftime("%A").lower()
    hours = availability_rules.get("available_hours", {}).get(day_name, {})
    if not hours or not hours.get("enabled", False):
        return []

    start_str = hours.get("start", "09:00")
    end_str = hours.get("end", "17:00")
    sh, sm = map(int, start_str.split(":"))
    eh, em = map(int, end_str.split(":"))

    day_start = date.replace(hour=sh, minute=sm, second=0, microsecond=0)
    day_end = date.replace(hour=eh, minute=em, second=0, microsecond=0)

    buffer_before = availability_rules.get("buffer_before_minutes", 0)
    buffer_after = availability_rules.get("buffer_after_minutes", 15)
    slot_duration = timedelta(minutes=duration_minutes)

    busy_ranges = []
    for ev in events:
        ev_start_str = ev.get("start", {}).get("dateTime")
        ev_end_str = ev.get("end", {}).get("dateTime")
        if not ev_start_str or not ev_end_str:
            continue
        ev_start = datetime.fromisoformat(ev_start_str)
        ev_end = datetime.fromisoformat(ev_end_str)
        if ev_start.tzinfo:
            ev_start = ev_start.astimezone(AMS_TZ).replace(tzinfo=None)
        if ev_end.tzinfo:
            ev_end = ev_end.astimezone(AMS_TZ).replace(tzinfo=None)
        busy_ranges.append((
            ev_start - timedelta(minutes=buffer_before),
            ev_end + timedelta(minutes=buffer_after),
        ))
    busy_ranges.sort()

    break_times = availability_rules.get("break_times", [])
    for bt in break_times:
        bh1, bm1 = map(int, bt["start"].split(":"))
        bh2, bm2 = map(int, bt["end"].split(":"))
        busy_ranges.append((
            date.replace(hour=bh1, minute=bm1, second=0, microsecond=0),
            date.replace(hour=bh2, minute=bm2, second=0, microsecond=0),
        ))
    busy_ranges.sort()

    min_notice = availability_rules.get("min_notice_hours", 1)
    now = datetime.now(AMS_TZ).replace(tzinfo=None)
    earliest = now + timedelta(hours=min_notice)

    slots = []
    current = day_start
    while current + slot_duration <= day_end:
        slot_end = current + slot_duration
        if current >= earliest:
            conflict = False
            for busy_start, busy_end in busy_ranges:
                if current < busy_end and slot_end > busy_start:
                    conflict = True
                    break
            if not conflict:
                slots.append({
                    "start": current.isoformat(),
                    "end": slot_end.isoformat(),
                    "duration_minutes": duration_minutes,
                })
        current += timedelta(minutes=availability_rules.get("slot_duration_minutes", 30))

    return slots


async def get_availability_for_range(
    calendar: CalendarIntegration,
    db: Session,
    start_date: datetime,
    end_date: datetime,
    duration_minutes: int = 30,
) -> list[dict]:
    """Get all available slots across a date range for a calendar."""
    access_token = await get_valid_access_token(calendar, db)
    cal_id = calendar.external_calendar_id or "primary"
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
    """Book an appointment by creating a Google Calendar event."""
    access_token = await get_valid_access_token(calendar, db)
    cal_id = calendar.external_calendar_id or "primary"
    add_meet = getattr(calendar, "meeting_link_provider", "none") == "google_meet"
    event = await create_event(
        access_token=access_token,
        calendar_id=cal_id,
        summary=summary,
        start=start,
        end=end,
        description=description,
        attendee_email=attendee_email,
        add_google_meet=add_meet,
    )
    meet_link = event.get("hangoutLink", "")
    logger.info(f"Booked appointment: {event.get('id')} on calendar {calendar.id} meet={meet_link or 'none'}")
    return event
