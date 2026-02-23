"""
klantenservice.ai - HubSpot CRM Service

Handles OAuth 2.1 + PKCE flow, token management, contact lookup, and engagement creation.
"""
import base64
import hashlib
import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encrypt_value, decrypt_value
from app.models.crm_integration import CRMIntegration

logger = logging.getLogger(__name__)
settings = get_settings()

HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_API = "https://api.hubapi.com"
SCOPES = "crm.objects.contacts.read crm.objects.contacts.write"


# ── PKCE helpers ─────────────────────────────────────────


def generate_pkce_pair() -> Tuple[str, str]:
    """
    Generate a PKCE code_verifier / code_challenge pair.
    Returns (code_verifier, code_challenge) using S256 method.
    """
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


# ── OAuth helpers ────────────────────────────────────────


def get_oauth_redirect_uri() -> str:
    if settings.APP_ENV == "production":
        return "https://api.klantenservice.ai/api/v1/crm/oauth/hubspot/callback"
    return "http://localhost:8000/api/v1/crm/oauth/hubspot/callback"


def build_auth_url(state: str, code_challenge: str) -> str:
    """Build HubSpot OAuth 2.1 authorization URL with PKCE challenge."""
    params = {
        "client_id": settings.HUBSPOT_CLIENT_ID,
        "redirect_uri": get_oauth_redirect_uri(),
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, code_verifier: str) -> dict:
    """Exchange authorization code for access + refresh tokens (with PKCE verifier)."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.HUBSPOT_CLIENT_ID,
                "client_secret": settings.HUBSPOT_CLIENT_SECRET,
                "redirect_uri": get_oauth_redirect_uri(),
                "code": code,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            HUBSPOT_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": settings.HUBSPOT_CLIENT_ID,
                "client_secret": settings.HUBSPOT_CLIENT_SECRET,
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_access_token(integration: CRMIntegration, db: Session) -> str:
    """Get a valid access token, refreshing if expired."""
    if not integration.access_token_encrypted:
        raise ValueError("No access token stored for this CRM integration")

    if not integration.is_token_expired:
        return decrypt_value(integration.access_token_encrypted)

    if not integration.refresh_token_encrypted:
        raise ValueError("No refresh token — user must re-authorize")

    refresh_token = decrypt_value(integration.refresh_token_encrypted)
    token_data = await refresh_access_token(refresh_token)

    integration.access_token_encrypted = encrypt_value(token_data["access_token"])
    integration.token_expires_at = datetime.utcnow() + timedelta(
        seconds=token_data.get("expires_in", 21600)
    )
    if "refresh_token" in token_data:
        integration.refresh_token_encrypted = encrypt_value(token_data["refresh_token"])

    db.commit()
    logger.info(f"Refreshed HubSpot token for integration {integration.id}")
    return token_data["access_token"]


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def _normalize_phone(phone: str) -> str:
    """Strip a phone number to digits only for comparison."""
    return re.sub(r"[^\d+]", "", phone)


async def search_contact_by_phone(
    access_token: str, phone_number: str
) -> Optional[dict]:
    """
    Search for a contact in HubSpot by phone number.
    Returns contact properties or None if not found.
    """
    normalized = _normalize_phone(phone_number)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/contacts/search",
            headers=_auth_headers(access_token),
            json={
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "phone",
                                "operator": "CONTAINS_TOKEN",
                                "value": normalized[-9:],
                            }
                        ]
                    },
                    {
                        "filters": [
                            {
                                "propertyName": "mobilephone",
                                "operator": "CONTAINS_TOKEN",
                                "value": normalized[-9:],
                            }
                        ]
                    },
                ],
                "properties": [
                    "firstname",
                    "lastname",
                    "email",
                    "phone",
                    "mobilephone",
                    "company",
                    "hs_lead_status",
                    "notes_last_updated",
                ],
                "limit": 1,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                props = results[0].get("properties", {})
                return {
                    "id": results[0]["id"],
                    "first_name": props.get("firstname"),
                    "last_name": props.get("lastname"),
                    "email": props.get("email"),
                    "phone": props.get("phone") or props.get("mobilephone"),
                    "company_name": props.get("company"),
                    "lead_status": props.get("hs_lead_status"),
                }
        else:
            logger.warning(
                f"HubSpot contact search failed ({resp.status_code}): {resp.text}"
            )
    return None


async def create_contact(
    access_token: str,
    phone: str,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
) -> Optional[dict]:
    """Create a new contact in HubSpot."""
    properties = {"phone": phone}
    if first_name:
        properties["firstname"] = first_name
    if last_name:
        properties["lastname"] = last_name
    if email:
        properties["email"] = email

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/contacts",
            headers=_auth_headers(access_token),
            json={"properties": properties},
        )
        if resp.status_code in (200, 201):
            return resp.json()
        logger.warning(
            f"HubSpot create contact failed ({resp.status_code}): {resp.text}"
        )
    return None


async def create_engagement_note(
    access_token: str, contact_id: str, note_body: str
) -> Optional[dict]:
    """Create a note (engagement) linked to a contact."""
    async with httpx.AsyncClient() as client:
        # Create the note
        note_resp = await client.post(
            f"{HUBSPOT_API}/crm/v3/objects/notes",
            headers=_auth_headers(access_token),
            json={
                "properties": {
                    "hs_timestamp": datetime.utcnow().isoformat() + "Z",
                    "hs_note_body": note_body,
                }
            },
        )
        if note_resp.status_code not in (200, 201):
            logger.warning(
                f"HubSpot create note failed ({note_resp.status_code}): {note_resp.text}"
            )
            return None

        note_id = note_resp.json()["id"]

        # Associate note with the contact
        await client.put(
            f"{HUBSPOT_API}/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/202",
            headers=_auth_headers(access_token),
        )

        return note_resp.json()


async def get_account_info(access_token: str) -> Optional[dict]:
    """Get basic HubSpot account info to verify connection."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{HUBSPOT_API}/oauth/v1/access-tokens/{access_token}",
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "portal_id": str(data.get("hub_id", "")),
                "user": data.get("user"),
                "hub_domain": data.get("hub_domain"),
            }
    return None
