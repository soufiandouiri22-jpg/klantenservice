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
from app.services.website_indexer import VectorStore

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
                if formatted else "Er zijn geen beschikbare momenten in deze periode."
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
    }


def tool_search_knowledge(
    db: Session,
    company_id: str,
    query: str,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Search company knowledge base using RAG (vector similarity).

    Priority: website/landing page content first (vector search),
    then ExampleAnswers as supplementary detail.

    Returns:
        Dict with ok, results (list of content+url), message
    """
    if not query.strip():
        return {
            "ok": True,
            "results": [],
            "message": "Geen zoekopdracht opgegeven."
        }

    logger.info(f"[search_knowledge] query={query!r} company={company_id}")

    vector_results = []
    qa_results = []

    # 1. Vector search FIRST — website/landing page is the primary source
    try:
        store = VectorStore(company_id, db)
        chunks = store.search(query, website_id=None, limit=limit, db=db)

        if chunks:
            vector_results = [
                {
                    "content": c.get("content", "")[:1000],
                    "url": c.get("metadata", {}).get("url", ""),
                    "title": c.get("metadata", {}).get("title", ""),
                }
                for c in chunks
            ]
    except Exception as e:
        logger.error(f"Error searching vector store: {e}")

    # 2. ExampleAnswers SECOND — supplementary detail for follow-up depth
    try:
        from app.models.training import ExampleAnswer
        query_lower = query.lower()
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
            if query_lower in (qa.question or "").lower() or any(
                query_lower in (v or "").lower() for v in (qa.question_variations or [])
            ):
                qa_results.append({
                    "content": f"Vraag: {qa.question}\nAntwoord: {qa.answer}",
                    "url": "",
                    "title": qa.category or "Voorbeeldantwoord",
                })
    except Exception:
        logger.warning("Failed to search ExampleAnswers", exc_info=True)

    results = vector_results + qa_results
    max_results = limit + 3

    logger.info(
        f"[search_knowledge] vector={len(vector_results)} "
        f"qa={len(qa_results)} total={len(results)} "
        f"(returning max {max_results})"
    )

    if not results:
        return {
            "ok": True,
            "results": [],
            "message": "Geen informatie beschikbaar. VERZIN NIETS. Zeg eerlijk dat je het antwoord op dit moment niet bij de hand hebt. Bied aan om een notitie achter te laten zodat een collega de klant zo snel mogelijk terugbelt met het antwoord. Bevestig het telefoonnummer."
        }

    return {
        "ok": True,
        "results": results[:max_results],
        "message": f"{len(results)} relevante resultaten gevonden."
    }


def tool_get_prices(
    db: Session,
    company_id: str,
    topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get price information from knowledge base.
    
    Args:
        db: Database session
        company_id: Company UUID
        topic: Specific topic to search for (e.g., "knippen", "behandeling X")
        
    Returns:
        Dict with ok, prices (list of content), message
    """
    # Build query for price-related content
    query = topic or "prijzen tarieven kosten"
    if topic and "prijs" not in topic.lower():
        query = f"{topic} prijs tarief kosten"
    
    try:
        store = VectorStore(company_id, db)
        chunks = store.search(query, website_id=None, limit=3, db=db)
        
        if not chunks:
            return {
                "ok": True,
                "prices": [],
                "message": "Geen prijsinformatie gevonden. Vraag de klant om contact op te nemen voor prijzen."
            }
        
        # Extract price-related content
        prices = []
        for c in chunks:
            content = c.get("content", "")
            # Only include if it likely contains price info
            if any(word in content.lower() for word in ["€", "euro", "prijs", "tarief", "kost"]):
                prices.append(content[:300])
        
        if not prices:
            return {
                "ok": True,
                "prices": [],
                "message": "Geen specifieke prijsinformatie gevonden voor dit onderwerp."
            }
        
        return {
            "ok": True,
            "prices": prices,
            "message": f"Prijsinformatie gevonden."
        }
        
    except Exception as e:
        logger.error(f"Error getting prices: {e}")
        return {
            "ok": False,
            "prices": [],
            "message": "Er ging iets mis bij het ophalen van prijsinformatie."
        }


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
