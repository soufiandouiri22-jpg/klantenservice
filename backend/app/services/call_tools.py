"""
klantenservice.ai - Call Tools for Orchestrator

Tool functions that the orchestrator calls during voice calls.
All "truth" (prices, availability, business info) comes from these tools.
PersonaPlex only speaks what the backend provides via these tool results.

Tools:
- check_availability: Get available calendar slots
- book_appointment: Create an appointment
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

from app.models.calendar_integration import CalendarIntegration
from app.models.appointment import Appointment, AppointmentStatus
from app.models.internal_note import InternalNote, NotePriority
from app.models.training import ExampleAnswer
from app.services.website_indexer import VectorStore

logger = logging.getLogger(__name__)


def tool_check_availability(
    db: Session,
    company_id: str,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    duration_minutes: int = 30,
    ai_worker_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get available time slots from the AI worker's linked calendar.
    
    Args:
        db: Database session
        company_id: Company UUID
        start_date: Start of availability window
        end_date: End of availability window (default: 7 days from start)
        duration_minutes: Appointment duration in minutes
        ai_worker_id: AI worker UUID (used to find worker-specific calendar)
        
    Returns:
        Dict with ok, slots (list of datetime strings), calendar_name
    """
    # Get the calendar linked to this AI worker (strict 1:1)
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
            "message": "Er is geen agenda gekoppeld. Vraag de klant om later terug te bellen.",
            "slots": []
        }
    
    # Determine end date
    end = end_date or (start_date + timedelta(days=7))
    
    # Get availability rules from calendar (or use defaults)
    rules = calendar.availability_rules or {}
    default_hours = rules.get("available_hours", {})
    
    # Generate available slots (mock implementation - in production, check actual calendar)
    # TODO: Integrate with actual calendar APIs (Google, Microsoft, CalDAV)
    slots = []
    current = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    # If start_date is today and past 9:00, start from next available slot
    if current < start_date:
        current = start_date.replace(minute=0, second=0, microsecond=0)
        # Round up to next 30-minute slot
        if current.minute > 0 and current.minute < 30:
            current = current.replace(minute=30)
        elif current.minute > 30:
            current = current.replace(minute=0) + timedelta(hours=1)
    
    while current < end and len(slots) < 20:
        # Skip weekends
        if current.weekday() < 5:
            # Business hours: 9:00 - 17:00
            if 9 <= current.hour < 17:
                slots.append(current.strftime("%Y-%m-%d %H:%M"))
        
        current += timedelta(minutes=30)
        
        # Move to next day if past business hours
        if current.hour >= 17:
            current = current.replace(hour=9, minute=0) + timedelta(days=1)
    
    return {
        "ok": True,
        "slots": slots[:20],
        "calendar_id": str(calendar.id),
        "calendar_name": calendar.name,
        "message": f"Er zijn {len(slots)} beschikbare momenten gevonden."
    }


def tool_book_appointment(
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
    Create an appointment in the calendar.
    
    Args:
        db: Database session
        company_id: Company UUID
        calendar_integration_id: Calendar UUID
        starts_at: Appointment start time
        ends_at: Appointment end time
        customer_name: Customer's name
        title: Appointment title
        customer_phone: Customer phone (from call)
        customer_email: Customer email (if provided)
        call_log_id: Link to the call log
        
    Returns:
        Dict with ok, appointment_id, starts_at, customer_name
    """
    # Verify calendar exists and belongs to company
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
    
    # Calculate duration
    duration = int((ends_at - starts_at).total_seconds() / 60)
    
    # Create appointment
    appointment = Appointment(
        id=uuid4(),
        company_id=UUID(company_id),
        calendar_integration_id=UUID(calendar_integration_id),
        call_log_id=UUID(call_log_id) if call_log_id else None,
        title=title,
        description=f"Geboekt tijdens telefoongesprek met {customer_name}",
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
    
    # Create notification for new appointment
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
        pass  # Don't fail the appointment creation if notification fails
    
    # Format datetime for speech
    day_names = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    day_name = day_names[starts_at.weekday()]
    
    return {
        "ok": True,
        "appointment_id": str(appointment.id),
        "starts_at": starts_at.isoformat(),
        "starts_at_readable": f"{day_name} {starts_at.day} {starts_at.strftime('%B')} om {starts_at.strftime('%H:%M')}",
        "customer_name": customer_name,
        "message": f"Afspraak ingepland op {day_name} om {starts_at.strftime('%H:%M')} voor {customer_name}."
    }


def tool_search_knowledge(
    db: Session,
    company_id: str,
    query: str,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Search company knowledge base using RAG (vector similarity).
    
    Args:
        db: Database session
        company_id: Company UUID
        query: Search query
        limit: Max number of results
        
    Returns:
        Dict with ok, results (list of content+url), message
    """
    if not query.strip():
        return {
            "ok": True,
            "results": [],
            "message": "Geen zoekopdracht opgegeven."
        }
    
    try:
        store = VectorStore(company_id, db)
        chunks = store.search(query, website_id=None, limit=limit, db=db)
        
        if not chunks:
            return {
                "ok": True,
                "results": [],
                "message": "Geen relevante informatie gevonden in de kennisbank."
            }
        
        results = []
        for c in chunks:
            results.append({
                "content": c.get("content", "")[:500],  # Limit content length
                "url": c.get("metadata", {}).get("url", ""),
                "title": c.get("metadata", {}).get("title", "")
            })
        
        return {
            "ok": True,
            "results": results,
            "message": f"{len(results)} relevante resultaten gevonden."
        }
        
    except Exception as e:
        logger.error(f"Error searching knowledge: {e}")
        return {
            "ok": False,
            "results": [],
            "message": "Er ging iets mis bij het zoeken in de kennisbank."
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
        chunks = store.search(query, website_id=None, limit=5, db=db)
        
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
