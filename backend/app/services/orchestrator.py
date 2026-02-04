"""
klantenservice.ai - Voice Call Orchestrator

Receives live transcript (user + assistant), detects intent, calls tools,
and builds context injection payload for PersonaPlex.

Goal: PersonaPlex NEVER hallucinates. Prices, availability, and policies
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
    tool_get_prices,
    tool_create_note,
    tool_flag_unknown,
)

settings = get_settings()
logger = logging.getLogger(__name__)

# System prompt for the orchestrator
SYSTEM_PROMPT = """Je bent de intent- en actie-laag voor een Nederlandse klantenservice-telefoonlijn.
Jij bepaalt de waarheid; de spraakassistent spreekt alleen jouw feiten uit.

BELANGRIJKE REGELS:
- Bij prijzen, openingstijden, beleid: gebruik ALLEEN de resultaten van de tools. NOOIT iets verzinnen.
- Bij afspraakvragen: gebruik check_availability en book_appointment tools.
- Bij vragen over het bedrijf: gebruik search_knowledge tool.
- Bij prijsvragen: gebruik get_prices tool.
- Als je een vraag NIET kunt beantwoorden: gebruik flag_unknown tool EN maak een notitie.
- Voor terugbelverzoeken of notities: gebruik create_note tool.

OUTPUT:
Geef een JSON object met twee velden:
1. "facts": Letterlijke feiten uit tool-resultaten die de assistent moet gebruiken. Kort en concreet.
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
                        "description": "ISO datetime of date (YYYY-MM-DD of YYYY-MM-DDTHH:MM:SS). Gebruik vandaag als geen datum genoemd."
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
                    "title": {"type": "string", "description": "Titel/omschrijving afspraak", "default": "Afspraak"},
                },
                "required": ["starts_at", "ends_at", "customer_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Zoek in de bedrijfsinformatie/kennisbank. Gebruik dit voor vragen over openingstijden, locatie, diensten, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "De zoekopdracht"},
                    "limit": {"type": "integer", "description": "Max aantal resultaten", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_prices",
            "description": "Haal prijsinformatie op. Gebruik dit bij prijsvragen. Geef ALLEEN prijzen door die hier terugkomen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Onderwerp/dienst waarvoor prijzen gevraagd worden"},
                },
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
]


def _run_tool(
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
            except:
                start = datetime.now()
            return tool_check_availability(
                db, company_id,
                start_date=start,
                duration_minutes=int(arguments.get("duration_minutes", 30)),
            )
        
        if name == "book_appointment":
            from dateutil import parser as date_parser
            # Need calendar_id - get from availability result or use first calendar
            cal_id = calendar_id
            if not cal_id:
                from app.models.calendar_integration import CalendarIntegration
                calendar = db.query(CalendarIntegration).filter(
                    CalendarIntegration.company_id == company_id,
                    CalendarIntegration.is_active == True,
                ).first()
                cal_id = str(calendar.id) if calendar else None
            
            if not cal_id:
                return {"ok": False, "reason": "no_calendar", "message": "Geen agenda beschikbaar."}
            
            return tool_book_appointment(
                db, company_id,
                calendar_integration_id=cal_id,
                starts_at=date_parser.parse(arguments["starts_at"]),
                ends_at=date_parser.parse(arguments["ends_at"]),
                customer_name=arguments.get("customer_name", "Klant"),
                title=arguments.get("title", "Afspraak"),
                customer_phone=customer_phone,
                call_log_id=call_log_id,
            )
        
        if name == "search_knowledge":
            return tool_search_knowledge(
                db, company_id,
                query=arguments.get("query", ""),
                limit=arguments.get("limit", 5)
            )
        
        if name == "get_prices":
            return tool_get_prices(
                db, company_id,
                topic=arguments.get("topic")
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
        Tuple of (facts, instructions) to inject into PersonaPlex
    """
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
    
    try:
        # First call: let LLM decide which tools to call
        response = client.chat.completions.create(
            model=settings.ORCHESTRATOR_MODEL,
            messages=messages,
            tools=TOOLS_OPENAI,
            tool_choice="auto",
            max_tokens=1024,
        )
        
        choice = response.choices[0]
        
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
                
                logger.info(f"Orchestrator calling tool: {name} with {args}")
                result = _run_tool(name, args, tool_context)
                result_str = json.dumps(result, ensure_ascii=False)
                tool_results.append(result_str)
                
                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str
                })
            
            # Second call: get facts + instructions based on tool results
            followup = client.chat.completions.create(
                model=settings.ORCHESTRATOR_MODEL,
                messages=messages + tool_messages,
                max_tokens=512,
            )
            
            text = followup.choices[0].message.content or ""
        else:
            # No tools called - use direct response
            text = choice.message.content or ""
        
        # Parse facts and instructions from response
        return _parse_context_response(text)
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}", exc_info=True)
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
