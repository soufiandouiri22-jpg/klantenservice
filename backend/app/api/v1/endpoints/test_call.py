"""
klantenservice.ai - Test Call Endpoint

Generates a signed URL for in-browser voice testing via ElevenLabs
Conversational AI. Uses the same prompt pipeline as real Twilio calls.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.ai_worker import AIWorker
from app.models.training import TrainingRule
from app.services.openai_realtime_service import build_system_instructions
from app.api.deps import get_current_user, get_current_company

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/signed-url")
async def get_test_call_signed_url(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """
    Generate a signed URL for testing the AI in the browser.
    Builds the exact same prompt as a real inbound call.
    """
    worker = db.query(AIWorker).filter(
        AIWorker.company_id == company.id,
        AIWorker.is_active == True,
    ).first()

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geen AI-medewerker gevonden. Maak eerst een AI-medewerker aan.",
        )

    training_rules_db = db.query(TrainingRule).filter(
        TrainingRule.company_id == company.id,
        TrainingRule.is_enabled == True,
    ).order_by(TrainingRule.display_order).all()
    training_rules = [
        {"key": r.rule_key, "name": r.rule_name, "description": r.rule_description}
        for r in training_rules_db
    ]

    from app.models.phone_number import PhoneNumber
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.company_id == company.id,
        PhoneNumber.is_active == True,
    ).first()

    transfer_enabled = bool(
        phone and phone.transfer_enabled and phone.transfer_number
    )

    disclosure_message = company.disclosure_message or None

    full_instructions = build_system_instructions(
        worker=worker,
        company_name=company.name,
        disclosure_message=disclosure_message,
        knowledge_context=None,
        training_rules=training_rules,
        example_answers=None,
        db=db,
        caller_context=None,
        custom_instructions=company.custom_instructions,
        transfer_enabled=transfer_enabled,
    )

    ams_hour = datetime.now(ZoneInfo("Europe/Amsterdam")).hour
    if ams_hour < 12:
        greeting = "Goedemorgen"
    elif ams_hour < 18:
        greeting = "Goedemiddag"
    else:
        greeting = "Goedenavond"

    if disclosure_message:
        first_msg = disclosure_message.format(
            greeting=greeting,
            company_name=company.name,
            ai_worker_name=worker.name,
        )
    else:
        first_msg = (
            f"{greeting}, met {worker.name} van {company.name}, "
            "waarmee kan ik u helpen?"
        )

    voice_id = worker.voice_id or "AVIlLDn2TVmdaDycgbo3"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url",
                params={"agent_id": settings.ELEVENLABS_AGENT_ID},
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            )
            resp.raise_for_status()
            signed_url = resp.json().get("signed_url")
    except Exception as e:
        logger.error(f"Failed to get ElevenLabs signed URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Kon geen verbinding maken met de spraakservice.",
        )

    return {
        "signed_url": signed_url,
        "overrides": {
            "agent": {
                "prompt": {"prompt": full_instructions},
                "firstMessage": first_msg,
            },
            "tts": {"voiceId": voice_id},
        },
        "worker_name": worker.name,
    }
