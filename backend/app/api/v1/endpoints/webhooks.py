"""
klantenservice.ai - Webhook Endpoints
For receiving callbacks from external services (Twilio, calendar providers, etc.)
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from fastapi.responses import Response
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
import hmac
import hashlib
import httpx

import logging

from app.core.database import get_db
from app.core.config import settings
from app.services.tts_service import generate_tts_audio, get_tts_url
from app.services.openai_realtime_service import build_system_instructions
from app.core.voices import DEFAULT_VOICE_ID

logger = logging.getLogger(__name__)
from app.models.company import Company
from app.models.call_log import CallLog, CallStatus
from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.models.website_knowledge import WebsiteKnowledge, IndexStatus
from app.models.training import TrainingRule

router = APIRouter()


def verify_twilio_signature(request: Request, signature: str) -> bool:
    """Verify Twilio webhook signature."""
    # In production, implement proper Twilio signature verification
    return True


def _tts_twiml(text: str, voice: str = None, extra_twiml: str = "") -> str:
    """
    Build TwiML that plays a TTS-generated audio file.
    Falls back to <Say> if TTS generation fails.
    """
    filename = generate_tts_audio(text, voice=voice)
    if filename:
        url = get_tts_url(filename)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Play>{url}</Play>
            {extra_twiml}
            <Hangup/>
        </Response>"""
    else:
        # Fallback: use Twilio's built-in TTS
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say language="nl-NL">{text}</Say>
            {extra_twiml}
            <Hangup/>
        </Response>"""


@router.post("/twilio/voice")
async def twilio_voice_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle incoming Twilio voice webhook.
    This is called when a call comes in or status changes.
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    from_number = form_data.get("From")
    to_number = form_data.get("To")
    
    if not all([call_sid, from_number, to_number]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required parameters",
        )
    
    # Find the phone number and associated company
    from app.models.phone_number import PhoneNumber
    phone = db.query(PhoneNumber).filter(PhoneNumber.number == to_number).first()
    
    if not phone:
        # Return TwiML to reject the call
        twiml = _tts_twiml("Dit nummer is niet in gebruik.")
        return Response(content=twiml, media_type="text/xml")
    
    company = db.query(Company).filter(Company.id == phone.company_id).first()
    
    # Check kill switch - immediately reject calls for kill-switched companies
    if company and company.is_kill_switched:
        logger.warning(f"Call rejected: kill switch active for {company.name} (call_sid={call_sid})")
        twiml = _tts_twiml("Dit nummer is momenteel niet bereikbaar. Probeert u het later nog eens.")
        return Response(content=twiml, media_type="text/xml")
    
    # Check subscription status - reject calls for inactive subscriptions
    if company and company.subscription_status not in ("trialing", "active"):
        logger.warning(
            f"Call rejected: inactive subscription ({company.subscription_status}) "
            f"for {company.name} (call_sid={call_sid})"
        )
        twiml = _tts_twiml("Dit nummer is momenteel niet bereikbaar. Probeert u het later nog eens.")
        return Response(content=twiml, media_type="text/xml")
    
    # Check if within business hours
    if not phone.is_within_business_hours():
        # Use the AI worker's voice for the after-hours message if available
        worker_voice = None
        if phone.ai_worker_id:
            worker = db.query(AIWorker).filter(AIWorker.id == phone.ai_worker_id).first()
            if worker:
                worker_voice = worker.voice_id
        record_tag = "<Record maxLength='120' transcribe='true'/>" if phone.after_hours_voicemail else ""
        twiml = _tts_twiml(phone.after_hours_message, voice=worker_voice, extra_twiml=record_tag)
        return Response(content=twiml, media_type="text/xml")
    
    # First try the linked AI worker for this phone number
    available_worker = None
    
    if phone.ai_worker_id:
        linked_worker = db.query(AIWorker).filter(
            AIWorker.id == phone.ai_worker_id,
            AIWorker.is_active == True,
            AIWorker.status == AIWorkerStatus.AVAILABLE
        ).first()
        if linked_worker:
            available_worker = linked_worker
    
    # Fallback: find any available AI worker for the company
    if not available_worker:
        available_worker = db.query(AIWorker).filter(
            AIWorker.company_id == company.id,
            AIWorker.is_active == True,
            AIWorker.status == AIWorkerStatus.AVAILABLE
        ).first()
    
    if not available_worker:
        # All workers busy - queue or voicemail
        # Try to use the linked worker's voice for consistency
        busy_voice = None
        if phone.ai_worker_id:
            linked = db.query(AIWorker).filter(AIWorker.id == phone.ai_worker_id).first()
            if linked:
                busy_voice = linked.voice_id
        if phone.voicemail_enabled:
            twiml = _tts_twiml(
                "Al onze medewerkers zijn momenteel in gesprek. U kunt een bericht achterlaten na de piep.",
                voice=busy_voice,
                extra_twiml='<Record maxLength="120" transcribe="true"/>',
            )
        else:
            twiml = _tts_twiml(
                "Al onze medewerkers zijn momenteel in gesprek. Probeert u het later nog eens.",
                voice=busy_voice,
            )
        return Response(content=twiml, media_type="text/xml")
    
    # Create call log
    call_log = CallLog(
        id=uuid4(),
        company_id=company.id,
        ai_worker_id=available_worker.id,
        phone_number_id=phone.id,
        twilio_call_sid=call_sid,
        caller_number=from_number,
        called_number=to_number,
        status=CallStatus.IN_PROGRESS,
        started_at=datetime.utcnow(),
        answered_at=datetime.utcnow(),
    )
    db.add(call_log)
    
    # Mark worker as busy
    available_worker.status = AIWorkerStatus.BUSY
    available_worker.current_call_id = call_log.id
    
    db.commit()
    
    # ── Build full system prompt from admin + customer settings ──
    voice_id = available_worker.voice_id or DEFAULT_VOICE_ID

    # Knowledge context is NOT loaded into the system prompt to keep it
    # short and reduce latency.  The AI uses search_knowledge on-demand.

    # Load training rules (these are short and stay in the prompt)
    training_rules_db = db.query(TrainingRule).filter(
        TrainingRule.company_id == company.id,
        TrainingRule.is_enabled == True,
    ).order_by(TrainingRule.display_order).all()
    training_rules = [
        {"key": r.rule_key, "name": r.rule_name, "description": r.rule_description}
        for r in training_rules_db
    ]

    # Example answers are NOT loaded into the system prompt — the AI
    # retrieves them via search_knowledge when a relevant question is asked.

    # Disclosure message
    disclosure_message = company.disclosure_message if company.disclosure_message else None

    # Build the full system prompt (personality, tone, rules, permissions, etc.)
    full_instructions = build_system_instructions(
        worker=available_worker,
        company_name=company.name,
        disclosure_message=disclosure_message,
        knowledge_context=None,
        training_rules=training_rules,
        example_answers=None,
        db=db,
    )

    logger.info(
        f"Built full system prompt for {available_worker.name} "
        f"({len(full_instructions)} chars, {len(training_rules)} rules)"
    )

    # Time-aware greeting based on Amsterdam timezone
    ams_hour = datetime.now(ZoneInfo("Europe/Amsterdam")).hour
    if ams_hour < 12:
        greeting = "Goedemorgen"
    elif ams_hour < 18:
        greeting = "Goedemiddag"
    else:
        greeting = "Goedenavond"

    # Build first message — use disclosure if configured
    if disclosure_message:
        first_msg = disclosure_message.format(
            greeting=greeting,
            company_name=company.name,
            ai_worker_name=available_worker.name,
        )
    else:
        first_msg = (
            f"{greeting}, met {available_worker.name} van {company.name}, "
            "waarmee kan ik u helpen?"
        )

    # ── Connect to ElevenLabs Conversational AI ──────────────────
    register_payload = {
        "agent_id": settings.ELEVENLABS_AGENT_ID,
        "from_number": from_number,
        "to_number": to_number,
        "direction": "inbound",
        "conversation_initiation_client_data": {
            "dynamic_variables": {
                "company_id": str(company.id),
                "ai_worker_id": str(available_worker.id),
                "call_log_id": str(call_log.id),
                "customer_phone": from_number,
                "company_name": company.name or "",
            },
            "conversation_config_override": {
                "agent": {
                    "prompt": {
                        "prompt": full_instructions,
                    },
                    "first_message": first_msg,
                },
                "tts": {
                    "voice_id": voice_id,
                },
            },
        },
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.elevenlabs.io/v1/convai/twilio/register-call",
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json=register_payload,
            )
            resp.raise_for_status()
            
            twiml = resp.text
            logger.info(
                f"ElevenLabs register_call success for {call_sid} "
                f"(worker={available_worker.name}, voice={voice_id})"
            )
            logger.info(f"ElevenLabs TwiML for {call_sid}: {twiml[:500]}")

            # Inject a brief pause before <Connect> to give ElevenLabs'
            # WebSocket time to initialise — prevents silent-call issue
            # when calls come in quick succession.
            if "<Connect>" in twiml:
                twiml = twiml.replace(
                    "<Connect>",
                    "<Pause length=\"1\"/><Connect>",
                )

            return Response(content=twiml, media_type="text/xml")
            
    except Exception as e:
        logger.error(f"ElevenLabs register_call failed for {call_sid}: {e}", exc_info=True)
        # Fallback: play a professional TTS message instead of crashing
        twiml = _tts_twiml(
            "Er is een technisch probleem opgetreden. Probeert u het later nog eens.",
            voice=voice_id,
        )
        # Free the worker since the call won't connect
        available_worker.status = AIWorkerStatus.AVAILABLE
        available_worker.current_call_id = None
        call_log.status = CallStatus.FAILED
        db.commit()
        return Response(content=twiml, media_type="text/xml")


@router.post("/twilio/status")
async def twilio_status_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Twilio call status updates.
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    call_duration = form_data.get("CallDuration", 0)
    
    logger.info(
        f"Twilio status callback: call_sid={call_sid} "
        f"status={call_status} duration={call_duration}s"
    )
    
    call_log = db.query(CallLog).filter(CallLog.twilio_call_sid == call_sid).first()
    
    if not call_log:
        logger.warning(f"Status callback for unknown call_sid={call_sid} (status={call_status})")
        return {"status": "ok", "message": "Call not found"}
    
    status_mapping = {
        "completed": CallStatus.COMPLETED,
        "busy": CallStatus.MISSED,
        "no-answer": CallStatus.MISSED,
        "failed": CallStatus.FAILED,
        "canceled": CallStatus.ABANDONED,
    }
    
    if call_status in status_mapping:
        call_log.status = status_mapping[call_status]
        call_log.ended_at = datetime.utcnow()
        call_log.duration_seconds = int(call_duration)
        
        if call_log.ai_worker_id:
            worker = db.query(AIWorker).filter(AIWorker.id == call_log.ai_worker_id).first()
            if worker:
                worker.end_call()
                logger.info(
                    f"Worker {worker.name} freed after call {call_sid} "
                    f"(status={call_status}, duration={call_duration}s)"
                )
        
        db.commit()
    
    return {"status": "ok"}


@router.post("/twilio/recording")
async def twilio_recording_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle Twilio recording completion.
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    recording_url = form_data.get("RecordingUrl")
    recording_duration = form_data.get("RecordingDuration", 0)
    
    call_log = db.query(CallLog).filter(CallLog.twilio_call_sid == call_sid).first()
    
    if call_log:
        call_log.recording_url = recording_url
        call_log.recording_duration_seconds = int(recording_duration)
        db.commit()
    
    return {"status": "ok"}


@router.post("/website/{website_id}/update")
async def website_update_webhook(
    website_id: UUID,
    request: Request,
    x_webhook_secret: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Trigger website re-indexing via webhook.
    """
    website = db.query(WebsiteKnowledge).filter(WebsiteKnowledge.id == website_id).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )
    
    # Verify webhook secret
    if x_webhook_secret != website.webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )
    
    # Trigger re-indexing
    website.status = IndexStatus.pending
    db.commit()
    
    # TODO: Trigger background indexing job
    
    return {"status": "ok", "message": "Re-indexing scheduled"}


@router.post("/calendar/google/callback")
async def google_calendar_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Handle Google Calendar OAuth callback.
    """
    # TODO: Implement OAuth token exchange
    return {"status": "ok", "message": "Calendar connected"}


@router.post("/calendar/microsoft/callback")
async def microsoft_calendar_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Handle Microsoft Calendar OAuth callback.
    """
    # TODO: Implement OAuth token exchange
    return {"status": "ok", "message": "Calendar connected"}
