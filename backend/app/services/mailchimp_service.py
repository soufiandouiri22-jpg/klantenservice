"""
klantenservice.ai - Mailchimp Service
Adds subscribers to the Mailchimp audience when they register with marketing consent.
"""
import hashlib
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_server_prefix(api_key: str) -> str:
    """Extract datacenter prefix from API key (e.g. 'us3')."""
    return api_key.rsplit("-", 1)[-1]


async def add_subscriber(
    email: str,
    first_name: str = "",
    last_name: str = "",
    company_name: str = "",
) -> bool:
    """
    Add or update a subscriber in the Mailchimp audience.
    Uses PUT with subscriber hash for upsert behavior.
    Returns True on success, False on failure (non-blocking).
    """
    settings = get_settings()
    api_key = settings.MAILCHIMP_API_KEY
    audience_id = settings.MAILCHIMP_AUDIENCE_ID

    if not api_key or not audience_id:
        logger.debug("Mailchimp not configured, skipping subscriber add")
        return False

    server = _get_server_prefix(api_key)
    subscriber_hash = hashlib.md5(email.lower().encode()).hexdigest()
    url = f"https://{server}.api.mailchimp.com/3.0/lists/{audience_id}/members/{subscriber_hash}"

    payload = {
        "email_address": email,
        "status_if_new": "subscribed",
        "merge_fields": {
            "FNAME": first_name,
            "LNAME": last_name,
            "COMPANY": company_name,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.put(
                url,
                json=payload,
                auth=("anystring", api_key),
            )
            if resp.status_code in (200, 201):
                logger.info(f"Mailchimp: added/updated subscriber {email}")
                return True
            else:
                logger.warning(
                    f"Mailchimp: failed to add {email} "
                    f"(status={resp.status_code}, body={resp.text[:200]})"
                )
                return False
    except Exception as e:
        logger.warning(f"Mailchimp: request failed for {email}: {e}")
        return False
