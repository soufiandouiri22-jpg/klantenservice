"""
klantenservice.ai - Public Demo Call Endpoint

Public (no auth) endpoint for the landing page "Demo gesprek" feature.
Connects visitors to the AI of the admin/demo company so they can
experience the product and book a demo with the account manager.

Rate-limited to prevent abuse.
"""
import logging
import time
from collections import defaultdict
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.ai_worker import AIWorker
from app.models.call_log import CallLog, CallStatus
from app.models.phone_number import PhoneNumber
from app.models.training import TrainingRule
from app.services.openai_realtime_service import build_system_instructions

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)

# Simple in-memory rate limiter: max requests per IP per hour
_RATE_LIMIT = 10
_RATE_WINDOW = 3600  # 1 hour in seconds
_ip_requests: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    timestamps = _ip_requests[ip]
    # Prune old entries
    _ip_requests[ip] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_ip_requests[ip]) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Te veel verzoeken. Probeer het later opnieuw.",
        )
    _ip_requests[ip].append(now)


def _get_demo_company(db: Session) -> tuple[Company, AIWorker]:
    """Look up the demo company and its first active AI worker."""
    user = db.query(User).filter(
        User.email == settings.DEMO_COMPANY_EMAIL,
    ).first()

    if not user or not user.company_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo is momenteel niet beschikbaar.",
        )

    company = db.query(Company).filter(Company.id == user.company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo is momenteel niet beschikbaar.",
        )

    worker = db.query(AIWorker).filter(
        AIWorker.company_id == company.id,
        AIWorker.is_active == True,
    ).first()

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo is momenteel niet beschikbaar. Probeer het later opnieuw.",
        )

    return company, worker


@router.post("/signed-url")
async def get_demo_signed_url(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Public endpoint: generate a signed URL for the landing page demo.
    No authentication required. Rate-limited per IP.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    company, worker = _get_demo_company(db)

    # Load training rules
    training_rules_db = db.query(TrainingRule).filter(
        TrainingRule.company_id == company.id,
        TrainingRule.is_enabled == True,
    ).order_by(TrainingRule.display_order).all()
    training_rules = [
        {"key": r.rule_key, "name": r.rule_name, "description": r.rule_description}
        for r in training_rules_db
    ]

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
    if ams_hour < 6:
        greeting = "Goedenavond"
    elif ams_hour < 12:
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

    # Create a demo CallLog so tools have context
    call_log = CallLog(
        id=uuid4(),
        company_id=company.id,
        ai_worker_id=worker.id,
        phone_number_id=phone.id if phone else None,
        twilio_call_sid=f"demo_{uuid4().hex[:16]}",
        caller_number="demo-visitor",
        called_number=phone.number if phone else "demo",
        status=CallStatus.IN_PROGRESS,
        started_at=datetime.utcnow(),
        answered_at=datetime.utcnow(),
    )
    db.add(call_log)
    db.commit()

    logger.info(
        f"[DEMO CALL] Created demo CallLog {call_log.id} "
        f"for company={company.name} worker={worker.name} ip={client_ip}"
    )

    # Get signed URL from ElevenLabs (include_conversation_id for demo call recording)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url",
                params={
                    "agent_id": settings.ELEVENLABS_AGENT_ID,
                    "include_conversation_id": "true",
                },
                headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            )
            resp.raise_for_status()
            data = resp.json()
            signed_url = data.get("signed_url")
            conversation_id = data.get("conversation_id")
            if conversation_id:
                call_log.elevenlabs_conversation_id = conversation_id
                db.commit()
    except Exception as e:
        logger.error(f"Failed to get ElevenLabs signed URL for demo: {e}", exc_info=True)
        db.delete(call_log)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Kon geen verbinding maken met de spraakservice.",
        )

    # Get calendar_id if available
    calendar_id = ""
    try:
        from app.models.calendar_integration import CalendarIntegration
        cal = db.query(CalendarIntegration).filter(
            CalendarIntegration.company_id == company.id,
            CalendarIntegration.is_active == True,
        ).first()
        if cal:
            calendar_id = str(cal.id)
    except Exception:
        pass

    return {
        "signed_url": signed_url,
        "overrides": {
            "agent": {
                "prompt": {"prompt": full_instructions},
            },
            "tts": {"voiceId": voice_id},
        },
        "dynamic_variables": {
            "company_id": str(company.id),
            "ai_worker_id": str(worker.id),
            "call_log_id": str(call_log.id),
            "customer_phone": "",
            "company_name": company.name or "",
            "call_sid": call_log.twilio_call_sid,
            "calendar_id": calendar_id,
        },
        "first_message": first_msg,
        "worker_name": worker.name,
        "call_log_id": str(call_log.id),
    }


@router.post("/end")
async def end_demo_call(
    data: dict,
    db: Session = Depends(get_db),
):
    """Mark a demo call as completed."""
    call_log_id = data.get("call_log_id")
    if not call_log_id:
        return {"ok": True}

    call_log = db.query(CallLog).filter(
        CallLog.id == call_log_id,
        CallLog.caller_number == "demo-visitor",
    ).first()

    if call_log:
        call_log.status = CallStatus.COMPLETED
        call_log.ended_at = datetime.utcnow()
        if call_log.started_at:
            call_log.duration_seconds = int(
                (datetime.utcnow() - call_log.started_at).total_seconds()
            )
        db.commit()
        logger.info(f"[DEMO CALL] Ended demo CallLog {call_log.id}")

    return {"ok": True}
