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
import asyncio

from app.core.database import get_db
from app.core.config import settings
from app.services.tts_service import generate_tts_audio, get_tts_url
from app.services.openai_realtime_service import build_system_instructions
from app.core.voices import DEFAULT_VOICE_ID

logger = logging.getLogger(__name__)
from app.models.company import Company
from app.models.call_log import CallLog, CallStatus, CallTranscript
from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.services.indexing.models import IdxSite, SiteStatus
from app.models.training import TrainingRule

router = APIRouter()


async def _start_recording(call_sid: str):
    """Start call recording via Twilio REST API."""
    recording_callback = (
        "https://api.klantenservice.ai/api/v1/webhooks/twilio/recording"
        if settings.APP_ENV == "production"
        else "http://localhost:8000/api/v1/webhooks/twilio/recording"
    )
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Calls/{call_sid}/Recordings.json",
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                data={
                    "RecordingChannels": "dual",
                    "RecordingStatusCallback": recording_callback,
                    "RecordingStatusCallbackEvent": "completed",
                },
            )
            logger.info(f"[RECORDING] Started for call_sid={call_sid} (status={resp.status_code})")
    except Exception as e:
        logger.warning(f"[RECORDING] Failed to start for {call_sid}: {e}")


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
    form_dict = dict(form_data)
    
    call_sid = form_dict.get("CallSid")
    call_status = form_dict.get("CallStatus")
    from_number = form_dict.get("From")
    to_number = form_dict.get("To")
    
    logger.info(
        f"[VOICE WEBHOOK] call_sid={call_sid} call_status={call_status} "
        f"from={from_number} to={to_number} "
        f"all_params={list(form_dict.keys())}"
    )
    
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
    
    # Auto-verify forwarding when a forwarded call comes in
    forwarded_from = form_dict.get("ForwardedFrom")
    if forwarded_from and not phone.forwarding_verified:
        phone.forwarding_verified = True
        phone.setup_completed = True
        db.commit()
        logger.info(f"Forwarding auto-verified for phone {phone.number} (forwarded from {forwarded_from})")
    
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

    # Check call minutes limit
    if company:
        from app.api.v1.endpoints.payments import PLAN_MINUTES
        from sqlalchemy import func as sqlfunc

        plan = company.subscription_plan.value
        limit = PLAN_MINUTES.get(plan)
        if limit is not None:
            now = datetime.utcnow()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            total_seconds = db.query(sqlfunc.coalesce(sqlfunc.sum(CallLog.duration_seconds), 0)).filter(
                CallLog.company_id == company.id,
                CallLog.started_at >= month_start,
                CallLog.duration_seconds > 0,
            ).scalar()
            minutes_used = total_seconds / 60
            if minutes_used >= limit:
                logger.warning(
                    f"Call rejected: minutes limit reached ({minutes_used:.0f}/{limit}) "
                    f"for {company.name} (call_sid={call_sid})"
                )
                twiml = _tts_twiml("Het belbudget voor deze maand is bereikt. Probeert u het later nog eens.")
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
        else:
            busy_check = db.query(AIWorker).filter(AIWorker.id == phone.ai_worker_id).first()
            if busy_check:
                logger.info(
                    f"[VOICE WEBHOOK] Linked worker {busy_check.name} not available: "
                    f"status={busy_check.status.value}, active={busy_check.is_active}, "
                    f"current_call_id={busy_check.current_call_id}"
                )
    
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

    # ── CRM caller lookup ──────────────────────────────────────
    caller_context = None
    try:
        from app.models.crm_integration import CRMIntegration
        from app.services import hubspot_service as hubspot
        crm_integration = db.query(CRMIntegration).filter(
            CRMIntegration.company_id == company.id,
            CRMIntegration.is_active == True,
            CRMIntegration.sync_contacts_on_call == True,
        ).first()
        if crm_integration and crm_integration.access_token_encrypted:
            try:
                access_token = await hubspot.get_valid_access_token(crm_integration, db)
                contact = await hubspot.search_contact_by_phone(access_token, from_number)
                if contact:
                    caller_context = contact
                    logger.info(f"CRM lookup found contact: {contact.get('first_name')} {contact.get('last_name')}")
            except Exception as crm_err:
                logger.warning(f"CRM lookup failed (non-blocking): {crm_err}")
    except Exception as crm_import_err:
        logger.debug(f"CRM module not available: {crm_import_err}")

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
        caller_context=caller_context,
        custom_instructions=company.custom_instructions,
        transfer_enabled=bool(phone.transfer_enabled and phone.transfer_number),
    )

    logger.info(
        f"Built full system prompt for {available_worker.name} "
        f"({len(full_instructions)} chars, {len(training_rules)} rules)"
    )

    # Time-aware greeting based on Amsterdam timezone
    ams_hour = datetime.now(ZoneInfo("Europe/Amsterdam")).hour
    if ams_hour < 6:
        greeting = "Goedenavond"
    elif ams_hour < 12:
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
                "call_sid": call_sid,
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
                f"[VOICE WEBHOOK] ElevenLabs register_call OK for {call_sid} "
                f"worker={available_worker.name} voice={voice_id} "
                f"status_code={resp.status_code} "
                f"response_headers={dict(resp.headers)} "
                f"twiml={twiml}"
            )

            asyncio.create_task(_start_recording(call_sid))

            return Response(content=twiml, media_type="text/xml")
            
    except Exception as e:
        logger.error(f"[VOICE WEBHOOK] ElevenLabs register_call FAILED for {call_sid}: {e}", exc_info=True)
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
    form_dict = dict(form_data)
    
    call_sid = form_dict.get("CallSid")
    call_status = form_dict.get("CallStatus")
    call_duration = form_dict.get("CallDuration", 0)
    
    logger.info(
        f"[STATUS CALLBACK] call_sid={call_sid} status={call_status} "
        f"duration={call_duration}s all_params={form_dict}"
    )
    
    call_log = db.query(CallLog).filter(CallLog.twilio_call_sid == call_sid).first()
    
    if not call_log:
        logger.warning(f"[STATUS CALLBACK] Unknown call_sid={call_sid} (status={call_status})")
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
                    f"[STATUS CALLBACK] Worker {worker.name} freed: "
                    f"call_sid={call_sid} status={call_status} duration={call_duration}s"
                )
        
        db.commit()

        # Notification: missed / failed call
        if call_status in ("no-answer", "busy", "failed"):
            try:
                from app.services.notification_service import create_notification
                from app.models.notification import NotificationType
                caller = call_log.caller_number or "Onbekend nummer"
                create_notification(
                    db=db,
                    company_id=str(call_log.company_id),
                    type=NotificationType.CALL_ERROR,
                    title=f"Gemist gesprek van {caller}",
                    message=f"Status: {call_status}",
                    url="/dashboard/calls",
                )
            except Exception:
                logger.warning("Failed to create missed-call notification", exc_info=True)

        # Post-call sentiment analysis (non-blocking)
        if call_status == "completed":
            try:
                from app.services.sentiment_service import analyze_sentiment
                transcripts = db.query(CallTranscript).filter(
                    CallTranscript.call_log_id == call_log.id
                ).order_by(CallTranscript.timestamp).all()
                if transcripts:
                    transcript_text = "\n".join(
                        f"{'Klant' if t.speaker == 'caller' else 'AI'}: {t.message}"
                        for t in transcripts
                    )
                    sentiment = await analyze_sentiment(transcript_text)
                    if sentiment:
                        call_log.sentiment = sentiment
                        db.commit()
                        logger.info(f"[SENTIMENT] call_sid={call_sid} → {sentiment}")

                        if sentiment == "negative":
                            try:
                                from app.services.notification_service import create_notification
                                from app.models.notification import NotificationType
                                caller = call_log.caller_number or "Onbekend nummer"
                                create_notification(
                                    db=db,
                                    company_id=str(call_log.company_id),
                                    type=NotificationType.CALL_ERROR,
                                    title="Ontevreden klant",
                                    message=f"Gesprek met {caller} is als negatief beoordeeld.",
                                    url=f"/dashboard/calls",
                                )
                            except Exception:
                                logger.warning("Failed to create negative-sentiment notification", exc_info=True)
            except Exception as sent_err:
                logger.warning(f"Sentiment analysis failed (non-blocking): {sent_err}")

        # Write call summary back to CRM if configured
        if call_status == "completed" and call_log.summary:
            try:
                from app.models.crm_integration import CRMIntegration
                from app.services import hubspot_service as hubspot
                crm = db.query(CRMIntegration).filter(
                    CRMIntegration.company_id == call_log.company_id,
                    CRMIntegration.is_active == True,
                    CRMIntegration.write_call_notes == True,
                ).first()
                if crm and crm.access_token_encrypted:
                    access_token = await hubspot.get_valid_access_token(crm, db)
                    contact = await hubspot.search_contact_by_phone(
                        access_token, call_log.caller_number
                    )
                    if contact:
                        note_body = (
                            f"Telefoongesprek via klantenservice.ai\n"
                            f"Duur: {call_duration}s\n\n"
                            f"{call_log.summary}"
                        )
                        await hubspot.create_engagement_note(
                            access_token, contact["id"], note_body
                        )
                        logger.info(f"CRM note created for contact {contact['id']}")
            except Exception as crm_err:
                logger.warning(f"CRM post-call note failed (non-blocking): {crm_err}")
    elif call_status == "in-progress":
        logger.info(f"[STATUS CALLBACK] Call in-progress: call_sid={call_sid} (recording started from voice webhook)")
    else:
        logger.info(f"[STATUS CALLBACK] Ignoring status={call_status} for call_sid={call_sid}")
    
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
    site = db.query(IdxSite).filter(IdxSite.id == website_id).first()
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website not found",
        )
    
    # Trigger re-indexing
    site.status = SiteStatus.pending
    db.commit()
    
    import asyncio
    from app.core.config import settings
    from app.api.v1.endpoints.websites import _run_indexing_background
    asyncio.create_task(_run_indexing_background(str(site.id), settings.DATABASE_URL))
    
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
