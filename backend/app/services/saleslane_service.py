"""
klantenservice.ai - Saleslane CRM Service

JWT RS256-signed authentication. Contact lookup by phone and transaction tagging.
API docs: https://docs.saleslane.nl/
"""
import logging
import re
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import httpx
from jose import jwt

from app.core.security import decrypt_value
from app.models.crm_integration import CRMIntegration

logger = logging.getLogger(__name__)

SALESLANE_DOMAIN_SUFFIX = "saleslane.nl"
API_VERSION = "v1"


def _build_base_url(client_prefix: str) -> str:
    return f"https://{client_prefix}.{SALESLANE_DOMAIN_SUFFIX}/api/{API_VERSION}"


def _normalize_phone(phone: str) -> str:
    """Normalize phone to E.164 for Saleslane (expects +31...)."""
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("06") and len(digits) == 10:
        digits = "+31" + digits[1:]
    elif digits.startswith("316") and not digits.startswith("+"):
        digits = "+" + digits
    elif digits.startswith("0031"):
        digits = "+" + digits[2:]
    return digits


def _sign_payload(private_key_pem: str, api_context_id: str, data: dict) -> str:
    """Sign request data as an RS256 JWT for Saleslane API authentication."""
    now = datetime.now(timezone.utc)
    payload = {
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "sub": api_context_id,
        "jti": str(_uuid.uuid4()),
        "data": data,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def get_valid_credentials(
    integration: CRMIntegration, db
) -> Tuple[str, str, str]:
    """
    Decrypt stored RSA private key and return (private_key_pem, api_context_id, client_prefix).
    Raises ValueError if credentials are missing.
    """
    if not integration.api_key_encrypted:
        raise ValueError("Geen RSA private key opgeslagen voor deze Saleslane integratie")
    if not integration.api_context_id:
        raise ValueError("Geen API Context ID geconfigureerd voor deze Saleslane integratie")
    if not integration.account_domain:
        raise ValueError("Geen client prefix geconfigureerd voor deze Saleslane integratie")

    private_key = decrypt_value(integration.api_key_encrypted)
    return private_key, integration.api_context_id, integration.account_domain


async def search_contact_by_phone(
    private_key: str, api_context_id: str, client_prefix: str, phone_number: str
) -> Optional[dict]:
    """
    Look up a contact by phone number via GET /contact/by-phone.
    Returns a normalized caller_context dict or None.
    """
    normalized = _normalize_phone(phone_number)
    signed_token = _sign_payload(private_key, api_context_id, {"phoneNumber": normalized})
    url = f"{_build_base_url(client_prefix)}/contact/by-phone"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params={"signed": signed_token})

        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            logger.warning(
                f"Saleslane contact lookup failed ({resp.status_code}): {resp.text[:300]}"
            )
            return None

        body = resp.json()
        results = body.get("data", [])
        if not results:
            return None

        first = results[0]
        contact = first.get("contact", {})
        transactions = first.get("transactions", [])

        latest_tags = []
        for txn in transactions:
            for sub in txn.get("subtransactions", []):
                for tag in sub.get("tags", []):
                    if tag.get("isPrimaryStatus"):
                        latest_tags.append(tag.get("tag", ""))

        return {
            "id": contact.get("_id", ""),
            "first_name": None,
            "last_name": None,
            "email": None,
            "phone": normalized,
            "company_name": None,
            "saleslane_transactions": [
                {
                    "reference_id": t.get("referenceId"),
                    "status_tags": latest_tags,
                }
                for t in transactions
            ],
        }


async def tag_transaction(
    private_key: str,
    api_context_id: str,
    client_prefix: str,
    reference_id: str,
    tag: str,
    description: str = "",
    color: str = "",
    label_type: str = "info",
) -> Optional[dict]:
    """
    Add a tag to a transaction subtransaction via POST /transaction/transaction-tag.
    Returns the API response data or None on failure.
    """
    payload: dict = {"referenceId": reference_id, "tag": tag}
    if description:
        payload["description"] = description
    if color:
        payload["color"] = color
    if label_type:
        payload["labelType"] = label_type
    payload["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    signed_token = _sign_payload(private_key, api_context_id, payload)
    url = f"{_build_base_url(client_prefix)}/transaction/transaction-tag"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            content=f'"{signed_token}"',
        )
        if resp.status_code in (200, 201):
            return resp.json().get("data")
        logger.warning(
            f"Saleslane tag_transaction failed ({resp.status_code}): {resp.text[:300]}"
        )
    return None


async def test_connection(
    private_key: str, api_context_id: str, client_prefix: str
) -> dict:
    """
    Test the Saleslane connection by calling GET /api/me.
    Returns identity info on success, raises on failure.
    """
    signed_token = _sign_payload(private_key, api_context_id, {})
    url = f"{_build_base_url(client_prefix)}/api/me"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params={"signed": signed_token})

        if resp.status_code == 401:
            raise ValueError("Ongeldige credentials — controleer de private key en API Context ID")
        if resp.status_code == 400:
            raise ValueError("Ongeldig verzoek — controleer de private key en API Context ID")
        if resp.status_code != 200:
            raise ValueError(f"Saleslane API fout (HTTP {resp.status_code})")

        data = resp.json().get("data", {})
        return {
            "prefix": client_prefix,
            "title": data.get("title", ""),
            "message": "Verbinding succesvol",
        }
