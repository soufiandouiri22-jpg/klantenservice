"""
klantenservice.ai - Voice Call Orchestrator

Receives live transcript (user + assistant), detects intent, calls tools,
and builds context injection payload for the voice agent.

Goal: The AI NEVER hallucinates. Prices, availability, and policies
come ONLY from tool results injected via update_context.

Flow:
1. Receive user_transcript + assistant_transcript
2. LLM determines intent and calls appropriate tools
3. Tool results are converted to facts + instructions
4. Facts + instructions are sent back for context injection
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.call_tools import (
    tool_check_availability,
    tool_book_appointment,
    tool_search_knowledge,
    tool_get_pricing,
    tool_get_company_overview,
    tool_get_contact_info,
    tool_get_opening_hours,
    tool_get_services,
    tool_get_location,
    tool_create_note,
    tool_flag_unknown,
    tool_transfer_call,
    tool_check_policy,
    tool_cancel_appointment,
    tool_reschedule_appointment,
    tool_create_lead,
    tool_send_sms,
    tool_send_email,
    tool_leave_message,
    tool_create_callback_request,
)
from app.models.context_log import ContextLog
from app.models.usage_log import UsageLog
from app.models.global_config import GlobalConfig

settings = get_settings()
logger = logging.getLogger(__name__)


def _get_model_config(db: Session, key: str, default: str) -> str:
    """
    Get model configuration from database, fallback to default if not found.
    
    Args:
        db: Database session
        key: Config key (e.g., 'model_default', 'model_fallback', 'model_big')
        default: Default value if config not found
        
    Returns:
        Model name string
    """
    try:
        config = db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
        if config and config.value:
            return str(config.value)
    except Exception as e:
        logger.warning(f"Failed to read model config '{key}': {e}")
    
    return default

# System prompt for the orchestrator
SYSTEM_PROMPT = """Je bent de intent- en actie-laag voor een Nederlandse klantenservice-telefoonlijn.
Jij bepaalt de waarheid; de spraakassistent spreekt alleen jouw feiten uit.

BELANGRIJKE REGELS:
- Bij prijzen, pakketten, abonnementen: gebruik get_pricing tool. NIET search_knowledge.
- Bij "wat doen jullie?" / bedrijfsoverzicht: gebruik get_company_overview tool. NIET search_knowledge.
- Bij contact, telefoon, email: gebruik get_contact_info tool. NIET search_knowledge.
- Bij openingstijden, wanneer open/dicht: gebruik get_opening_hours tool. NIET search_knowledge.
- Bij diensten, services, aanbod: gebruik get_services tool. NIET search_knowledge.
- Bij locatie, adres, vestiging: gebruik get_location tool. NIET search_knowledge.
- Bij beleid, FAQ, retour, garantie, overige vragen: gebruik search_knowledge tool.
- Bij afspraakvragen: gebruik check_availability en book_appointment tools.
- Als je een vraag NIET kunt beantwoorden: gebruik flag_unknown tool EN maak een notitie.
- Voor terugbelverzoeken of notities: gebruik create_note tool.
- VERZIN NOOIT producten, diensten, prijzen of openingstijden. Als de kennisbank geen resultaat geeft, zeg dan dat je het niet weet en bied aan om een collega te laten terugbellen.
- Noem NOOIT interne systemen (agenda, kennisbank, tools) tegen de klant. Gebruik altijd klantgerichte taal.

PRIJZEN — STRIKT:
- Kopieer prijzen, bedragen en getallen EXACT uit tool-resultaten naar het "facts" veld.
- Wijzig GEEN enkel cijfer. Rond NIET af. €99 moet €99 blijven, NIET €100.
- Als een tool-resultaat een PRIJSINSTRUCTIE bevat, neem die op in "instructions".

AFSCHEID / TEVREDEN — STRIKT:
- Als de klant aangeeft tevreden te zijn of afscheid neemt: roep GEEN tools aan.
- Voorbeelden: "ik weet genoeg", "dat was het", "top dankjewel", "nee hoeft niet", "fijne dag".
- Geef dan ALLEEN een kort afscheid in "instructions" (bijv. "Fijne dag!"). Gebruik GEEN tool.
- Spreek NOOIT interne instructies uit. Zeg nooit "ik rond af" of "ik ga afsluiten".

ACTIE-ROUTING:
- "Annuleer mijn afspraak" → cancel_appointment
- "Verzet mijn afspraak" / "kan ik mijn afspraak verplaatsen" → reschedule_appointment
- "Laat iemand mij terugbellen" / "kan iemand mij bellen" → create_callback_request
- "Ik wil een bericht achterlaten" → leave_message
- "Stuur me een sms" → send_sms
- "Mail het me even" / "stuur het per email" → send_email
- "Ik ben geïnteresseerd" / "ik wil een demo" → create_lead

INTERNE INSTRUCTIES NOOIT UITSPREKEN:
- Spreek NOOIT instructietekst, toolnamen, systeemtekst of interne logica hardop uit.
- Zeg nooit: "ik rond het gesprek af", "ik ga end_call gebruiken", "de tool zegt...", "instruction_nl is...".
- Alles in "instructions" is voor JOU, niet voor de klant.

OUTPUT:
Geef een JSON object met twee velden:
1. "facts": Letterlijke feiten uit tool-resultaten die de assistent moet gebruiken. Kort en concreet. Prijzen en getallen EXACT overnemen.
2. "instructions": Wat de assistent moet zeggen/doen. Geen beleefdheden, alleen de kern.

Voorbeeld output:
{
    "facts": "Beschikbaar: morgen 14:00 en 15:30. Afspraak van 30 minuten.",
    "instructions": "Vraag welk tijdstip de klant het beste uitkomt."
}"""

# Tool definitions for OpenAI function calling
TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Haal beschikbare agenda-slots op voor een datum/periode. Gebruik dit als de klant een afspraak wil maken.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": (
                            "ISO datetime of date. Als de klant al een tijd noemde (bijv. om 10 uur), "
                            "zet die tijd in de string (YYYY-MM-DDTHH:MM). Alleen datum als nog geen tijd bekend is."
                        ),
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duur van de afspraak in minuten. Standaard 30.",
                        "default": 30
                    },
                },
                "required": ["start_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Plan een afspraak in de agenda. Gebruik dit nadat de klant een tijdstip heeft gekozen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "starts_at": {"type": "string", "description": "ISO datetime van de afspraak"},
                    "ends_at": {"type": "string", "description": "ISO datetime einde afspraak"},
                    "customer_name": {"type": "string", "description": "Naam van de klant"},
                    "customer_email": {"type": "string", "description": "E-mailadres van de klant (optioneel, voor bevestigingsmail)", "default": ""},
                    "title": {"type": "string", "description": "Titel/omschrijving afspraak", "default": "Afspraak"},
                },
                "required": ["starts_at", "ends_at", "customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pricing",
            "description": "Haal prijsinformatie op. Gebruik bij prijsvragen, pakketvragen, abonnementsvragen. NIET search_knowledge gebruiken voor prijzen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optioneel: naam van een specifiek pakket (bijv. 'starter', 'business'). Leeg laten voor alle pakketten.",
                        "default": "",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_overview",
            "description": "Haal bedrijfsoverzicht op. Gebruik als de klant vraagt wat het bedrijf doet, aanbiedt, of wie jullie zijn. NIET search_knowledge gebruiken voor bedrijfsoverzicht.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_contact_info",
            "description": "Haal contactgegevens op (telefoon, email, whatsapp). Gebruik als de klant vraagt hoe ze contact kunnen opnemen. NIET search_knowledge gebruiken voor contactgegevens.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_opening_hours",
            "description": "Haal openingstijden op. Gebruik als de klant vraagt wanneer het bedrijf open/dicht is of bereikbaar is. NIET search_knowledge gebruiken voor openingstijden.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_services",
            "description": "Haal een lijst van diensten/services op. Gebruik als de klant vraagt welke diensten of services worden aangeboden. NIET search_knowledge gebruiken voor diensten.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_location",
            "description": "Haal locatie/adresgegevens op. Gebruik als de klant vraagt waar het bedrijf zit, het adres, of de vestiging. NIET search_knowledge gebruiken voor locatie.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Zoek in de bedrijfskennisbank voor overige vragen. Gebruik voor FAQ, beleid (retour, garantie), en vragen die niet door een dedicated tool worden afgehandeld. NIET gebruiken voor: prijzen (get_pricing), bedrijfsoverzicht (get_company_overview), contact (get_contact_info), openingstijden (get_opening_hours), diensten (get_services), locatie (get_location).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "De zoekopdracht"},
                    "limit": {"type": "integer", "description": "Max aantal resultaten", "default": 20},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": "Maak een interne notitie voor opvolging (bijv. terugbelverzoek, klacht, speciale vraag).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Korte titel van de notitie"},
                    "content": {"type": "string", "description": "Inhoud van de notitie"},
                    "customer_name": {"type": "string", "description": "Naam van de klant"},
                    "action_required": {"type": "boolean", "description": "Moet er actie worden ondernomen?", "default": False},
                    "priority": {"type": "string", "description": "Prioriteit: low, normal, high, urgent", "default": "normal"},
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "flag_unknown",
            "description": "Markeer een vraag die niet beantwoord kon worden. Gebruik dit als je geen informatie hebt om de vraag te beantwoorden.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "De vraag die niet beantwoord kon worden"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_call",
            "description": "Verbind het gesprek door naar een menselijke collega. Gebruik ALLEEN als de beller expliciet om een mens vraagt of de situatie te complex is.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Korte reden waarom het gesprek wordt doorverbonden"},
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Annuleer een bestaande afspraak. Zoekt op telefoonnummer, naam en/of datum.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Naam van de klant"},
                    "appointment_date": {"type": "string", "description": "Datum van de afspraak (YYYY-MM-DD)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Verzet een bestaande afspraak naar een nieuw tijdstip. Zoekt bestaande afspraak op telefoonnummer/naam/datum, verplaatst naar nieuwe tijd.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Naam van de klant"},
                    "appointment_date": {"type": "string", "description": "Datum van de huidige afspraak (YYYY-MM-DD)"},
                    "new_starts_at": {"type": "string", "description": "ISO datetime van het nieuwe tijdstip"},
                    "new_ends_at": {"type": "string", "description": "ISO datetime einde nieuwe afspraak"},
                },
                "required": ["new_starts_at", "new_ends_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_lead",
            "description": "Leg een lead/geïnteresseerde vast (demo-aanvraag, verkoopinteresse, opvolgverzoek).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Naam van de geïnteresseerde"},
                    "phone": {"type": "string", "description": "Telefoonnummer"},
                    "email": {"type": "string", "description": "E-mailadres"},
                    "notes": {"type": "string", "description": "Opmerkingen of reden van interesse"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_sms",
            "description": "Stuur een SMS-bericht naar de klant of een opgegeven nummer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Telefoonnummer (leeg = nummer van de beller)"},
                    "message": {"type": "string", "description": "Tekst van het SMS-bericht"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Stuur een e-mail namens het bedrijf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "E-mailadres van de ontvanger"},
                    "subject": {"type": "string", "description": "Onderwerp van de e-mail"},
                    "body": {"type": "string", "description": "Inhoud van de e-mail"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leave_message",
            "description": "Laat een bericht achter voor een collega. Gebruik als de klant een boodschap wil achterlaten.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Het bericht"},
                    "customer_name": {"type": "string", "description": "Naam van de klant"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_callback_request",
            "description": "Maak een terugbelverzoek aan. De klant wil worden teruggebeld.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Naam van de klant"},
                    "preferred_callback_time": {"type": "string", "description": "Gewenst tijdstip voor terugbellen"},
                    "notes": {"type": "string", "description": "Extra opmerkingen"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_policy",
            "description": "Controleer of een actie mag worden uitgevoerd (bijv. ophangen, escaleren). VERPLICHT vóór end_call en transfer_call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trigger_reason": {
                        "type": "string",
                        "description": "Reden: ending_call, escalation, low_confidence, repeated_failure, off_topic, silence",
                    },
                    "customer_message": {
                        "type": "string",
                        "description": "Wat de klant het laatst heeft gezegd",
                    },
                },
                "required": ["trigger_reason", "customer_message"],
            },
        },
    },
]


async def _run_tool(
    name: str,
    arguments: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a tool and return its result."""
    db: Session = context["db"]
    company_id: str = context["company_id"]
    call_log_id: Optional[str] = context.get("call_log_id")
    calendar_id: Optional[str] = context.get("calendar_id")
    customer_phone: Optional[str] = context.get("customer_phone")
    
    try:
        if name == "check_availability":
            from dateutil import parser as date_parser
            start_str = arguments.get("start_date", "")
            try:
                start = date_parser.parse(start_str)
            except Exception:
                from zoneinfo import ZoneInfo
                start = datetime.now(ZoneInfo("Europe/Amsterdam")).replace(tzinfo=None)
            ai_worker_id = context.get("ai_worker_id")
            return await tool_check_availability(
                db, company_id,
                start_date=start,
                duration_minutes=int(arguments.get("duration_minutes", 30)),
                ai_worker_id=ai_worker_id,
            )
        
        if name == "book_appointment":
            from dateutil import parser as date_parser
            ai_worker_id = context.get("ai_worker_id")
            cal_id = calendar_id
            if not cal_id:
                from app.models.calendar_integration import CalendarIntegration
                query = db.query(CalendarIntegration).filter(
                    CalendarIntegration.company_id == company_id,
                    CalendarIntegration.is_active == True,
                )
                if ai_worker_id:
                    query = query.filter(CalendarIntegration.ai_worker_id == ai_worker_id)
                calendar = query.first()
                cal_id = str(calendar.id) if calendar else None
            
            if not cal_id:
                return {"ok": False, "reason": "no_calendar", "message": "Afspraken inplannen is op dit moment niet mogelijk. Zeg NIET dat er geen agenda is. Bied aan om de gegevens te noteren zodat een collega zo snel mogelijk terugbelt om een afspraak in te plannen. Bevestig het telefoonnummer."}

            # Validatie: ontbrekende velden (PolyAI-style)
            customer_name = (arguments.get("customer_name") or "").strip()
            if not customer_name or customer_name.lower() == "klant":
                return {
                    "ok": False,
                    "missing": "customer_name",
                    "message": "Vraag de naam van de klant voordat je boekt. Roep book_appointment pas aan als je de naam hebt.",
                }
            if not arguments.get("starts_at"):
                return {
                    "ok": False,
                    "missing": "starts_at",
                    "message": "Vraag eerst de datum en tijd. Roep check_availability aan, laat de klant kiezen, en roep dan book_appointment aan.",
                }
            if not arguments.get("ends_at"):
                return {
                    "ok": False,
                    "missing": "ends_at",
                    "message": "Vraag eerst de datum en tijd. Roep check_availability aan, laat de klant kiezen, en roep dan book_appointment aan.",
                }
            try:
                starts_at = date_parser.parse(arguments["starts_at"])
                ends_at = date_parser.parse(arguments["ends_at"])
            except Exception:
                return {
                    "ok": False,
                    "missing": "starts_at",
                    "message": "De datum of tijd kon niet worden begrepen. Vraag de klant om de datum en tijd opnieuw te zeggen, bijvoorbeeld: 'dinsdag 15 maart om 14 uur'.",
                }

            return await tool_book_appointment(
                db, company_id,
                calendar_integration_id=cal_id,
                starts_at=starts_at,
                ends_at=ends_at,
                customer_name=customer_name,
                title=arguments.get("title", "Afspraak"),
                customer_phone=customer_phone,
                customer_email=arguments.get("customer_email") or None,
                call_log_id=call_log_id,
            )
        
        if name == "get_pricing":
            return tool_get_pricing(
                db, company_id,
                query=arguments.get("query", ""),
            )

        if name == "get_company_overview":
            return tool_get_company_overview(db, company_id)

        if name == "get_contact_info":
            return tool_get_contact_info(db, company_id)

        if name == "get_opening_hours":
            return tool_get_opening_hours(db, company_id)

        if name == "get_services":
            return tool_get_services(db, company_id)

        if name == "get_location":
            return tool_get_location(db, company_id)

        if name == "search_knowledge":
            return tool_search_knowledge(
                db, company_id,
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 20)
            )
        
        if name == "create_note":
            return tool_create_note(
                db, company_id,
                title=arguments.get("title", "Notitie"),
                content=arguments.get("content", ""),
                call_log_id=call_log_id,
                customer_name=arguments.get("customer_name"),
                customer_phone=customer_phone,
                action_required=arguments.get("action_required", False),
                priority=arguments.get("priority", "normal"),
            )
        
        if name == "flag_unknown":
            return tool_flag_unknown(
                db, company_id,
                question=arguments.get("question", ""),
                call_log_id=call_log_id,
            )

        if name == "transfer_call":
            call_sid = context.get("call_sid")
            return tool_transfer_call(
                db, company_id,
                call_log_id=call_log_id,
                call_sid=call_sid,
                reason=arguments.get("reason", ""),
            )

        if name == "cancel_appointment":
            return await tool_cancel_appointment(
                db, company_id,
                customer_phone=customer_phone,
                customer_name=arguments.get("customer_name"),
                appointment_date=arguments.get("appointment_date"),
                call_log_id=call_log_id,
            )

        if name == "reschedule_appointment":
            from dateutil import parser as date_parser
            try:
                new_starts_at = date_parser.parse(arguments["new_starts_at"])
                new_ends_at = date_parser.parse(arguments["new_ends_at"])
            except Exception:
                return {
                    "ok": False,
                    "missing": "new_starts_at",
                    "message": "De nieuwe datum of tijd kon niet worden begrepen. Vraag de klant om de gewenste datum en tijd.",
                }
            return await tool_reschedule_appointment(
                db, company_id,
                new_starts_at=new_starts_at,
                new_ends_at=new_ends_at,
                customer_phone=customer_phone,
                customer_name=arguments.get("customer_name"),
                appointment_date=arguments.get("appointment_date"),
                call_log_id=call_log_id,
                customer_email=arguments.get("customer_email"),
            )

        if name == "create_lead":
            lead_name = (arguments.get("name") or "").strip()
            if not lead_name:
                return {"ok": False, "missing": "name", "message": "Vraag de naam van de klant."}
            return tool_create_lead(
                db, company_id,
                name=lead_name,
                phone=arguments.get("phone") or customer_phone,
                email=arguments.get("email"),
                notes=arguments.get("notes"),
                call_log_id=call_log_id,
            )

        if name == "send_sms":
            msg = (arguments.get("message") or "").strip()
            if not msg:
                return {"ok": False, "missing": "message", "message": "Vraag wat er in de SMS moet staan."}
            return tool_send_sms(
                db, company_id,
                to=arguments.get("to", ""),
                message=msg,
                customer_phone=customer_phone,
            )

        if name == "send_email":
            if not arguments.get("to"):
                return {"ok": False, "missing": "to", "message": "Vraag het e-mailadres van de klant."}
            if not arguments.get("subject"):
                return {"ok": False, "missing": "subject", "message": "Geef een onderwerp op voor de e-mail."}
            return tool_send_email(
                db, company_id,
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments.get("body", ""),
            )

        if name == "leave_message":
            msg = (arguments.get("message") or "").strip()
            if not msg:
                return {"ok": False, "missing": "message", "message": "Vraag wat het bericht is."}
            return tool_leave_message(
                db, company_id,
                message=msg,
                customer_name=arguments.get("customer_name"),
                customer_phone=customer_phone,
                call_log_id=call_log_id,
            )

        if name == "create_callback_request":
            return tool_create_callback_request(
                db, company_id,
                customer_name=arguments.get("customer_name"),
                customer_phone=customer_phone,
                preferred_callback_time=arguments.get("preferred_callback_time"),
                notes=arguments.get("notes"),
                call_log_id=call_log_id,
            )

        if name == "check_policy":
            call_sid = context.get("call_sid") or ""
            return tool_check_policy(
                db, company_id,
                call_sid=call_sid,
                call_log_id=call_log_id,
                trigger_reason=arguments.get("trigger_reason", "ending_call"),
                customer_message=arguments.get("customer_message", ""),
            )

        return {"ok": False, "reason": "unknown_tool", "message": f"Onbekende tool: {name}"}
        
    except Exception as e:
        logger.error(f"Tool {name} error: {e}", exc_info=True)
        return {"ok": False, "reason": "error", "message": str(e)}


def build_context_payload(
    db: Session,
    company_id: str,
    call_log_id: Optional[str],
    calendar_id: Optional[str],
    user_transcript: str,
    assistant_transcript_so_far: str,
    customer_phone: Optional[str] = None,
    turn_id: int = 0,
) -> Tuple[str, str]:
    """
    Build context injection payload from transcript.
    
    Args:
        db: Database session
        company_id: Company UUID
        call_log_id: Call log UUID
        calendar_id: Calendar UUID (if known)
        user_transcript: What the customer said (from STT)
        assistant_transcript_so_far: What the assistant has said
        customer_phone: Customer's phone number
        turn_id: Current turn ID
        
    Returns:
        Tuple of (facts, instructions) to inject into the voice agent
    """
    import asyncio
    import time
    from uuid import UUID
    
    # Check if OpenAI is configured
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not configured - orchestrator disabled")
        return "", ""
    
    if not user_transcript.strip():
        return "", ""
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
    except ImportError:
        logger.error("OpenAI package not installed")
        return "", ""
    except Exception as e:
        logger.error(f"Failed to create OpenAI client: {e}")
        return "", ""
    
    # Build context for tool execution
    tool_context = {
        "db": db,
        "company_id": str(company_id),
        "call_log_id": str(call_log_id) if call_log_id else None,
        "calendar_id": str(calendar_id) if calendar_id else None,
        "customer_phone": customer_phone,
    }
    
    # Build messages for LLM
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Beurt {turn_id}:
KLANT: {user_transcript}
ASSISTENT TOT NU: {assistant_transcript_so_far or "(nog niets gezegd)"}

Bepaal welke tools nodig zijn en geef daarna facts + instructions als JSON."""
        },
    ]
    
    # Track for logging
    tool_calls_log: List[Dict[str, Any]] = []
    detected_intent = None
    intent_confidence = None
    was_escalated = 0
    total_input_tokens = 0
    total_output_tokens = 0
    
    # Get model configuration from database (with fallback to settings)
    model_used = _get_model_config(db, "model_default", settings.ORCHESTRATOR_MODEL)
    model_fallback = _get_model_config(db, "model_fallback", "gpt-3.5-turbo")
    model_big = _get_model_config(db, "model_big", "gpt-4o")
    use_big_on_unknown = False
    try:
        config_use_big = db.query(GlobalConfig).filter(GlobalConfig.key == "model_use_big_on_unknown").first()
        if config_use_big and config_use_big.value:
            use_big_on_unknown = bool(config_use_big.value)
    except:
        pass
    
    try:
        # First call: let LLM decide which tools to call
        response = client.chat.completions.create(
            model=model_used,
            messages=messages,
            tools=TOOLS_OPENAI,
            tool_choice="auto",
            max_tokens=1024,
        )
        
        choice = response.choices[0]
        
        # Track token usage
        if response.usage:
            total_input_tokens += response.usage.prompt_tokens
            total_output_tokens += response.usage.completion_tokens
        
        # If tools were called, execute them
        if choice.message.tool_calls:
            tool_results: List[str] = []
            tool_messages = [choice.message]
            
            for tc in choice.message.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                
                # Detect intent from first tool call
                if detected_intent is None:
                    detected_intent = name
                    intent_confidence = 85  # Assume high confidence if LLM called a tool
                
                logger.info(f"Orchestrator calling tool: {name} with {args}")
                
                # Time the tool call
                tool_start = time.time()
                result = asyncio.run(_run_tool(name, args, tool_context))
                tool_latency_ms = int((time.time() - tool_start) * 1000)
                
                result_str = json.dumps(result, ensure_ascii=False)
                tool_results.append(result_str)
                
                # Log tool call
                tool_calls_log.append({
                    "name": name,
                    "arguments": args,
                    "result": result,
                    "latency_ms": tool_latency_ms,
                })
                
                # Check if escalated
                if name == "flag_unknown":
                    was_escalated = 1
                elif name == "create_note" and args.get("priority") in ["high", "urgent"]:
                    was_escalated = 2
                
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str
                })
            
            # Second call: get facts + instructions based on tool results
            followup = client.chat.completions.create(
                model=model_used,
                messages=messages + tool_messages,
                max_tokens=512,
            )
            
            # Track token usage
            if followup.usage:
                total_input_tokens += followup.usage.prompt_tokens
                total_output_tokens += followup.usage.completion_tokens
            
            text = followup.choices[0].message.content or ""
        else:
            # No tools called - check if we should use big model for unknown questions
            if use_big_on_unknown:
                logger.info("No tools called, using big model for unknown question")
                try:
                    # Retry with big model
                    big_response = client.chat.completions.create(
                        model=model_big,
                        messages=messages,
                        tools=TOOLS_OPENAI,
                        tool_choice="auto",
                        max_tokens=1024,
                    )
                    big_choice = big_response.choices[0]
                    if big_response.usage:
                        total_input_tokens += big_response.usage.prompt_tokens
                        total_output_tokens += big_response.usage.completion_tokens
                    
                    if big_choice.message.tool_calls:
                        # Big model found tools - execute them
                        tool_results = []
                        tool_messages = [big_choice.message]
                        
                        for tc in big_choice.message.tool_calls:
                            name = tc.function.name
                            try:
                                args = json.loads(tc.function.arguments or "{}")
                            except json.JSONDecodeError:
                                args = {}
                            
                            if detected_intent is None:
                                detected_intent = name
                                intent_confidence = 80
                            
                            logger.info(f"Orchestrator (big model) calling tool: {name} with {args}")
                            tool_start = time.time()
                            result = asyncio.run(_run_tool(name, args, tool_context))
                            tool_latency_ms = int((time.time() - tool_start) * 1000)
                            
                            result_str = json.dumps(result, ensure_ascii=False)
                            tool_results.append(result_str)
                            tool_calls_log.append({
                                "name": name,
                                "arguments": args,
                                "result": result,
                                "latency_ms": tool_latency_ms,
                            })
                            
                            if name == "flag_unknown":
                                was_escalated = 1
                            elif name == "create_note" and args.get("priority") in ["high", "urgent"]:
                                was_escalated = 2
                            
                            tool_messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": result_str
                            })
                        
                        # Get facts + instructions from big model
                        followup = client.chat.completions.create(
                            model=model_big,
                            messages=messages + tool_messages,
                            max_tokens=512,
                        )
                        if followup.usage:
                            total_input_tokens += followup.usage.prompt_tokens
                            total_output_tokens += followup.usage.completion_tokens
                        text = followup.choices[0].message.content or ""
                        model_used = model_big  # Update model_used for logging
                    else:
                        text = big_choice.message.content or ""
                        detected_intent = "direct_response"
                        intent_confidence = 70
                        model_used = model_big  # Update model_used for logging
                except Exception as big_err:
                    logger.warning(f"Big model call failed, using default response: {big_err}")
                    text = choice.message.content or ""
                    detected_intent = "direct_response"
                    intent_confidence = 70
            else:
                # No tools called - use direct response
                text = choice.message.content or ""
                detected_intent = "direct_response"
                intent_confidence = 70
        
        # Parse facts and instructions from response
        facts, instructions = _parse_context_response(text)
        
        # Log to ContextLog
        try:
            if call_log_id:
                context_log = ContextLog(
                    call_log_id=UUID(call_log_id),
                    turn_id=turn_id,
                    user_transcript=user_transcript,
                    assistant_transcript=assistant_transcript_so_far,
                    detected_intent=detected_intent,
                    intent_confidence=intent_confidence,
                    tool_calls=tool_calls_log,
                    facts=facts,
                    instructions=instructions,
                    model_used=model_used,
                    was_escalated=was_escalated,
                )
                db.add(context_log)
                
                # Log to UsageLog
                usage_log = UsageLog(
                    company_id=UUID(company_id),
                    call_log_id=UUID(call_log_id),
                    turn_id=turn_id,
                    llm_input_tokens=total_input_tokens,
                    llm_output_tokens=total_output_tokens,
                    llm_model=model_used,
                )
                usage_log.calculate_costs()
                db.add(usage_log)
                
                db.commit()
        except Exception as log_err:
            logger.warning(f"Failed to save context/usage log: {log_err}")
            # Don't fail the whole operation if logging fails
        
        return facts, instructions
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}", exc_info=True)
        
        # Try fallback model if default model failed
        if model_used != model_fallback:
            logger.info(f"Trying fallback model: {model_fallback}")
            try:
                fallback_response = client.chat.completions.create(
                    model=model_fallback,
                    messages=messages,
                    tools=TOOLS_OPENAI,
                    tool_choice="auto",
                    max_tokens=1024,
                )
                choice = fallback_response.choices[0]
                if choice.message.content:
                    facts, instructions = _parse_context_response(choice.message.content)
                    logger.info("Fallback model succeeded")
                    return facts, instructions
            except Exception as fallback_err:
                logger.error(f"Fallback model also failed: {fallback_err}")
        
        return "", ""


def _parse_context_response(text: str) -> Tuple[str, str]:
    """Parse facts and instructions from LLM response."""
    facts = ""
    instructions = ""
    
    # Try to parse as JSON first
    try:
        # Find JSON in the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            facts = data.get("facts", "")
            instructions = data.get("instructions", "")
            return facts.strip(), instructions.strip()
    except json.JSONDecodeError:
        pass
    
    # Fallback: try to extract from text
    text_lower = text.lower()
    
    if "facts:" in text_lower or "feiten:" in text_lower:
        for marker in ["facts:", "feiten:", "Facts:", "Feiten:"]:
            if marker in text:
                idx = text.index(marker) + len(marker)
                rest = text[idx:]
                # Find where instructions start
                for end_marker in ["instructions:", "instructies:", "Instructions:", "Instructies:"]:
                    if end_marker in rest:
                        facts = rest[:rest.index(end_marker)].strip()
                        rest = rest[rest.index(end_marker) + len(end_marker):]
                        instructions = rest.strip()
                        break
                else:
                    facts = rest.strip()
                break
    else:
        # Just use the whole text as instructions
        instructions = text.strip()
    
    return facts, instructions


# Convenience function for simple cases
async def process_turn(
    db: Session,
    company_id: str,
    call_log_id: Optional[str],
    user_transcript: str,
    assistant_transcript: str,
    customer_phone: Optional[str] = None,
    turn_id: int = 0,
) -> Tuple[str, str]:
    """
    Async wrapper for build_context_payload.
    
    Returns (facts, instructions) tuple.
    """
    import asyncio
    
    # Run in thread pool to not block async loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        build_context_payload,
        db,
        company_id,
        call_log_id,
        None,  # calendar_id
        user_transcript,
        assistant_transcript,
        customer_phone,
        turn_id,
    )
