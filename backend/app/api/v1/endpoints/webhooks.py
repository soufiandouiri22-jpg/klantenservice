"""
klantenservice.ai - Webhook Endpoints
For receiving callbacks from external services (Twilio, calendar providers, etc.)
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from fastapi.responses import Response
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
import hmac
import hashlib

from app.core.database import get_db
from app.core.config import settings
from app.models.company import Company
from app.models.call_log import CallLog, CallStatus
from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.models.website_knowledge import WebsiteKnowledge, IndexStatus

router = APIRouter()


def verify_twilio_signature(request: Request, signature: str) -> bool:
    """Verify Twilio webhook signature."""
    # In production, implement proper Twilio signature verification
    return True


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
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say language="nl-NL">Dit nummer is niet in gebruik.</Say>
            <Hangup/>
        </Response>"""
        return Response(content=twiml, media_type="text/xml")
    
    company = db.query(Company).filter(Company.id == phone.company_id).first()
    
    # Check if within business hours
    if not phone.is_within_business_hours():
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say language="nl-NL">{phone.after_hours_message}</Say>
            {"<Record maxLength='120' transcribe='true'/>" if phone.after_hours_voicemail else ""}
            <Hangup/>
        </Response>"""
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
        if phone.voicemail_enabled:
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say language="nl-NL">Al onze medewerkers zijn momenteel in gesprek. U kunt een bericht achterlaten na de piep.</Say>
                <Record maxLength="120" transcribe="true"/>
                <Hangup/>
            </Response>"""
        else:
            twiml = """<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say language="nl-NL">Al onze medewerkers zijn momenteel in gesprek. Probeert u het later nog eens.</Say>
                <Hangup/>
            </Response>"""
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
    
    # Return TwiML to connect to the AI via PersonaPlex
    disclosure = company.disclosure_message.format(
        company_name=company.name,
        ai_worker_name=available_worker.name
    )
    
    # Get the WebSocket URL from settings or use default
    ws_url = settings.WEBSOCKET_URL or "wss://api.klantenservice.ai/ws/voice"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say language="nl-NL">{disclosure}</Say>
        <Connect>
            <Stream url="{ws_url}">
                <Parameter name="to" value="{to_number}"/>
                <Parameter name="from" value="{from_number}"/>
            </Stream>
        </Connect>
    </Response>"""
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
    
    call_log = db.query(CallLog).filter(CallLog.twilio_call_sid == call_sid).first()
    
    if not call_log:
        return {"status": "ok", "message": "Call not found"}
    
    # Update call status
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
        
        # Free up the AI worker
        if call_log.ai_worker_id:
            worker = db.query(AIWorker).filter(AIWorker.id == call_log.ai_worker_id).first()
            if worker:
                worker.end_call()
        
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
