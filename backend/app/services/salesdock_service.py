"""
klantenservice.ai - Salesdock CRM Service

Handles API-key-based auth, relation lookup by phone, and task creation (call notes).
Salesdock API docs: https://developer.salesdock.nl/
"""
import logging
import re
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_value
from app.models.crm_integration import CRMIntegration

logger = logging.getLogger(__name__)

SALESDOCK_BASE = "https://app.salesdock.nl"
API_VERSION = "v1"
SCOPE_ACCOUNT = "account"


def _build_url(domain: str, path: str, scope: str = SCOPE_ACCOUNT) -> str:
    return f"{SALESDOCK_BASE}/api/{domain}/{API_VERSION}/{scope}/{path}"


def _auth_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }


def _normalize_phone(phone: str) -> str:
    """Strip a phone number to digits and + only for comparison."""
    return re.sub(r"[^\d+]", "", phone)


def get_valid_credentials(integration: CRMIntegration, db: Session) -> Tuple[str, str]:
    """
    Decrypt the stored API key and return (api_key, account_domain).
    Raises ValueError if credentials are missing.
    """
    if not integration.api_key_encrypted:
        raise ValueError("No API key stored for this Salesdock integration")
    if not integration.account_domain:
        raise ValueError("No account domain configured for this Salesdock integration")
    api_key = decrypt_value(integration.api_key_encrypted)
    return api_key, integration.account_domain


async def search_relation_by_phone(
    api_key: str, domain: str, phone_number: str
) -> Optional[dict]:
    """
    Search Salesdock relations by phone number using the ?q= parameter.
    Returns a normalized contact dict or None.
    """
    normalized = _normalize_phone(phone_number)
    search_term = normalized[-9:]

    url = _build_url(domain, "relations")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            url,
            headers=_auth_headers(api_key),
            params={"q": search_term},
        )
        if resp.status_code != 200:
            logger.warning(f"Salesdock relation search failed ({resp.status_code}): {resp.text[:300]}")
            return None

        data = resp.json()
        if not data.get("success"):
            return None

        payload = data.get("data", {})
        relations = payload.get("data", []) if isinstance(payload, dict) else payload
        if not isinstance(relations, list):
            return None

        for relation in relations:
            rel_phone = _normalize_phone(relation.get("phone") or "")
            rel_email = relation.get("email") or ""
            if rel_phone and rel_phone[-9:] == search_term:
                customer = relation.get("customer", {})
                firstname = customer.get("firstname") if customer else relation.get("firstname")
                lastname = customer.get("lastname") if customer else relation.get("lastname")
                email = customer.get("email") if customer else rel_email
                company_name = customer.get("company_name") if customer else relation.get("company_name")

                return {
                    "id": str(relation["id"]),
                    "first_name": firstname,
                    "last_name": lastname,
                    "email": email,
                    "phone": relation.get("phone"),
                    "company_name": company_name,
                }

    return None


async def get_relation(api_key: str, domain: str, relation_id: str) -> Optional[dict]:
    """Fetch a single relation by ID."""
    url = _build_url(domain, f"relations/{relation_id}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=_auth_headers(api_key))
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                return data.get("data")
    return None


async def create_relation(
    api_key: str,
    domain: str,
    phone: str,
    firstname: str = "",
    lastname: str = "",
    email: str = "",
    visibility: str = "account",
) -> Optional[int]:
    """Create a new relation in Salesdock. Returns the relation_id or None."""
    url = _build_url(domain, "relations")
    body: dict = {"visibility": visibility, "phone": phone}
    if firstname:
        body["firstname"] = firstname
    if lastname:
        body["lastname"] = lastname
    if email:
        body["email"] = email

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=_auth_headers(api_key), json=body)
        if resp.status_code in (200, 201):
            data = resp.json()
            if data.get("success"):
                return data.get("data", {}).get("relation_id")
        logger.warning(f"Salesdock create relation failed ({resp.status_code}): {resp.text[:300]}")
    return None


async def create_call_task(
    api_key: str,
    domain: str,
    relation_id: str,
    title: str,
    description: str,
) -> Optional[int]:
    """
    Create a completed callback task linked to a relation.
    Used to write call summaries back to Salesdock.
    Returns the task_id or None.
    """
    url = _build_url(domain, "tasks")

    form_data = {
        "title": title,
        "type": "callback",
        "description": description,
        "relation_id": str(relation_id),
        "completed": "yes",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            headers=_auth_headers(api_key),
            data=form_data,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            if data.get("success"):
                return data.get("data", {}).get("task_id")
        logger.warning(f"Salesdock create task failed ({resp.status_code}): {resp.text[:300]}")
    return None


async def test_connection(api_key: str, domain: str) -> dict:
    """
    Test the Salesdock connection by making a lightweight API call.
    Returns account info dict on success, raises on failure.
    """
    url = _build_url(domain, "relations")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            url,
            headers=_auth_headers(api_key),
            params={"q": "test"},
        )
        if resp.status_code == 401:
            raise ValueError("Ongeldige API key")
        if resp.status_code == 403:
            raise ValueError("Geen toegang — controleer de API key rechten")
        if resp.status_code != 200:
            raise ValueError(f"Salesdock API fout (HTTP {resp.status_code})")

        data = resp.json()
        if not data.get("success"):
            raise ValueError(f"Salesdock API fout: {data.get('message', 'onbekend')}")

        return {
            "domain": domain,
            "message": data.get("message", "Verbinding succesvol"),
        }
