"""
klantenservice.ai - Microsoft Teams Meeting Service

Handles Microsoft OAuth2 flow, token management, and Teams online meeting creation.
Uses Microsoft Graph API to auto-generate Teams meeting links for appointments.
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

MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

SCOPES = "offline_access OnlineMeetings.ReadWrite"


def get_oauth_redirect_uri() -> str:
    if settings.APP_ENV == "production":
        return "https://api.klantenservice.ai/api/v1/calendars/oauth/teams/callback"
    return "http://localhost:8000/api/v1/calendars/oauth/teams/callback"


def build_auth_url(state: str) -> str:
    """Build Microsoft OAuth2 authorization URL for Teams OnlineMeetings."""
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


async def get_valid_teams_token(calendar: CalendarIntegration, db: Session) -> str:
    """Get a valid Microsoft access token, refreshing if expired."""
    if not calendar.teams_access_token_encrypted:
        raise ValueError("No Teams access token stored for this calendar")

    now = datetime.utcnow()
    if calendar.teams_token_expires_at and now < calendar.teams_token_expires_at:
        return decrypt_value(calendar.teams_access_token_encrypted)

    if not calendar.teams_refresh_token_encrypted:
        raise ValueError("No Teams refresh token — user must re-authorize")

    refresh_token = decrypt_value(calendar.teams_refresh_token_encrypted)
    token_data = await refresh_access_token(refresh_token)

    calendar.teams_access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.teams_token_expires_at = now + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.teams_refresh_token_encrypted = encrypt_value(token_data["refresh_token"])

    db.commit()
    logger.info(f"Refreshed Teams token for calendar {calendar.id}")
    return token_data["access_token"]


def store_teams_tokens(calendar: CalendarIntegration, token_data: dict, db: Session) -> None:
    """Store Microsoft OAuth tokens on the calendar integration."""
    calendar.teams_access_token_encrypted = encrypt_value(token_data["access_token"])
    calendar.teams_token_expires_at = datetime.utcnow() + timedelta(
        seconds=token_data.get("expires_in", 3600)
    )
    if "refresh_token" in token_data:
        calendar.teams_refresh_token_encrypted = encrypt_value(token_data["refresh_token"])
    db.commit()


async def create_meeting(
    access_token: str,
    subject: str,
    start_time: datetime,
    end_time: datetime,
    timezone: str = "Europe/Amsterdam",
) -> dict:
    """
    Create a Microsoft Teams online meeting via Graph API.
    POST /me/onlineMeetings
    """
    body = {
        "subject": subject,
        "startDateTime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "endDateTime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "lobbyBypassSettings": {
            "scope": "everyone",
            "isDialInBypassEnabled": True,
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_API_BASE}/me/onlineMeetings",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


async def create_meeting_for_calendar(
    calendar: CalendarIntegration,
    db: Session,
    subject: str,
    start_time: datetime,
    end_time: datetime,
) -> Optional[str]:
    """
    Create a Teams meeting for a calendar integration.
    Returns the joinWebUrl or None on failure.
    """
    try:
        access_token = await get_valid_teams_token(calendar, db)
        meeting = await create_meeting(
            access_token=access_token,
            subject=subject,
            start_time=start_time,
            end_time=end_time,
        )
        join_url = meeting.get("joinWebUrl", "")
        logger.info(f"Created Teams meeting for calendar {calendar.id}: {join_url}")
        return join_url
    except Exception as e:
        logger.error(f"Failed to create Teams meeting for calendar {calendar.id}: {e}")
        return None
