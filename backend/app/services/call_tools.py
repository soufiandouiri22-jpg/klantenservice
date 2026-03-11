"""
klantenservice.ai - Call Tools for Orchestrator

Tool functions that the orchestrator calls during voice calls.
All "truth" (prices, availability, business info) comes from these tools.
The AI only speaks what the backend provides via these tool results.

Tools:
- check_availability: Get available calendar slots (real calendar API)
- book_appointment: Create an appointment (real calendar API + internal DB)
- search_knowledge: RAG search in company knowledge base
- get_prices: Search for price information (via RAG)
- create_note: Create internal note for dashboard
- flag_unknown: Flag question that couldn't be answered (realtime to dashboard)
- check_policy: Policy engine — checks whether an action is allowed
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.calendar_integration import CalendarIntegration, CalendarProvider
from app.models.appointment import Appointment, AppointmentStatus
from app.models.internal_note import InternalNote, NotePriority
from app.models.training import ExampleAnswer
from app.services.retrieval import RetrievalService
from app.services.voice.intent_classifier import classify_intent, CallerIntent
from app.services.voice.conversation_state import ConversationStateManager
from app.services.voice.policy_engine import PolicyEngine, PolicyResult

logger = logging.getLogger(__name__)


async def tool_check_availability(
    db: Session,
    company_id: str,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    duration_minutes: int = 30,
    ai_worker_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get available time slots from the AI worker's linked calendar.
    Queries the real Google/Outlook calendar for events and applies availability rules.
    """
    query = db.query(CalendarIntegration).filter(
        CalendarIntegration.company_id == company_id,
        CalendarIntegration.is_active == True,
    )
    if ai_worker_id:
        query = query.filter(CalendarIntegration.ai_worker_id == ai_worker_id)
    calendar = query.first()

    if not calendar:
        return {
            "ok": False,
            "reason": "geen_agenda",
            "message": "Afspraken inplannen is op dit moment niet mogelijk. Zeg NIET dat er geen agenda is. Bied aan om de gegevens te noteren zodat een collega zo snel mogelijk terugbelt om een afspraak in te plannen. Bevestig het telefoonnummer van de klant.",
            "slots": []
        }

    if not calendar.access_token_encrypted:
        return {
            "ok": False,
            "reason": "niet_verbonden",
            "message": "Afspraken inplannen is op dit moment niet mogelijk. Zeg NIET dat de agenda niet werkt. Bied aan om de gegevens te noteren zodat een collega zo snel mogelijk terugbelt om een afspraak in te plannen. Bevestig het telefoonnummer van de klant.",
            "slots": []
        }

    end = end_date or (start_date + timedelta(days=7))

    try:
        if calendar.provider == CalendarProvider.MICROSOFT:
            from app.services import outlook_calendar_service as svc
        else:
            from app.services import google_calendar_service as svc

        slots = await svc.get_availability_for_range(
            calendar=calendar,
            db=db,
            start_date=start_date,
            end_date=end,
            duration_minutes=duration_minutes,
        )

        formatted = [s["start"][:16].replace("T", " ") for s in slots[:20]]

        return {
            "ok": True,
            "slots": formatted,
            "calendar_id": str(calendar.id),
            "calendar_name": calendar.name,
            "message": f"Er zijn {len(formatted)} beschikbare momenten gevonden."
                if formatted else "Er zijn geen beschikbare momenten in deze periode.",
            "next_action": "Bied maximaal 3 opties aan en vraag welk moment het beste uitkomt. Vraag daarna de naam van de klant.",
        }

    except Exception as e:
        logger.error(f"Calendar availability error: {e}", exc_info=True)
        return {
            "ok": False,
            "reason": "agenda_fout",
            "message": "Er ging iets mis bij het ophalen van de beschikbaarheid. Vraag de klant om later terug te bellen.",
            "slots": []
        }


async def tool_book_appointment(
    db: Session,
    company_id: str,
    calendar_integration_id: str,
    starts_at: datetime,
    ends_at: datetime,
    customer_name: str,
    title: str = "Afspraak",
    customer_phone: Optional[str] = None,
    customer_email: Optional[str] = None,
    call_log_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an appointment in both the external calendar (Google/Outlook) and the internal DB.
    """
    calendar = db.query(CalendarIntegration).filter(
        CalendarIntegration.id == calendar_integration_id,
        CalendarIntegration.company_id == company_id,
    ).first()

    if not calendar:
        return {
            "ok": False,
            "reason": "agenda_niet_gevonden",
            "message": "De agenda kon niet worden gevonden."
        }

    duration = int((ends_at - starts_at).total_seconds() / 60)
    description = f"Geboekt tijdens telefoongesprek met {customer_name}"
    if customer_phone:
        description += f"\nTelefoon: {customer_phone}"

    external_event_id = None
    try:
        if calendar.access_token_encrypted:
            if calendar.provider == CalendarProvider.MICROSOFT:
                from app.services import outlook_calendar_service as svc
            else:
                from app.services import google_calendar_service as svc

            event = await svc.book_appointment(
                calendar=calendar,
                db=db,
                summary=title,
                start=starts_at,
                end=ends_at,
                description=description,
                attendee_email=customer_email or "",
            )
            external_event_id = event.get("id")
    except Exception as e:
        logger.error(f"Failed to create external calendar event: {e}", exc_info=True)

    appointment = Appointment(
        id=uuid4(),
        company_id=UUID(company_id),
        calendar_integration_id=UUID(calendar_integration_id),
        call_log_id=UUID(call_log_id) if call_log_id else None,
        external_event_id=external_event_id,
        title=title,
        description=description,
        appointment_type=None,
        starts_at=starts_at,
        ends_at=ends_at,
        duration_minutes=duration,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        status=AppointmentStatus.CONFIRMED,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    try:
        from app.services.notification_service import create_notification
        from app.models.notification import NotificationType
        create_notification(
            db=db,
            company_id=company_id,
            type=NotificationType.APPOINTMENT_NEW,
            title=f"Nieuwe afspraak: {customer_name}",
            message=f"Afspraak ingepland op {starts_at.strftime('%d-%m-%Y')} om {starts_at.strftime('%H:%M')}.",
            url="/dashboard/appointments",
        )
    except Exception:
        pass

    day_names = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    day_name = day_names[starts_at.weekday()]
    starts_at_readable = f"{day_name} {starts_at.day} {starts_at.strftime('%B')} om {starts_at.strftime('%H:%M')}"

    if customer_phone:
        try:
            from app.models.phone_number import PhoneNumber
            from app.models.company import Company
            from app.services.sms_service import send_appointment_confirmation_sms

            phone_cfg = db.query(PhoneNumber).filter(
                PhoneNumber.company_id == company_id,
                PhoneNumber.is_active == True,
                PhoneNumber.sms_confirmation_enabled == True,
            ).first()

            if phone_cfg:
                company_obj = db.query(Company).filter(Company.id == company_id).first()
                company_name = company_obj.name if company_obj else "ons bedrijf"
                send_appointment_confirmation_sms(
                    to=customer_phone,
                    company_name=company_name,
                    starts_at_readable=starts_at_readable,
                    custom_template=phone_cfg.sms_confirmation_template,
                )
        except Exception as e:
            logger.error(f"Failed to send confirmation SMS: {e}", exc_info=True)

    return {
        "ok": True,
        "appointment_id": str(appointment.id),
        "starts_at": starts_at.isoformat(),
        "starts_at_readable": starts_at_readable,
        "customer_name": customer_name,
        "message": f"Afspraak ingepland op {day_name} om {starts_at.strftime('%H:%M')} voor {customer_name}.",
        "in_external_calendar": external_event_id is not None,
        "next_action": "Bevestig de afspraak en vraag of er verder nog iets is.",
    }


def _matches_example_answer(query: str, question: str, variations: List[str]) -> bool:
    """Match query to ExampleAnswer via substring only."""
    query_lower = query.lower()
    if query_lower in (question or "").lower():
        return True
    for v in (variations or []):
        if query_lower in (v or "").lower():
            return True
    return False


def _run_retrieval(db: Session, company_id: str, query: str, limit: int) -> List[Dict]:
    """Bridge async RetrievalService into sync context safely."""
    import asyncio
    import time as _time

    retrieval = RetrievalService(db)
    t0 = _time.time()

    async def _do():
        return await retrieval.search(company_id, query, limit=limit)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _do())
            result = future.result(timeout=15)
    else:
        result = asyncio.run(_do())

    elapsed_ms = int((_time.time() - t0) * 1000)
    logger.info("[_run_retrieval] completed in %dms, results=%d", elapsed_ms, len(result.get("results", [])) if isinstance(result, dict) else 0)

    return result.get("results", []) if isinstance(result, dict) else []


def tool_search_knowledge(
    db: Session,
    company_id: str,
    query: str,
    limit: int = 5,
) -> Dict[str, Any]:
    """Search company knowledge base using hybrid retrieval pipeline."""
    if not query.strip():
        return {"ok": True, "results": [], "message": "Geen zoekopdracht opgegeven."}

    import time as _time
    t0 = _time.time()
    logger.info("[search_knowledge] START query=%r company=%s limit=%d", query, company_id, limit)

    # 1. Retrieval pipeline (vector + metadata + fulltext + reranking)
    retrieval_results = _run_retrieval(db, company_id, query, limit)

    # Log top retrieval results
    for i, r in enumerate(retrieval_results[:5]):
        logger.info(
            "[search_knowledge] result #%d: score=%.4f type=%s url=%s title=%r preview=%r",
            i + 1, r.get("score", 0), r.get("chunk_type", "?"),
            r.get("url", "")[:80], (r.get("title") or "")[:60],
            r.get("content", "")[:250].replace("\n", " "),
        )

    # 2. ExampleAnswers — training/voorbeeldantwoorden (substring match)
    qa_results = []
    try:
        qa_all = (
            db.query(ExampleAnswer)
            .filter(
                ExampleAnswer.company_id == company_id,
                ExampleAnswer.is_active == True,
                ExampleAnswer.is_verified == True,
            )
            .all()
        )
        for qa in qa_all:
            if _matches_example_answer(query, qa.question, qa.question_variations or []):
                qa_results.append({
                    "content": f"Vraag: {qa.question}\nAntwoord: {qa.answer}",
                    "url": "",
                    "title": qa.category or "Voorbeeldantwoord",
                })
    except Exception:
        logger.warning("Failed to search ExampleAnswers", exc_info=True)

    results = retrieval_results + qa_results
    elapsed_ms = int((_time.time() - t0) * 1000)
    logger.info(
        "[search_knowledge] DONE in %dms: %d retrieval + %d training = %d total",
        elapsed_ms, len(retrieval_results), len(qa_results), len(results),
    )

    if not results:
        return {
            "ok": True,
            "results": [],
            "message": "Geen informatie beschikbaar. VERZIN NIETS. Zeg eerlijk dat je het antwoord op dit moment niet bij de hand hebt. Bied aan om een notitie achter te laten zodat een collega de klant zo snel mogelijk terugbelt met het antwoord. Bevestig het telefoonnummer.",
        }

    # Log the final message that will be sent to the voice agent
    final_msg = f"{len(results)} relevante resultaten gevonden."
    logger.info("[search_knowledge] final_message=%r", final_msg)
    for r in results:
        logger.info(
            "[search_knowledge] -> TTS content (%d chars): %r",
            len(r.get("content", "")),
            r.get("content", "")[:300].replace("\n", " "),
        )

    return {
        "ok": True,
        "results": results,
        "message": final_msg,
    }


def tool_get_prices(
    db: Session,
    company_id: str,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    """Get price information from knowledge base via retrieval pipeline."""
    query = topic or "prijzen tarieven kosten"
    if topic and "prijs" not in topic.lower():
        query = f"{topic} prijs tarief kosten"

    result = tool_search_knowledge(db, company_id, query, limit=3)
    prices = [
        r["content"][:500]
        for r in result.get("results", [])
        if any(w in r.get("content", "").lower() for w in ("€", "euro", "prijs", "tarief", "kost"))
    ]

    if not prices:
        return {
            "ok": True,
            "prices": [],
            "message": "Geen prijsinformatie gevonden. Vraag de klant om contact op te nemen voor prijzen.",
        }

    return {"ok": True, "prices": prices, "message": "Prijsinformatie gevonden."}


def tool_create_note(
    db: Session,
    company_id: str,
    title: str,
    content: str,
    call_log_id: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    action_required: bool = False,
    priority: str = "normal",
) -> Dict[str, Any]:
    """
    Create an internal note for the dashboard.
    
    Args:
        db: Database session
        company_id: Company UUID
        title: Note title
        content: Note content
        call_log_id: Link to the call
        customer_name: Customer name
        customer_phone: Customer phone
        action_required: Whether follow-up is needed
        priority: low, normal, high, urgent
        
    Returns:
        Dict with ok, note_id, message
    """
    # Map priority string to enum
    priority_map = {
        "low": NotePriority.LOW,
        "normal": NotePriority.NORMAL,
        "high": NotePriority.HIGH,
        "urgent": NotePriority.URGENT,
    }
    note_priority = priority_map.get(priority.lower(), NotePriority.NORMAL)
    
    note = InternalNote(
        id=uuid4(),
        company_id=UUID(company_id),
        call_log_id=UUID(call_log_id) if call_log_id else None,
        title=title,
        content=content,
        category="Telefoon",
        tags=[],
        priority=note_priority,
        customer_name=customer_name,
        customer_phone=customer_phone,
        action_required=action_required,
        action_description="Terugbellen" if action_required else None,
        is_resolved=False,
    )
    
    db.add(note)
    db.commit()
    db.refresh(note)
    
    logger.info(f"Created note {note.id} for company {company_id}")

    if action_required:
        try:
            from app.services.notification_service import create_notification
            from app.models.notification import NotificationType
            create_notification(
                db=db,
                company_id=company_id,
                type=NotificationType.NOTE_ACTION,
                title=f"Actie vereist: {title}",
                message=content[:120] if content else None,
                url="/dashboard/notes",
            )
        except Exception:
            logger.warning("Failed to create note-action notification", exc_info=True)

        # Send callback SMS to the customer
        if customer_phone:
            try:
                from app.models.phone_number import PhoneNumber
                from app.models.company import Company
                phone = (
                    db.query(PhoneNumber)
                    .filter(PhoneNumber.company_id == company_id, PhoneNumber.is_active == True)
                    .first()
                )
                if phone and phone.sms_confirmation_enabled:
                    company = db.query(Company).filter(Company.id == company_id).first()
                    company_name = company.name if company else "ons bedrijf"
                    template = phone.sms_callback_template or "Uw verzoek is genoteerd bij {bedrijfsnaam}. U wordt zo snel mogelijk teruggebeld."
                    sms_text = template.replace("{bedrijfsnaam}", company_name)

                    from app.services.sms_service import send_sms
                    send_sms(
                        to_number=customer_phone,
                        from_number=phone.number,
                        body=sms_text,
                    )
                    logger.info(f"Sent callback SMS to {customer_phone}")
            except Exception:
                logger.warning("Failed to send callback SMS", exc_info=True)

    return {
        "ok": True,
        "note_id": str(note.id),
        "message": "Notitie aangemaakt voor opvolging."
    }


def tool_flag_unknown(
    db: Session,
    company_id: str,
    question: str,
    call_log_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Flag a question that couldn't be answered (realtime to dashboard).
    
    This creates or increments a "detected question" in ExampleAnswer
    so it shows up in the training/dashboard immediately.
    
    Args:
        db: Database session
        company_id: Company UUID
        question: The question that couldn't be answered
        call_log_id: Link to the call
        
    Returns:
        Dict with ok, action (created/incremented), question
    """
    if not question.strip():
        return {"ok": False, "reason": "empty_question"}
    
    # Normalize question
    question = question.strip()
    if not question.endswith("?"):
        question += "?"
    
    try:
        # Check if similar question already exists (detected, unverified)
        existing = db.query(ExampleAnswer).filter(
            ExampleAnswer.company_id == company_id,
            ExampleAnswer.source == "detected",
            ExampleAnswer.is_verified == False,
        ).all()
        
        # Simple similarity check (exact or substring)
        for ex in existing:
            if ex.question and (
                question.lower() in ex.question.lower() or
                ex.question.lower() in question.lower()
            ):
                # Increment count
                ex.detected_count += 1
                ex.updated_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"Incremented detected question count: {question[:50]}... (count: {ex.detected_count})")
                
                return {
                    "ok": True,
                    "action": "incremented",
                    "question": question,
                    "count": ex.detected_count,
                    "message": "Deze vraag is vaker gesteld en wordt bekeken."
                }
        
        # Create new detected question
        new_question = ExampleAnswer(
            id=uuid4(),
            company_id=UUID(company_id),
            question=question,
            answer="",  # No answer yet
            source="detected",
            detected_count=1,
            is_active=False,  # Not active until verified
            is_verified=False,
        )
        
        db.add(new_question)
        db.commit()
        
        logger.info(f"Created new detected question: {question[:50]}...")

        try:
            from app.services.notification_service import create_notification
            from app.models.notification import NotificationType
            create_notification(
                db=db,
                company_id=company_id,
                type=NotificationType.DETECTED_QUESTION,
                title="Nieuwe onbeantwoorde vraag",
                message=question[:120],
                url="/dashboard/training",
            )
        except Exception:
            logger.warning("Failed to create detected-question notification", exc_info=True)
        
        return {
            "ok": True,
            "action": "created",
            "question": question,
            "count": 1,
            "message": "Vraag genoteerd voor opvolging door een medewerker."
        }
        
    except Exception as e:
        logger.error(f"Error flagging unknown question: {e}")
        db.rollback()
        return {
            "ok": False,
            "action": "error",
            "message": "Kon vraag niet opslaan."
        }


def tool_check_policy(
    db: Session,
    company_id: str,
    call_sid: str,
    call_log_id: Optional[str] = None,
    trigger_reason: str = "ending_call",
    customer_message: str = "",
) -> Dict[str, Any]:
    """
    Policy engine checkpoint — called by the AI before taking gated actions.

    trigger_reason options:
      ending_call, escalation, low_confidence, repeated_failure,
      off_topic, silence

    Returns machine-readable policy result:
      allowed, policy_name, required_action, reason_code, instruction_nl
    """
    if not call_sid:
        return {
            "ok": False,
            "allowed": True,
            "policy_name": "none",
            "required_action": "proceed",
            "reason_code": "no_call_sid",
            "instruction_nl": "",
        }

    mgr = ConversationStateManager(db)
    session = mgr.get_or_create(
        call_sid=call_sid,
        call_log_id=call_log_id,
        company_id=company_id,
    )

    intent, confidence = classify_intent(customer_message)
    logger.info(
        "[check_policy] call=%s reason=%s intent=%s(%.2f) msg=%r",
        call_sid, trigger_reason, intent.value, confidence,
        customer_message[:80],
    )

    mgr.record_turn(session, intent, customer_message, "check_policy", confidence)

    engine = PolicyEngine(db)
    result = engine.evaluate(
        session=session,
        intent=intent,
        trigger_tool="check_policy",
        trigger_reason=trigger_reason,
        intent_confidence=confidence,
        utterance=customer_message,
    )

    if trigger_reason == "ending_call" and result.allowed:
        mgr.mark_ended(session, ended_by="agent", hangup_reason="normal")

    db.commit()

    response: Dict[str, Any] = {
        "ok": True,
        **result.to_dict(),
    }

    # Flag that retrieval should be skipped on off-topic blocks
    if not result.allowed and result.policy_name == "scope_guard":
        response["skip_retrieval"] = True

    return response


def run_auto_policies(
    db: Session,
    company_id: str,
    call_sid: str,
    call_log_id: Optional[str],
    tool_name: str,
    customer_message: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Run automatic policy checks on every tool invocation.

    Returns a policy override dict if a policy blocks/redirects,
    or None if all policies pass.
    """
    if not call_sid:
        return None

    mgr = ConversationStateManager(db)
    session = mgr.get_or_create(
        call_sid=call_sid,
        call_log_id=call_log_id,
        company_id=company_id,
    )

    intent, confidence = classify_intent(customer_message)
    mgr.record_turn(session, intent, customer_message, tool_name, confidence)

    engine = PolicyEngine(db)
    override = engine.evaluate_all(
        session=session,
        intent=intent,
        trigger_tool=tool_name,
        intent_confidence=confidence,
        utterance=customer_message,
    )

    db.commit()

    if override and not override.allowed:
        logger.info(
            "[auto_policy] OVERRIDE on tool=%s policy=%s action=%s",
            tool_name, override.policy_name, override.required_action,
        )
        result: Dict[str, Any] = {
            "ok": True,
            "policy_override": True,
            **override.to_dict(),
        }
        if override.policy_name == "scope_guard":
            result["skip_retrieval"] = True
        return result

    return None


def tool_transfer_call(
    db: Session,
    company_id: str,
    call_log_id: Optional[str] = None,
    call_sid: Optional[str] = None,
    reason: str = "",
) -> Dict[str, Any]:
    """
    Transfer the current call to a human agent via Twilio.

    Looks up the PhoneNumber for the company, checks if transfer is enabled,
    then uses the Twilio REST API to redirect the live call to a <Dial> TwiML.
    """
    from app.models.phone_number import PhoneNumber
    from app.models.call_log import CallLog, CallOutcome
    from app.models.ai_worker import AIWorker
    from app.core.config import get_settings

    settings = get_settings()

    if not call_sid:
        return {
            "ok": False,
            "message": "Doorverbinden is op dit moment niet mogelijk. Bied aan om een collega te laten terugbellen.",
        }

    phone = (
        db.query(PhoneNumber)
        .filter(PhoneNumber.company_id == company_id, PhoneNumber.is_active == True)
        .first()
    )

    if not phone or not phone.transfer_enabled or not phone.transfer_number:
        return {
            "ok": False,
            "message": "Doorverbinden is niet beschikbaar. Bied aan om een collega te laten terugbellen.",
        }

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        transfer_twiml = (
            '<Response>'
            '<Say language="nl-NL">Een moment alstublieft, ik verbind u door.</Say>'
            f'<Dial>{phone.transfer_number}</Dial>'
            '</Response>'
        )

        client.calls(call_sid).update(twiml=transfer_twiml)

        if call_log_id:
            call_log = db.query(CallLog).filter(CallLog.id == call_log_id).first()
            if call_log:
                call_log.outcome = CallOutcome.TRANSFERRED
                if call_log.ai_worker_id:
                    worker = db.query(AIWorker).filter(AIWorker.id == call_log.ai_worker_id).first()
                    if worker:
                        worker.end_call()
                db.commit()

        logger.info(
            f"Call {call_sid} transferred to {phone.transfer_number} "
            f"(reason: {reason[:80]})"
        )

        return {
            "ok": True,
            "message": "Gesprek wordt doorverbonden.",
        }

    except Exception as e:
        logger.error(f"Failed to transfer call {call_sid}: {e}", exc_info=True)
        return {
            "ok": False,
            "message": "Doorverbinden is op dit moment niet mogelijk. Bied aan om een collega te laten terugbellen.",
        }
