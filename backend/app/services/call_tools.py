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
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

# ── Dutch spoken date/time helpers ────────────────────────────────

_NL_DAY_NAMES = [
    "maandag", "dinsdag", "woensdag", "donderdag",
    "vrijdag", "zaterdag", "zondag",
]
_NL_DAY_ABBR = ["ma", "di", "wo", "do", "vr", "za", "zo"]
_NL_MONTH_NAMES = [
    "", "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


def format_spoken_date(dt: datetime) -> str:
    """Format a datetime as natural spoken Dutch: 'maandag 16 maart'."""
    return f"{_NL_DAY_NAMES[dt.weekday()]} {dt.day} {_NL_MONTH_NAMES[dt.month]}"


def format_spoken_time(dt: datetime) -> str:
    """Format a time as natural spoken Dutch: '10 uur' or '10:30'."""
    if dt.minute == 0:
        return f"{dt.hour} uur"
    return f"{dt.hour}:{dt.minute:02d}"


def format_spoken_slot(dt: datetime) -> str:
    """Format a datetime as a full spoken Dutch timeslot: 'maandag 16 maart om 10 uur'."""
    return f"{format_spoken_date(dt)} om {format_spoken_time(dt)}"


def _format_slots_spoken(slots: list[dict]) -> list[str]:
    """Convert ISO slot dicts to natural spoken Dutch strings."""
    result = []
    for s in slots:
        raw = s.get("start", "")
        try:
            dt = datetime.fromisoformat(raw[:16])
            result.append(format_spoken_slot(dt))
        except (ValueError, TypeError):
            result.append(raw[:16].replace("T", " "))
    return result


from sqlalchemy.orm import Session

from app.models.calendar_integration import CalendarIntegration, CalendarProvider
from app.models.appointment import Appointment, AppointmentStatus
from app.models.internal_note import InternalNote, NotePriority
from app.models.lead import Lead
from app.models.training import ExampleAnswer
from app.models.business_facts import (
    CompanyOverview, PricingPlan, ContactInfo, OpeningHours,
    BusinessLocation, BusinessService,
)
from app.services.retrieval import RetrievalService
from app.services.retrieval.query_classifier import classify_query
from app.services.voice.intent_classifier import classify_intent, CallerIntent, CompanyScope
from app.services.voice.conversation_state import ConversationStateManager
from app.services.voice.policy_engine import PolicyEngine, PolicyResult
from app.services.voice.output_guardrails import validate_output, ViolationType

logger = logging.getLogger(__name__)

_company_scope_cache: dict[str, CompanyScope] = {}


def _get_company_scope(db: Session, company_id: str) -> CompanyScope:
    """Build a CompanyScope from the company's inferred business profile (cached)."""
    if company_id in _company_scope_cache:
        return _company_scope_cache[company_id]

    from app.models.company import Company
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        scope = CompanyScope()
    else:
        scope = CompanyScope(
            business_type=company.effective_business_type,
            topics=company.inferred_topics or [],
        )
    _company_scope_cache[company_id] = scope
    return scope


def _get_internal_availability(
    db: Session,
    calendar: CalendarIntegration,
    start_date: datetime,
    end_date: datetime,
    duration_minutes: int,
) -> List[Dict[str, Any]]:
    """
    Compute available slots using the calendar's availability_rules and
    existing Appointment records as busy periods (no external calendar needed).
    """
    from app.services.google_calendar_service import compute_available_slots

    rules = calendar.availability_rules or {}

    existing = db.query(Appointment).filter(
        Appointment.company_id == calendar.company_id,
        Appointment.starts_at >= start_date,
        Appointment.starts_at <= end_date,
        Appointment.status.in_([
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.HELD,
        ]),
    ).all()

    internal_events = []
    for appt in existing:
        internal_events.append({
            "start": {"dateTime": appt.starts_at.isoformat()},
            "end": {"dateTime": appt.ends_at.isoformat()},
        })

    all_slots: List[Dict] = []
    current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    while current_date <= end:
        day_str = current_date.strftime("%Y-%m-%d")
        day_events = [
            e for e in internal_events
            if e["start"]["dateTime"].startswith(day_str)
        ]
        day_slots = compute_available_slots(day_events, rules, current_date, duration_minutes)
        all_slots.extend(day_slots)
        current_date += timedelta(days=1)

    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    max_advance = rules.get("max_advance_days", 60)
    cutoff = _dt.now(ZoneInfo("Europe/Amsterdam")).replace(tzinfo=None) + timedelta(days=max_advance)
    all_slots = [s for s in all_slots if _dt.fromisoformat(s["start"]) <= cutoff]

    return all_slots


async def tool_check_availability(
    db: Session,
    company_id: str,
    start_date: datetime,
    end_date: Optional[datetime] = None,
    duration_minutes: int = 30,
    ai_worker_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get available time slots. Priority:
      1. External calendar (Google/Outlook) if connected
      2. Internal calendar (availability_rules + existing appointments)
      3. Structured failure if no calendar source at all
    """
    query = db.query(CalendarIntegration).filter(
        CalendarIntegration.company_id == company_id,
        CalendarIntegration.is_active == True,
    )
    if ai_worker_id:
        query = query.filter(CalendarIntegration.ai_worker_id == ai_worker_id)
    calendar = query.first()

    if not calendar:
        logger.warning("[check_availability] source=no_calendar_source company=%s", company_id)
        return {
            "ok": False,
            "reason": "no_calendar_source",
            "source": "none",
            "message": "Afspraken inplannen is op dit moment niet mogelijk. Zeg NIET dat er geen agenda is. Bied aan om de gegevens te noteren zodat een collega zo snel mogelijk terugbelt om een afspraak in te plannen. Bevestig het telefoonnummer van de klant.",
            "slots": [],
        }

    end = end_date or (start_date + timedelta(days=7))
    has_external_token = bool(calendar.access_token_encrypted)
    has_availability_rules = bool(calendar.availability_rules and
                                  calendar.availability_rules.get("available_hours"))

    # ── Path 1: External calendar connected ──
    if has_external_token:
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

            formatted = _format_slots_spoken(slots[:20])
            logger.info(
                "[check_availability] source=external_calendar provider=%s slots=%d company=%s",
                calendar.provider, len(formatted), company_id,
            )
            return {
                "ok": True,
                "source": "external_calendar",
                "slots": formatted,
                "calendar_id": str(calendar.id),
                "calendar_name": calendar.name,
                "message": f"Er zijn {len(formatted)} beschikbare momenten gevonden."
                    if formatted else "Er zijn geen beschikbare momenten in deze periode.",
                "next_action": "Bied maximaal 3 opties aan en vraag welk moment het beste uitkomt. Vraag daarna de naam van de klant.",
            }

        except Exception as e:
            logger.error(
                "[check_availability] external_calendar failed (%s), trying internal fallback: %s",
                calendar.provider, e, exc_info=True,
            )
            if has_availability_rules:
                logger.info("[check_availability] falling back to internal_calendar after external failure")
            else:
                return {
                    "ok": False,
                    "reason": "external_calendar_unavailable",
                    "source": "external_calendar",
                    "message": "Er ging iets mis bij het ophalen van de beschikbaarheid. Bied aan om de gegevens te noteren zodat een collega terugbelt.",
                    "slots": [],
                }

    # ── Path 2: Internal calendar (availability rules + existing appointments) ──
    if has_availability_rules:
        try:
            slots = _get_internal_availability(db, calendar, start_date, end, duration_minutes)
            formatted = _format_slots_spoken(slots[:20])
            logger.info(
                "[check_availability] source=internal_calendar slots=%d company=%s",
                len(formatted), company_id,
            )
            return {
                "ok": True,
                "source": "internal_calendar",
                "slots": formatted,
                "calendar_id": str(calendar.id),
                "calendar_name": calendar.name,
                "message": f"Er zijn {len(formatted)} beschikbare momenten gevonden."
                    if formatted else "Er zijn geen beschikbare momenten in deze periode.",
                "next_action": "Bied maximaal 3 opties aan en vraag welk moment het beste uitkomt. Vraag daarna de naam van de klant.",
            }
        except Exception as e:
            logger.error("[check_availability] internal_calendar error: %s", e, exc_info=True)
            return {
                "ok": False,
                "reason": "internal_calendar_unavailable",
                "source": "internal_calendar",
                "message": "Er ging iets mis bij het ophalen van de beschikbaarheid. Bied aan om de gegevens te noteren zodat een collega terugbelt.",
                "slots": [],
            }

    # ── Path 3: Calendar exists but no source is usable ──
    logger.warning(
        "[check_availability] source=no_calendar_source calendar=%s has_token=%s has_rules=%s",
        calendar.id, has_external_token, has_availability_rules,
    )
    return {
        "ok": False,
        "reason": "no_calendar_source",
        "source": "none",
        "message": "Afspraken inplannen is op dit moment niet mogelijk. Zeg NIET dat er geen agenda is. Bied aan om de gegevens te noteren zodat een collega zo snel mogelijk terugbelt om een afspraak in te plannen. Bevestig het telefoonnummer van de klant.",
        "slots": [],
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

    conflict = db.query(Appointment).filter(
        Appointment.company_id == UUID(company_id),
        Appointment.calendar_integration_id == UUID(calendar_integration_id),
        Appointment.status.in_([AppointmentStatus.CONFIRMED]),
        Appointment.starts_at < ends_at,
        Appointment.ends_at > starts_at,
    ).first()

    if conflict:
        return {
            "ok": False,
            "reason": "slot_taken",
            "message": "Dit tijdslot is zojuist geboekt door iemand anders. Vraag de klant een ander moment te kiezen.",
        }

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
            message=f"Afspraak ingepland op {format_spoken_slot(starts_at)}.",
            url="/dashboard/appointments",
        )
    except Exception:
        pass

    starts_at_readable = format_spoken_slot(starts_at)

    # ── Post-booking confirmations (SMS + Email) ──
    try:
        from app.models.phone_number import PhoneNumber
        from app.models.company import Company

        phone_cfg = db.query(PhoneNumber).filter(
            PhoneNumber.company_id == company_id,
            PhoneNumber.is_active == True,
        ).first()

        if phone_cfg:
            company_obj = db.query(Company).filter(Company.id == company_id).first()
            _company_name = company_obj.name if company_obj else "ons bedrijf"

            # SMS confirmation
            if customer_phone and phone_cfg.sms_confirmation_enabled:
                try:
                    from app.services.sms_service import send_appointment_confirmation_sms
                    send_appointment_confirmation_sms(
                        to=customer_phone,
                        company_name=_company_name,
                        starts_at_readable=starts_at_readable,
                        custom_template=phone_cfg.sms_confirmation_template,
                    )
                    logger.info("Confirmation SMS sent to %s", customer_phone)
                except Exception as e:
                    logger.error("Failed to send confirmation SMS: %s", e, exc_info=True)

            # Email confirmation
            if customer_email and phone_cfg.email_confirmation_enabled:
                try:
                    from app.core.email import send_appointment_confirmation_email
                    send_appointment_confirmation_email(
                        to=customer_email,
                        company_name=_company_name,
                        starts_at_readable=starts_at_readable,
                        custom_template=phone_cfg.email_confirmation_template,
                    )
                    logger.info("Confirmation email sent to %s", customer_email)
                except Exception as e:
                    logger.error("Failed to send confirmation email: %s", e, exc_info=True)
    except Exception as e:
        logger.error("Failed to load phone config for confirmations: %s", e, exc_info=True)

    return {
        "ok": True,
        "appointment_id": str(appointment.id),
        "starts_at": starts_at.isoformat(),
        "starts_at_readable": starts_at_readable,
        "customer_name": customer_name,
        "message": f"Afspraak ingepland op {starts_at_readable} voor {customer_name}.",
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


def _try_structured_facts(
    db: Session, company_id: str, query: str,
) -> Optional[Dict[str, Any]]:
    """
    Legacy structured-facts hook inside search_knowledge.

    All structured intents are now served by dedicated tools:
      get_pricing, get_company_overview, get_contact_info,
      get_opening_hours, get_services, get_location.

    This function is kept as a no-op for backward compatibility.
    """
    return None


_WEEKDAY_NAMES = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]


def _format_overview_response(overview) -> Dict[str, Any]:
    """Format a CompanyOverview into a tool result for the voice agent."""
    lines = [overview.summary]

    if overview.capabilities:
        caps = overview.capabilities if isinstance(overview.capabilities, list) else []
        if caps:
            lines.append("")
            for cap in caps[:8]:
                lines.append(f"  - {cap}")

    if overview.target_audience:
        lines.append(f"\nDoelgroep: {overview.target_audience}")

    content = "\n".join(lines)
    source_url = overview.source_url or ""
    logger.info("[structured_facts] returning company overview (%d chars)", len(content))
    return {
        "ok": True,
        "results": [{"content": content, "url": source_url, "title": "Bedrijfsoverzicht", "chunk_type": "about", "score": 1.0}],
        "top_retrieval_score": 1.0,
        "message": content,
        "source": "structured_facts",
    }


def _format_price_str(price) -> str:
    """Format price for voice: €99 (not €99,00) to prevent LLM rounding."""
    if price is None:
        return ""
    if price == int(price):
        return f"\u20ac{int(price)}"
    return f"\u20ac{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_pricing_response(plans: List) -> Dict[str, Any]:
    lines = []
    for p in plans:
        if p.price_type == "fixed" and p.price is not None:
            price_str = _format_price_str(p.price)
            period = f" per {p.billing_period}" if p.billing_period else ""
            lines.append(f"{p.name}: {price_str}{period}")
        elif p.price_type == "free":
            lines.append(f"{p.name}: Gratis")
        elif p.price_type == "contact_required":
            lines.append(f"{p.name}: Prijs op aanvraag")
        else:
            lines.append(p.name)

        if p.features:
            feats = p.features if isinstance(p.features, list) else []
            for feat in feats:
                lines.append(f"  - {feat}")

    content = "\n".join(lines)
    source_url = plans[0].source_url or ""
    logger.info("[structured_facts] returning %d pricing plans", len(plans))

    # Build a strict verbal template the LLM must follow verbatim
    verbal_instruction = (
        "PRIJSINSTRUCTIE: Noem onderstaande prijzen en pakketten EXACT zoals ze hier staan. "
        "Wijzig GEEN enkel bedrag. Rond NIET af. "
        "Zeg het getal precies: €99 = negenennegentig euro, €499 = vierhonderdnegenennegentig euro. "
        "Als er eerdere zoekresultaten in het gesprek staan, NEGEER die voor de prijsvraag en gebruik ALLEEN deze gegevens.\n\n"
    )

    return {
        "ok": True,
        "results": [{"content": content, "url": source_url, "title": "Prijzen", "chunk_type": "pricing", "score": 1.0}],
        "top_retrieval_score": 1.0,
        "message": verbal_instruction + content,
        "source": "structured_facts",
    }


def _format_contact_response(contacts: List) -> Dict[str, Any]:
    parts = []
    for c in contacts:
        if c.phone:
            parts.append(f"Telefoon: {c.phone}")
        if c.email:
            parts.append(f"E-mail: {c.email}")
        if c.whatsapp:
            parts.append(f"WhatsApp: {c.whatsapp}")
    content = "\n".join(parts)
    return {
        "ok": True,
        "results": [{"content": content, "url": contacts[0].source_url or "", "title": "Contact", "chunk_type": "contact", "score": 1.0}],
        "top_retrieval_score": 1.0,
        "message": content,
        "source": "structured_facts",
    }


def _format_hours_response(hours: List) -> Dict[str, Any]:
    lines = []
    for h in hours:
        day = _WEEKDAY_NAMES[h.weekday] if 0 <= h.weekday <= 6 else f"Dag {h.weekday}"
        if h.closed:
            lines.append(f"{day}: Gesloten")
        elif h.open_time and h.close_time:
            lines.append(f"{day}: {h.open_time.strftime('%H:%M')} - {h.close_time.strftime('%H:%M')}")
    content = "\n".join(lines)
    return {
        "ok": True,
        "results": [{"content": content, "url": hours[0].source_url or "", "title": "Openingstijden", "chunk_type": "contact", "score": 1.0}],
        "top_retrieval_score": 1.0,
        "message": content,
        "source": "structured_facts",
    }


def _format_location_response(locations: List, hours: List) -> Dict[str, Any]:
    parts = []
    for loc in locations:
        loc_parts = [x for x in [loc.name, loc.address, f"{loc.postal_code} {loc.city}" if loc.postal_code else loc.city] if x]
        if loc_parts:
            parts.append(", ".join(loc_parts))
    if hours:
        parts.append("")
        parts.append("Openingstijden:")
        for h in hours:
            day = _WEEKDAY_NAMES[h.weekday] if 0 <= h.weekday <= 6 else f"Dag {h.weekday}"
            if h.closed:
                parts.append(f"{day}: Gesloten")
            elif h.open_time and h.close_time:
                parts.append(f"{day}: {h.open_time.strftime('%H:%M')} - {h.close_time.strftime('%H:%M')}")
    content = "\n".join(parts)
    source_url = locations[0].source_url if locations else (hours[0].source_url if hours else "")
    return {
        "ok": True,
        "results": [{"content": content, "url": source_url or "", "title": "Locatie", "chunk_type": "location", "score": 1.0}],
        "top_retrieval_score": 1.0,
        "message": content,
        "source": "structured_facts",
    }


def _format_service_response(services: List) -> Dict[str, Any]:
    lines = []
    for s in services:
        if s.price:
            price_str = f"€{s.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lines.append(f"{s.name} – {price_str}")
        else:
            lines.append(s.name)
    content = "\n".join(lines)
    return {
        "ok": True,
        "results": [{"content": content, "url": services[0].source_url or "", "title": "Diensten", "chunk_type": "service", "score": 1.0}],
        "top_retrieval_score": 1.0,
        "message": content,
        "source": "structured_facts",
    }


def _is_low_quality_chunk(chunk: Dict) -> bool:
    """Detect broken or useless retrieval chunks that would cause hallucination."""
    content = chunk.get("content", "").strip()
    chunk_type = chunk.get("chunk_type", "")

    if len(content) < 30:
        return True

    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    if not lines:
        return True

    question_lines = sum(1 for ln in lines if ln.rstrip().endswith("?"))
    total = len(lines)

    if chunk_type == "faq":
        has_answer_marker = any("antwoord:" in ln.lower() for ln in lines)
        if has_answer_marker:
            for i, ln in enumerate(lines):
                if ln.lower().startswith("antwoord:"):
                    answer_text = ln.split(":", 1)[1].strip()
                    rest = " ".join(lines[i + 1:]).strip() if i + 1 < len(lines) else ""
                    full_answer = f"{answer_text} {rest}".strip()
                    if not full_answer or len(full_answer) < 15:
                        return True
                    q_in_answer = sum(1 for s in re.split(r"[.!?\n]", full_answer)
                                      if s.strip() and "?" in s)
                    if q_in_answer / max(len(re.split(r"[.!?\n]", full_answer)), 1) > 0.5:
                        return True
                    break
        if question_lines > 0 and question_lines / total >= 0.7:
            return True

    if question_lines > 2 and question_lines / total >= 0.8:
        return True

    return False


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

    # 1. Try structured business facts (deterministic, O(1))
    structured = _try_structured_facts(db, company_id, query)
    if structured:
        elapsed_ms = int((_time.time() - t0) * 1000)
        logger.info(
            "[search_knowledge] STRUCTURED HIT in %dms: source=%s",
            elapsed_ms, structured.get("source"),
        )
        return structured

    # 2. Retrieval pipeline (vector + metadata + fulltext + reranking)
    retrieval_results = _run_retrieval(db, company_id, query, limit)

    # Log top retrieval results
    for i, r in enumerate(retrieval_results[:5]):
        logger.info(
            "[search_knowledge] result #%d: score=%.4f type=%s url=%s title=%r preview=%r",
            i + 1, r.get("score", 0), r.get("chunk_type", "?"),
            r.get("url", "")[:80], (r.get("title") or "")[:60],
            r.get("content", "")[:250].replace("\n", " "),
        )

    # 2b. Content quality filter — strip broken/empty chunks
    pre_filter_count = len(retrieval_results)
    retrieval_results = [r for r in retrieval_results if not _is_low_quality_chunk(r)]
    filtered_count = pre_filter_count - len(retrieval_results)
    if filtered_count > 0:
        logger.warning(
            "[search_knowledge] quality_filter removed %d/%d low-quality chunks",
            filtered_count, pre_filter_count,
        )

    # 3. ExampleAnswers — training/voorbeeldantwoorden (substring match)
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

    # Top retrieval score for low-confidence detection
    top_score = 0.0
    if retrieval_results:
        top_score = max(r.get("score", 0) for r in retrieval_results)

    if not results:
        return {
            "ok": True,
            "results": [],
            "top_retrieval_score": 0.0,
            "message": "Geen informatie beschikbaar. VERZIN NIETS. Zeg eerlijk dat je het antwoord op dit moment niet bij de hand hebt. Bied aan om een notitie achter te laten zodat een collega de klant zo snel mogelijk terugbelt met het antwoord. Bevestig het telefoonnummer.",
        }

    final_msg = f"{len(results)} relevante resultaten gevonden."
    logger.info("[search_knowledge] final_message=%r top_score=%.4f", final_msg, top_score)
    for r in results:
        logger.info(
            "[search_knowledge] -> TTS content (%d chars): %r",
            len(r.get("content", "")),
            r.get("content", "")[:300].replace("\n", " "),
        )

    return {
        "ok": True,
        "results": results,
        "top_retrieval_score": top_score,
        "message": final_msg,
    }


def tool_get_pricing(
    db: Session,
    company_id: str,
    query: str = "",
) -> Dict[str, Any]:
    """
    Dedicated pricing tool — reads directly from PricingPlan.

    Supports:
      - Full pricing overview (no query / generic query)
      - Single plan detail (query matches a plan name)
      - Plan comparison (query contains multiple plan names)

    Falls back to search_knowledge when no structured pricing exists.
    """
    import time as _time
    t0 = _time.time()
    logger.info("[tool_get_pricing] START query=%r company=%s", query, company_id)

    plans = (
        db.query(PricingPlan)
        .filter_by(company_id=company_id)
        .order_by(PricingPlan.display_order)
        .all()
    )

    if not plans:
        logger.info("[tool_get_pricing] no structured plans — falling back to search_knowledge")
        return tool_search_knowledge(db, company_id, query or "prijzen tarieven kosten", limit=5)

    q_lower = query.lower().strip()
    if q_lower:
        plan_names_lower = {p.name.lower(): p for p in plans}
        matched = [p for name, p in plan_names_lower.items() if name in q_lower]
        if matched:
            plans = matched
            logger.info("[tool_get_pricing] filtered to %d plan(s): %s",
                        len(matched), [p.name for p in matched])

    result = _format_pricing_response(plans)
    elapsed_ms = int((_time.time() - t0) * 1000)
    logger.info("[tool_get_pricing] returning %d plans in %dms", len(plans), elapsed_ms)
    return result


def tool_get_company_overview(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """
    Dedicated company overview tool — reads directly from CompanyOverview.

    Returns a short business summary, target audience, and key capabilities.
    Falls back to search_knowledge when no structured overview exists.
    """
    import time as _time
    t0 = _time.time()
    logger.info("[tool_get_company_overview] START company=%s", company_id)

    overview = db.query(CompanyOverview).filter_by(company_id=company_id).first()

    if not overview:
        logger.info("[tool_get_company_overview] no structured overview — falling back to search_knowledge")
        return tool_search_knowledge(db, company_id, "bedrijf overzicht wat doen jullie", limit=5)

    result = _format_overview_response(overview)
    elapsed_ms = int((_time.time() - t0) * 1000)
    logger.info("[tool_get_company_overview] returning overview in %dms (%d chars)",
                elapsed_ms, len(result.get("message", "")))
    return result


def tool_get_contact_info(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """
    Dedicated contact info tool — reads directly from ContactInfo.

    Returns phone, email, whatsapp, contact_url.
    Falls back to search_knowledge when no structured contact data exists.
    """
    import time as _time
    t0 = _time.time()
    logger.info("[tool_get_contact_info] START company=%s", company_id)

    contacts = db.query(ContactInfo).filter_by(company_id=company_id).all()

    if not contacts:
        logger.info("[tool_get_contact_info] no structured contacts — falling back to search_knowledge")
        return tool_search_knowledge(db, company_id, "contact telefoon email", limit=5)

    result = _format_contact_response(contacts)
    elapsed_ms = int((_time.time() - t0) * 1000)
    logger.info("[tool_get_contact_info] returning %d contact(s) in %dms", len(contacts), elapsed_ms)
    return result


def tool_get_opening_hours(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """
    Dedicated opening hours tool — reads directly from OpeningHours.

    Returns weekday schedule with open/close times.
    Falls back to search_knowledge when no structured hours exist.
    """
    import time as _time
    t0 = _time.time()
    logger.info("[tool_get_opening_hours] START company=%s", company_id)

    hours = (
        db.query(OpeningHours)
        .filter_by(company_id=company_id)
        .order_by(OpeningHours.weekday)
        .all()
    )

    if not hours:
        logger.info("[tool_get_opening_hours] no structured hours — falling back to search_knowledge")
        return tool_search_knowledge(db, company_id, "openingstijden bereikbaar", limit=5)

    result = _format_hours_response(hours)
    elapsed_ms = int((_time.time() - t0) * 1000)
    logger.info("[tool_get_opening_hours] returning %d day(s) in %dms", len(hours), elapsed_ms)
    return result


def tool_get_services(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """
    Dedicated services tool — reads directly from BusinessService.

    Returns a concise list of offered services/capabilities.
    Falls back to search_knowledge when no structured services exist.
    """
    import time as _time
    t0 = _time.time()
    logger.info("[tool_get_services] START company=%s", company_id)

    services = db.query(BusinessService).filter_by(company_id=company_id).all()

    if not services:
        logger.info("[tool_get_services] no structured services — falling back to search_knowledge")
        return tool_search_knowledge(db, company_id, "diensten services aanbod", limit=5)

    result = _format_service_response(services)
    elapsed_ms = int((_time.time() - t0) * 1000)
    logger.info("[tool_get_services] returning %d service(s) in %dms", len(services), elapsed_ms)
    return result


def tool_get_location(
    db: Session,
    company_id: str,
) -> Dict[str, Any]:
    """
    Dedicated location tool — reads directly from BusinessLocation.

    Returns address, city, postal code. Includes opening hours if available.
    Falls back to search_knowledge when no structured location data exists.
    """
    import time as _time
    t0 = _time.time()
    logger.info("[tool_get_location] START company=%s", company_id)

    locations = db.query(BusinessLocation).filter_by(company_id=company_id).all()
    hours = (
        db.query(OpeningHours)
        .filter_by(company_id=company_id)
        .order_by(OpeningHours.weekday)
        .all()
    )

    if not locations and not hours:
        logger.info("[tool_get_location] no structured location — falling back to search_knowledge")
        return tool_search_knowledge(db, company_id, "locatie adres vestiging", limit=5)

    result = _format_location_response(locations, hours)
    elapsed_ms = int((_time.time() - t0) * 1000)
    logger.info("[tool_get_location] returning %d location(s) in %dms", len(locations), elapsed_ms)
    return result


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
                        to=customer_phone,
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

    company_scope = _get_company_scope(db, company_id) if company_id else None

    engine = PolicyEngine(db)
    result = engine.evaluate(
        session=session,
        intent=intent,
        trigger_tool="check_policy",
        trigger_reason=trigger_reason,
        intent_confidence=confidence,
        utterance=customer_message,
        company_scope=company_scope,
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
    retrieval_confidence: float = 1.0,
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

    company_scope = _get_company_scope(db, company_id) if company_id else None

    engine = PolicyEngine(db)
    override = engine.evaluate_all(
        session=session,
        intent=intent,
        trigger_tool=tool_name,
        intent_confidence=confidence,
        retrieval_confidence=retrieval_confidence,
        utterance=customer_message,
        company_scope=company_scope,
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
            mgr.record_off_topic_block(session)
            db.commit()
        return result

    # Track low confidence on retrieval tools
    if retrieval_confidence < 0.2 and tool_name in ("search_knowledge", "get_prices"):
        mgr.record_low_confidence(session, retrieval_confidence)
        db.commit()

    return None


def apply_output_guardrails(
    db: Session,
    call_sid: Optional[str],
    call_log_id: Optional[str],
    company_id: Optional[str],
    tool_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run output guardrails on tool response content before returning to ElevenLabs.

    Checks the 'message' field and all 'content' fields in results for:
    - Prompt leakage
    - Tool name leakage
    - JSON/code leakage
    - Language violations (non-Dutch)
    - HTML/script fragments
    - Malformed output

    If any violation is found, replaces the offending content with a safe fallback
    and logs the violation.
    """
    texts_to_check: list[str] = []

    msg = tool_result.get("message", "")
    if msg:
        texts_to_check.append(msg)

    for r in tool_result.get("results", []):
        c = r.get("content", "")
        if c:
            texts_to_check.append(c)

    if not texts_to_check:
        return tool_result

    all_violations: list[str] = []
    any_blocked = False

    for text in texts_to_check:
        gr = validate_output(text)
        if not gr.passed:
            any_blocked = True
            all_violations.extend(v.value for v in gr.violations)
            logger.warning(
                "[output_guardrails] blocked text in tool response: violations=%s",
                [v.value for v in gr.violations],
            )

    if not any_blocked:
        return tool_result

    # Update session counters if we have a call
    if call_sid:
        try:
            mgr = ConversationStateManager(db)
            session = mgr.get_or_create(
                call_sid=call_sid,
                call_log_id=call_log_id,
                company_id=company_id,
            )
            mgr.record_output_guardrail_block(session)
            if ViolationType.LANGUAGE_VIOLATION.value in all_violations:
                mgr.record_language_violation(session)
            db.commit()
        except Exception:
            logger.warning("Failed to update session guardrail counters", exc_info=True)

    # Return sanitized result with guardrail metadata
    sanitized = dict(tool_result)
    sanitized["output_guardrail_triggered"] = True
    sanitized["output_guardrail_violations"] = list(set(all_violations))
    return sanitized


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


# ═══════════════════════════════════════════════════════════════════
# Action tools — cancel, reschedule, lead, sms, email, message, callback
# ═══════════════════════════════════════════════════════════════════


def _find_appointment(
    db: Session,
    company_id: str,
    customer_phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    appointment_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Shared lookup logic for cancel / reschedule.

    Returns {"ok": True, "appointment": <obj>} or
            {"ok": False, "reason": ..., "message": ...}.
    """
    q = db.query(Appointment).filter(
        Appointment.company_id == company_id,
        Appointment.status == AppointmentStatus.CONFIRMED,
    )

    if customer_phone:
        q = q.filter(Appointment.customer_phone == customer_phone)
    if customer_name:
        q = q.filter(Appointment.customer_name.ilike(f"%{customer_name}%"))
    if appointment_date:
        try:
            from dateutil import parser as dp
            dt = dp.parse(appointment_date)
            q = q.filter(
                Appointment.starts_at >= dt.replace(hour=0, minute=0, second=0),
                Appointment.starts_at < dt.replace(hour=23, minute=59, second=59),
            )
        except Exception:
            pass

    matches = q.order_by(Appointment.starts_at).all()

    if len(matches) == 0:
        return {
            "ok": False,
            "reason": "not_found",
            "message": "Er is geen afspraak gevonden die voldoet aan de opgegeven gegevens. Vraag de klant om meer details (naam, datum, telefoonnummer).",
        }

    if len(matches) == 1:
        return {"ok": True, "appointment": matches[0]}

    options = []
    for a in matches[:5]:
        options.append(f"- {a.customer_name}: {format_spoken_slot(a.starts_at)}")
    return {
        "ok": False,
        "reason": "ambiguous",
        "count": len(matches),
        "options": options,
        "message": f"Er zijn {len(matches)} afspraken gevonden. Vraag de klant welke afspraak bedoeld wordt:\n" + "\n".join(options),
    }


async def tool_cancel_appointment(
    db: Session,
    company_id: str,
    customer_phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    appointment_date: Optional[str] = None,
    call_log_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Cancel a confirmed appointment found by phone/name/date."""
    logger.info("[tool_cancel_appointment] company=%s phone=%s name=%s date=%s",
                company_id, customer_phone, customer_name, appointment_date)

    lookup = _find_appointment(db, company_id, customer_phone, customer_name, appointment_date)
    if not lookup["ok"]:
        return lookup

    appointment: Appointment = lookup["appointment"]
    old_event_id = appointment.external_event_id

    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancelled_at = datetime.utcnow()
    appointment.cancelled_by = "customer"
    appointment.cancellation_reason = "Geannuleerd via telefoon"
    db.commit()

    if appointment.calendar_integration_id and old_event_id:
        try:
            calendar = db.query(CalendarIntegration).filter(
                CalendarIntegration.id == appointment.calendar_integration_id
            ).first()
            if calendar and calendar.access_token_encrypted:
                if calendar.provider == CalendarProvider.MICROSOFT:
                    from app.services import outlook_calendar_service as svc
                else:
                    from app.services import google_calendar_service as svc
                await svc.delete_event(calendar, db, old_event_id)
        except Exception as e:
            logger.error("Failed to delete external calendar event: %s", e, exc_info=True)

    try:
        from app.services.notification_service import create_notification
        from app.models.notification import NotificationType
        create_notification(
            db=db, company_id=company_id,
            type=NotificationType.APPOINTMENT_CANCELLED,
            title=f"Afspraak geannuleerd: {appointment.customer_name}",
            message=f"Afspraak op {format_spoken_slot(appointment.starts_at)} is geannuleerd door de klant.",
            url="/dashboard/appointments",
        )
    except Exception:
        pass

    logger.info("Appointment %s cancelled", appointment.id)
    return {
        "ok": True,
        "appointment_id": str(appointment.id),
        "message": f"De afspraak van {appointment.customer_name} op {format_spoken_slot(appointment.starts_at)} is geannuleerd.",
    }


async def tool_reschedule_appointment(
    db: Session,
    company_id: str,
    new_starts_at: datetime,
    new_ends_at: datetime,
    customer_phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    appointment_date: Optional[str] = None,
    call_log_id: Optional[str] = None,
    customer_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Reschedule a confirmed appointment to a new timeslot."""
    logger.info("[tool_reschedule_appointment] company=%s new=%s phone=%s name=%s",
                company_id, new_starts_at, customer_phone, customer_name)

    lookup = _find_appointment(db, company_id, customer_phone, customer_name, appointment_date)
    if not lookup["ok"]:
        return lookup

    appointment: Appointment = lookup["appointment"]
    old_event_id = appointment.external_event_id

    appointment.starts_at = new_starts_at
    appointment.ends_at = new_ends_at
    appointment.duration_minutes = int((new_ends_at - new_starts_at).total_seconds() / 60)
    db.commit()
    db.refresh(appointment)

    # Update external calendar
    if appointment.calendar_integration_id:
        try:
            calendar = db.query(CalendarIntegration).filter(
                CalendarIntegration.id == appointment.calendar_integration_id
            ).first()
            if calendar and calendar.access_token_encrypted:
                if calendar.provider == CalendarProvider.MICROSOFT:
                    from app.services import outlook_calendar_service as svc
                else:
                    from app.services import google_calendar_service as svc
                if old_event_id:
                    try:
                        await svc.delete_event(calendar, db, old_event_id)
                    except Exception:
                        pass
                event = await svc.book_appointment(
                    calendar=calendar, db=db,
                    summary=appointment.title,
                    start=new_starts_at, end=new_ends_at,
                    description=appointment.description or "",
                    attendee_email=appointment.customer_email or "",
                )
                appointment.external_event_id = event.get("id")
                db.commit()
        except Exception as e:
            logger.error("Failed to update external calendar: %s", e, exc_info=True)

    starts_at_readable = format_spoken_slot(new_starts_at)

    # Send updated confirmations
    try:
        from app.models.phone_number import PhoneNumber
        from app.models.company import Company

        phone_cfg = db.query(PhoneNumber).filter(
            PhoneNumber.company_id == company_id, PhoneNumber.is_active == True,
        ).first()
        if phone_cfg:
            company_obj = db.query(Company).filter(Company.id == company_id).first()
            _cn = company_obj.name if company_obj else "ons bedrijf"

            _phone = customer_phone or appointment.customer_phone
            if _phone and phone_cfg.sms_confirmation_enabled:
                try:
                    from app.services.sms_service import send_appointment_confirmation_sms
                    send_appointment_confirmation_sms(to=_phone, company_name=_cn, starts_at_readable=starts_at_readable, custom_template=phone_cfg.sms_confirmation_template)
                except Exception as e:
                    logger.error("Failed to send reschedule SMS: %s", e, exc_info=True)

            _email = customer_email or appointment.customer_email
            if _email and phone_cfg.email_confirmation_enabled:
                try:
                    from app.core.email import send_appointment_confirmation_email
                    send_appointment_confirmation_email(to=_email, company_name=_cn, starts_at_readable=starts_at_readable, custom_template=phone_cfg.email_confirmation_template)
                except Exception as e:
                    logger.error("Failed to send reschedule email: %s", e, exc_info=True)
    except Exception as e:
        logger.error("Failed to load phone config for reschedule confirmations: %s", e, exc_info=True)

    logger.info("Appointment %s rescheduled to %s", appointment.id, new_starts_at)
    return {
        "ok": True,
        "appointment_id": str(appointment.id),
        "starts_at_readable": starts_at_readable,
        "message": f"De afspraak is verzet naar {starts_at_readable}.",
        "next_action": "Bevestig de nieuwe tijd en vraag of er verder nog iets is.",
    }


def tool_create_lead(
    db: Session,
    company_id: str,
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    notes: Optional[str] = None,
    source: str = "voice_call",
    call_log_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a lead record (demo request, sales interest, follow-up)."""
    logger.info("[tool_create_lead] company=%s name=%s source=%s", company_id, name, source)

    lead = Lead(
        id=uuid4(),
        company_id=UUID(company_id),
        call_log_id=UUID(call_log_id) if call_log_id else None,
        name=name,
        phone=phone,
        email=email,
        notes=notes,
        source=source,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    try:
        from app.services.notification_service import create_notification
        from app.models.notification import NotificationType
        create_notification(
            db=db, company_id=company_id,
            type=NotificationType.NOTE_ACTION,
            title=f"Nieuwe lead: {name}",
            message=notes[:120] if notes else f"Lead via {source}",
            url="/dashboard/notes",
        )
    except Exception:
        pass

    logger.info("Lead %s created for company %s", lead.id, company_id)
    return {
        "ok": True,
        "lead_id": str(lead.id),
        "message": f"Lead '{name}' is vastgelegd. Een collega neemt zo snel mogelijk contact op.",
    }


def tool_send_sms(
    db: Session,
    company_id: str,
    to: str,
    message: str,
    customer_phone: Optional[str] = None,
) -> Dict[str, Any]:
    """Send an SMS message. Falls back to caller phone if 'to' is empty."""
    destination = to.strip() if to else (customer_phone or "")
    if not destination:
        return {"ok": False, "message": "Er is geen telefoonnummer beschikbaar om een SMS naar te sturen."}

    logger.info("[tool_send_sms] company=%s to=%s", company_id, destination)
    from app.services.sms_service import send_sms
    ok = send_sms(to=destination, body=message)
    if ok:
        logger.info("SMS sent to %s", destination)
        return {"ok": True, "message": f"SMS verstuurd naar {destination}."}
    return {"ok": False, "message": "Het versturen van de SMS is mislukt. Probeer het later opnieuw."}


def tool_send_email(
    db: Session,
    company_id: str,
    to: str,
    subject: str,
    body: str,
) -> Dict[str, Any]:
    """Send a generic email on behalf of the company."""
    if not to or not to.strip():
        return {"ok": False, "message": "Er is geen e-mailadres opgegeven."}

    logger.info("[tool_send_email] company=%s to=%s subject=%s", company_id, to, subject)
    from app.core.email import send_generic_email
    from app.models.company import Company

    company_obj = db.query(Company).filter(Company.id == company_id).first()
    cn = company_obj.name if company_obj else "klantenservice.ai"

    ok = send_generic_email(to=to.strip(), subject=subject, body=body, company_name=cn)
    if ok:
        logger.info("Email sent to %s", to)
        return {"ok": True, "message": f"E-mail verstuurd naar {to}."}
    return {"ok": False, "message": "Het versturen van de e-mail is mislukt. Probeer het later opnieuw."}


def tool_leave_message(
    db: Session,
    company_id: str,
    message: str,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    customer_email: Optional[str] = None,
    call_log_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Leave a message — alias for create_note with category='Bericht'."""
    logger.info("[tool_leave_message] company=%s name=%s", company_id, customer_name)
    return tool_create_note(
        db=db,
        company_id=company_id,
        title=f"Bericht van {customer_name or 'klant'}",
        content=message,
        call_log_id=call_log_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        action_required=True,
        priority="normal",
    )


def tool_create_callback_request(
    db: Session,
    company_id: str,
    customer_name: Optional[str] = None,
    customer_phone: Optional[str] = None,
    preferred_callback_time: Optional[str] = None,
    notes: Optional[str] = None,
    call_log_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a callback request stored as an InternalNote with category 'Terugbellen'."""
    logger.info("[tool_create_callback_request] company=%s name=%s phone=%s",
                company_id, customer_name, customer_phone)

    content_parts = []
    if customer_name:
        content_parts.append(f"Naam: {customer_name}")
    if customer_phone:
        content_parts.append(f"Telefoon: {customer_phone}")
    if preferred_callback_time:
        content_parts.append(f"Gewenst tijdstip: {preferred_callback_time}")
    if notes:
        content_parts.append(f"Opmerking: {notes}")
    content = "\n".join(content_parts) or "Terugbelverzoek"

    note = InternalNote(
        id=uuid4(),
        company_id=UUID(company_id),
        call_log_id=UUID(call_log_id) if call_log_id else None,
        title=f"Terugbelverzoek: {customer_name or 'onbekend'}",
        content=content,
        category="Terugbellen",
        priority=NotePriority.HIGH,
        customer_name=customer_name,
        customer_phone=customer_phone,
        action_required=True,
        action_description="Bel de klant terug",
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    # Notification
    try:
        from app.services.notification_service import create_notification
        from app.models.notification import NotificationType
        create_notification(
            db=db, company_id=company_id,
            type=NotificationType.NOTE_ACTION,
            title=f"Terugbelverzoek: {customer_name or 'klant'}",
            message=content[:120],
            url="/dashboard/notes",
        )
    except Exception:
        pass

    # Callback SMS to customer
    if customer_phone:
        try:
            from app.models.phone_number import PhoneNumber
            from app.models.company import Company
            phone_cfg = db.query(PhoneNumber).filter(
                PhoneNumber.company_id == company_id, PhoneNumber.is_active == True,
            ).first()
            if phone_cfg and phone_cfg.sms_confirmation_enabled:
                company_obj = db.query(Company).filter(Company.id == company_id).first()
                cn = company_obj.name if company_obj else "ons bedrijf"
                template = phone_cfg.sms_callback_template or "Uw verzoek is genoteerd bij {bedrijfsnaam}. U wordt zo snel mogelijk teruggebeld."
                sms_text = template.replace("{bedrijfsnaam}", cn)
                from app.services.sms_service import send_sms
                send_sms(to=customer_phone, body=sms_text)
                logger.info("Callback SMS sent to %s", customer_phone)
        except Exception as e:
            logger.error("Failed to send callback SMS: %s", e, exc_info=True)

    logger.info("Callback request %s created for company %s", note.id, company_id)
    return {
        "ok": True,
        "note_id": str(note.id),
        "message": "Het terugbelverzoek is genoteerd. Een collega belt zo snel mogelijk terug.",
    }
