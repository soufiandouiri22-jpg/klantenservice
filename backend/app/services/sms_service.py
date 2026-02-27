"""
klantenservice.ai - SMS Service (Twilio)

Sends SMS confirmations for appointments.
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_CONFIRMATION_TEMPLATE = (
    "Uw afspraak bij {bedrijfsnaam} is bevestigd op {datum} om {tijd}. Tot dan!"
)


def send_sms(to: str, body: str) -> bool:
    """
    Send an SMS message via Twilio.
    Returns True on success, False on failure.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("[DEV] Twilio not configured, SMS not sent to %s: %s", to, body)
        return False

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=body,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to,
        )
        logger.info("SMS sent to %s (sid=%s)", to, message.sid)
        return True
    except Exception as e:
        logger.error("Failed to send SMS to %s: %s", to, e, exc_info=True)
        return False


def send_appointment_confirmation_sms(
    to: str,
    company_name: str,
    starts_at_readable: str,
    custom_template: Optional[str] = None,
) -> bool:
    """
    Send an appointment confirmation SMS using the company's template or default.
    
    Supported placeholders: {bedrijfsnaam}, {datum}, {tijd}
    """
    from datetime import datetime

    template = custom_template or DEFAULT_CONFIRMATION_TEMPLATE

    parts = starts_at_readable.split(" om ")
    datum = parts[0] if parts else starts_at_readable
    tijd = parts[1] if len(parts) > 1 else ""

    body = template.replace("{bedrijfsnaam}", company_name)
    body = body.replace("{datum}", datum)
    body = body.replace("{tijd}", tijd)

    return send_sms(to, body)
