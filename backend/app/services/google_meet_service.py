"""
klantenservice.ai - Standalone Google Meet Service

Handles Google OAuth2 for Meet-only usage (when the calendar provider is NOT Google).
Creates a temporary Google Calendar event with conferenceData to obtain a Meet link,
then returns the link for embedding in the actual calendar event (Outlook, CalDAV, etc.).
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode
import uuid as _uuid

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
SCOPES = "https://www.googleapis.com/auth/calendar.events"


def get_oauth_redirect_uri() -> str:
    if settings.APP_ENV == "production":
        return "https://api.klantenservice.ai/api/v1/calendars/oauth/gmeet/callback"
    return "http://localhost:8000/api/v1/calendars/oauth/gmeet/callback"


def build_auth_url(state: str) -> str:
    """Build Google OAuth2 authorization URL for standalone Meet usage."""
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


async def get_valid_gmeet_token(calendar: CalendarIntegration, db: Session) -> str:
    """Get a valid Google access token for Meet, refreshing if expired."""
    if not calendar.gmeet_access_token_encrypted:
        raise ValueError("No Google Meet access token stored")

    now = datetime.utcnow()
    if calendar.gmeet_token_expires_at and now < calendar.gmeet_token_expires_at:
        return decrypt_value(calendar.gmeet_access_token_encrypted)

    if not calendar.gmeet_refresh_token_encrypted:
        raise ValueError("No Google Meet refresh token — user must re-authorize")

    refresh_token = decrypt_value(calendar.gmeet_refresh_token_encrypted)
    token_data = await refresh_access_token(refresh_token)

    calendar.gmeet_access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.gmeet_token_expires_at = now + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.gmeet_refresh_token_encrypted = encrypt_value(token_data["refresh_token"])

    db.commit()
    logger.info(f"Refreshed Google Meet token for calendar {calendar.id}")
    return token_data["access_token"]


def store_gmeet_tokens(calendar: CalendarIntegration, token_data: dict, db: Session) -> None:
    calendar.gmeet_access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.gmeet_token_expires_at = datetime.utcnow() + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.gmeet_refresh_token_encrypted = encrypt_value(token_data["refresh_token"])
    db.commit()


async def create_meet_link(
    access_token: str,
    summary: str,
    start: datetime,
    end: datetime,
    timezone: str = "Europe/Amsterdam",
) -> Optional[str]:
    """
    Create a Google Calendar event with conferenceData to get a Meet link.
    The event is created on the user's primary Google Calendar.
    """
    event_body = {
        "summary": summary,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
        "conferenceData": {
            "createRequest": {
                "requestId": str(_uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "transparency": "transparent",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            json=event_body,
            params={"conferenceDataVersion": "1"},
        )
        resp.raise_for_status()
        data = resp.json()

        meet_link = data.get("hangoutLink", "")

        event_id = data.get("id")
        if event_id:
            await client.delete(
                f"{GOOGLE_CALENDAR_API}/calendars/primary/events/{event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        return meet_link or None


async def create_meeting_for_calendar(
    calendar: CalendarIntegration,
    db: Session,
    summary: str,
    start: datetime,
    end: datetime,
) -> Optional[str]:
    """Create a standalone Google Meet link for a non-Google calendar."""
    try:
        access_token = await get_valid_gmeet_token(calendar, db)
        meet_link = await create_meet_link(
            access_token=access_token,
            summary=summary,
            start=start,
            end=end,
        )
        logger.info(f"Created standalone Google Meet for calendar {calendar.id}: {meet_link}")
        return meet_link
    except Exception as e:
        logger.error(f"Failed to create Google Meet for calendar {calendar.id}: {e}")
        return None
