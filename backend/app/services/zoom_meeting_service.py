"""
klantenservice.ai - Zoom Meeting Service

Handles Zoom OAuth2 flow, token management, and meeting creation.
Used by the calendar integration to auto-generate Zoom meeting links.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encrypt_value, decrypt_value
from app.models.calendar_integration import CalendarIntegration

logger = logging.getLogger(__name__)
settings = get_settings()

ZOOM_AUTH_URL = "https://zoom.us/oauth/authorize"
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_API_BASE = "https://api.zoom.us/v2"


def get_oauth_redirect_uri() -> str:
    if settings.APP_ENV == "production":
        return "https://api.klantenservice.ai/api/v1/calendars/oauth/zoom/callback"
    return "http://localhost:8000/api/v1/calendars/oauth/zoom/callback"


def build_auth_url(state: str) -> str:
    """Build Zoom OAuth2 authorization URL."""
    params = {
        "client_id": settings.ZOOM_CLIENT_ID,
        "redirect_uri": get_oauth_redirect_uri(),
        "response_type": "code",
        "state": state,
    }
    return f"{ZOOM_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens using Basic auth."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ZOOM_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": get_oauth_redirect_uri(),
            },
            auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired Zoom access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            ZOOM_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(settings.ZOOM_CLIENT_ID, settings.ZOOM_CLIENT_SECRET),
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_zoom_token(calendar: CalendarIntegration, db: Session) -> str:
    """Get a valid Zoom access token, refreshing if expired."""
    if not calendar.zoom_access_token_encrypted:
        raise ValueError("No Zoom access token stored for this calendar")

    now = datetime.utcnow()
    if calendar.zoom_token_expires_at and now < calendar.zoom_token_expires_at:
        return decrypt_value(calendar.zoom_access_token_encrypted)

    if not calendar.zoom_refresh_token_encrypted:
        raise ValueError("No Zoom refresh token — user must re-authorize")

    refresh_token = decrypt_value(calendar.zoom_refresh_token_encrypted)
    token_data = await refresh_access_token(refresh_token)

    calendar.zoom_access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.zoom_token_expires_at = now + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.zoom_refresh_token_encrypted = encrypt_value(token_data["refresh_token"])

    db.commit()
    logger.info(f"Refreshed Zoom token for calendar {calendar.id}")
    return token_data["access_token"]


def store_zoom_tokens(calendar: CalendarIntegration, token_data: dict, db: Session) -> None:
    """Store Zoom OAuth tokens on the calendar integration."""
    calendar.zoom_access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.zoom_token_expires_at = datetime.utcnow() + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.zoom_refresh_token_encrypted = encrypt_value(token_data["refresh_token"])
    db.commit()


async def create_meeting(
    access_token: str,
    topic: str,
    start_time: datetime,
    duration_minutes: int = 30,
    timezone: str = "Europe/Amsterdam",
) -> dict:
    """
    Create a Zoom meeting and return meeting details including join_url.
    Uses Zoom API v2 POST /users/me/meetings.
    """
    body = {
        "topic": topic,
        "type": 2,  # scheduled meeting
        "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration": duration_minutes,
        "timezone": timezone,
        "settings": {
            "join_before_host": True,
            "waiting_room": False,
            "auto_recording": "none",
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{ZOOM_API_BASE}/users/me/meetings",
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


async def create_meeting_for_calendar(
    calendar: CalendarIntegration,
    db: Session,
    topic: str,
    start_time: datetime,
    duration_minutes: int = 30,
) -> Optional[str]:
    """
    Create a Zoom meeting for a calendar integration.
    Returns the join_url or None on failure.
    """
    try:
        access_token = await get_valid_zoom_token(calendar, db)
        meeting = await create_meeting(
            access_token=access_token,
            topic=topic,
            start_time=start_time,
            duration_minutes=duration_minutes,
        )
        join_url = meeting.get("join_url", "")
        logger.info(f"Created Zoom meeting for calendar {calendar.id}: {join_url}")
        return join_url
    except Exception as e:
        logger.error(f"Failed to create Zoom meeting for calendar {calendar.id}: {e}")
        return None
