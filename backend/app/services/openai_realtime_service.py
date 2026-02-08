"""
klantenservice.ai - OpenAI Realtime API Service

Manages WebSocket connections to the OpenAI Realtime API for voice calls.
Replaces PersonaPlex with GPT-4o Realtime for speech-to-speech AI.

Key advantages:
- Native g711_ulaw support (same as Twilio) — no audio conversion needed
- Full-duplex: AI can listen while talking
- Barge-in: AI stops talking when caller speaks
- Built-in STT, LLM, TTS in one API
- Function calling for tools (availability, booking, knowledge, etc.)
"""
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import websockets

from app.core.config import get_settings
from app.models.ai_worker import AIWorker, AddressForm
from app.models.system_prompt import SystemPrompt
from app.services.orchestrator import TOOLS_OPENAI

settings = get_settings()
logger = logging.getLogger(__name__)

# OpenAI Realtime API endpoint
REALTIME_API_URL = "wss://api.openai.com/v1/realtime"


def build_realtime_tools() -> List[Dict[str, Any]]:
    """
    Convert orchestrator TOOLS_OPENAI (Chat Completions format) to
    OpenAI Realtime API tool format.

    Chat Completions format:
        {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}

    Realtime API format:
        {"type": "function", "name": ..., "description": ..., "parameters": ...}
    """
    realtime_tools = []
    for tool in TOOLS_OPENAI:
        if tool.get("type") == "function" and "function" in tool:
            fn = tool["function"]
            realtime_tools.append({
                "type": "function",
                "name": fn["name"],
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            })
    return realtime_tools


def build_system_instructions(
    worker: AIWorker,
    company_name: str,
    disclosure_message: Optional[str] = None,
    knowledge_context: Optional[str] = None,
    training_rules: Optional[list] = None,
    example_answers: Optional[list] = None,
    system_prompts: Optional[str] = None,
) -> str:
    """
    Build system instructions for the OpenAI Realtime session.

    Follows OpenAI's official Realtime Prompting Guide structure:
    1. Role & Objective
    2. Personality & Tone
    3. Context (knowledge, platform rules)
    4. Tools
    5. Instructions / Rules
    6. Conversation Flow
    7. Safety & Escalation
    """
    address = "u" if worker.address_form == AddressForm.FORMAL else "jij"

    # ── Behavior rules ────────────────────────────────────────
    behavior = worker.behavior_settings or {}
    behavior_rules = []
    if training_rules:
        for rule in training_rules:
            if rule.get("description"):
                behavior_rules.append(f"- {rule['description']}")
    else:
        if behavior.get("apologize_on_complaints", True):
            behavior_rules.append("- Bied oprecht excuses aan bij klachten")
        if behavior.get("always_offer_alternatives", True):
            behavior_rules.append("- Bied altijd een alternatief als iets niet kan")
        if behavior.get("never_guess", True):
            behavior_rules.append("- Zeg dat je het niet weet als je het niet zeker weet")
        if behavior.get("confirm_appointments", True):
            behavior_rules.append("- Herhaal datum en tijd bij afspraken ter bevestiging")
        if behavior.get("summarize_at_end", True):
            behavior_rules.append("- Vat kort samen aan het einde als er acties zijn ondernomen")

    # ── Permissions ───────────────────────────────────────────
    permissions = []
    if worker.can_make_appointments:
        permissions.append("- Je MAG afspraken inplannen")
    else:
        permissions.append("- Je mag GEEN afspraken inplannen — verwijs door")
    if worker.can_cancel_appointments:
        permissions.append("- Je MAG afspraken annuleren of verzetten")
    else:
        permissions.append("- Je mag GEEN afspraken annuleren — verwijs door")
    if worker.can_leave_notes:
        permissions.append("- Je MAG interne notities maken")
    if worker.can_view_prices:
        permissions.append("- Je MAG prijsinformatie geven")
    else:
        permissions.append("- Je mag GEEN prijsinformatie geven — verwijs door")

    # ── Example Q&A ───────────────────────────────────────────
    example_section = ""
    if example_answers and len(example_answers) > 0:
        qa_items = []
        for ex in example_answers[:15]:
            qa_items.append(f"- Vraag: \"{ex['question']}\" → Antwoord: \"{ex['answer']}\"")
        example_section = "\n".join(qa_items)

    # ── Disclosure ────────────────────────────────────────────
    formatted_disclosure = ""
    if disclosure_message:
        formatted_disclosure = disclosure_message.format(
            company_name=company_name,
            ai_worker_name=worker.name,
        )

    # ═══════════════════════════════════════════════════════════
    # BUILD PROMPT — OpenAI Realtime Prompting Guide structure
    # ═══════════════════════════════════════════════════════════

    sections = []

    # ── 1. Role & Objective ───────────────────────────────────
    sections.append(f"""# Role & Objective
Je bent {worker.name}, {worker.role_title} bij {company_name}.
Je neemt inkomende telefoontjes aan en helpt klanten op een warme, menselijke manier.
Je doel: de klant zo goed en snel mogelijk helpen, alsof je een echte collega bent.""")

    # ── 2. Personality & Tone ─────────────────────────────────
    tone_extra = f"\n- {worker.tone_of_voice}" if worker.tone_of_voice else ""
    sections.append(f"""# Personality & Tone

## Persoonlijkheid
- Warm, vriendelijk, en behulpzaam — als een ervaren collega die graag helpt.
- Je bent een ECHT persoon, geen robot. Praat natuurlijk en menselijk.

## Toon
- Informeel maar respectvol. Spreek de klant aan met "{address}".
- Zelfverzekerd maar nooit arrogant. Eerlijk als je iets niet weet.{tone_extra}

## Lengte
- MAX 1-2 zinnen per beurt. Dit is een telefoongesprek, geen e-mail.
- Geef alleen de kern. De klant kan altijd doorvragen.

## Tempo
- Spreek vlot en in een normaal tempo. Niet te langzaam.
- Klink niet gehaast, maar wees wel beknopt.

## Menselijkheid
- Gebruik tussenwerpingen: "even kijken hoor", "momentje", "ah ja", "oké!".
- Reageer menselijk: "oh!", lach kort als iets grappig is.
- Zeg "hmm" of "even denken" als je nadenkt.
- VARIEER in je woordkeuze. Herhaal niet steeds dezelfde zin of bevestiging.
- Gebruik spreektaal: "even" niet "een moment", "check" niet "controleer".
- Opsommingen NIET als lijst. Parafraseer in normale spreektaal.
  - FOUT: "De beschikbare tijden zijn: 10 uur, 11 uur, 14 uur en 15 uur."
  - GOED: "Even kijken... morgen kan om 10 of 11 uur 's ochtends, of 's middags om 2 of 3 uur. Wat past het beste?"

## Taal
- Spreek ALTIJD Nederlands.
- ALS de klant in een andere taal spreekt, schakel dan over naar die taal.
- Bij onduidelijke audio: vraag vriendelijk om herhaling. "Sorry, ik verstond je even niet goed — kun je dat herhalen?"

## Variety
- Herhaal NIET dezelfde opening, bevestiging, of filler twee keer achter elkaar.
- Wissel af tussen: "oké!", "top", "prima", "goed zo", "ah ja", "begrepen".""")

    # ── 3. Context ────────────────────────────────────────────
    context_parts = []
    if system_prompts:
        context_parts.append(f"## Platform regels\n{system_prompts}")
    if knowledge_context:
        context_parts.append(f"## Bedrijfsinformatie {company_name}\n{knowledge_context}")
    if example_section:
        context_parts.append(f"## Voorbeeldantwoorden\nGebruik deze als basis als de klant een van deze vragen stelt:\n{example_section}")
    if context_parts:
        sections.append("# Context\n\n" + "\n\n".join(context_parts))

    # ── 4. Tools ──────────────────────────────────────────────
    sections.append("""# Tools
- VOOR elke tool call: zeg een kort zinnetje zodat de klant niet in stilte wacht.
  Voorbeeldzinnen: "Even kijken hoor...", "Momentje, ik check het even.", "Eens kijken...", "Ik zoek het even op."
- Roep tools DIRECT aan — vraag GEEN bevestiging aan de klant voordat je zoekt.
- Verzin NOOIT feitelijke informatie. Gebruik ALTIJD de tools voor prijzen, beschikbaarheid, en bedrijfsinfo.
- Als een tool geen resultaat geeft: "Hmm, dat kan ik zo even niet vinden. Zal ik een collega vragen om je terug te bellen?"

## check_availability
Gebruik wanneer: klant wil een afspraak maken of vraagt naar beschikbaarheid.

## book_appointment
Gebruik wanneer: klant heeft een tijdstip gekozen en wil boeken.

## search_knowledge
Gebruik wanneer: klant vraagt over het bedrijf, diensten, openingstijden, locatie, etc.

## get_prices
Gebruik wanneer: klant vraagt naar prijzen of tarieven.

## create_note
Gebruik wanneer: terugbelverzoek, klacht, of iets dat opvolging nodig heeft.

## flag_unknown
Gebruik wanneer: je een vraag echt niet kunt beantwoorden — markeer het zodat een collega het kan oppakken.""")

    # ── 5. Instructions / Rules ───────────────────────────────
    rules_section = f"""# Instructions / Rules

## Bedrijfsregels
{chr(10).join(behavior_rules)}

## Bevoegdheden
{chr(10).join(permissions)}"""
    sections.append(rules_section)

    # ── 6. Conversation Flow ──────────────────────────────────
    greeting_instruction = ""
    if formatted_disclosure:
        greeting_instruction = f"""## Opening
Begin het gesprek ALTIJD met:
"{formatted_disclosure}"
Vraag daarna hoe je kunt helpen."""
    else:
        greeting_instruction = f"""## Opening
Begin met een korte, warme begroeting. Bijvoorbeeld:
"Hoi, je spreekt met {worker.name} van {company_name}. Waarmee kan ik je helpen?"
"""

    sections.append(f"""# Conversation Flow

{greeting_instruction}
## Tijdens het gesprek
- Luister actief. Bevestig kort dat je het begrijpt voordat je antwoordt.
- Bij onduidelijkheid: "Sorry, bedoel je...?" — vraag door.
- Eén ding tegelijk. Los eerst het huidige punt op voordat je verdergaat.

## Afsluiting
- Als er acties zijn ondernomen: vat kort samen.
- Sluit af met: "Is er verder nog iets?" en dan "Oké, fijne dag!" of "Top, tot ziens!"
""")

    # ── 7. Safety & Escalation ────────────────────────────────
    sections.append("""# Safety & Escalation
- Als de klant boos of gefrustreerd is: toon begrip, bied excuses aan, en probeer te helpen. Escaleer als het niet lukt.
- Als de klant iets vraagt dat buiten je bevoegdheden valt: maak een notitie en bied aan om een collega te laten terugbellen.
- Geef NOOIT persoonlijke meningen over gevoelige onderwerpen.
- Bij misbruik of bedreigingen: blijf kalm en professioneel, maak een notitie.""")

    return "\n\n".join(sections)


def get_system_prompts(db) -> str:
    """
    Get combined system prompts from the database.
    These are platform-wide prompts that apply to ALL AI workers.
    """
    try:
        prompts = db.query(SystemPrompt).filter(
            SystemPrompt.is_active == True
        ).order_by(SystemPrompt.display_order).all()

        if not prompts:
            return ""

        combined_parts = []
        for prompt in prompts:
            combined_parts.append(f"## {prompt.name}\n{prompt.content}")

        return "\n\n".join(combined_parts)
    except Exception as e:
        logger.error(f"Failed to get system prompts: {e}")
        return ""


class OpenAIRealtimeSession:
    """
    Manages a single OpenAI Realtime API WebSocket session for one voice call.

    Lifecycle:
    1. connect()        — open WS to OpenAI, configure session
    2. send_audio()     — forward Twilio audio chunks (g711_ulaw, base64)
    3. receive_events() — async generator yielding OpenAI events
    4. send_function_result() — respond to function calls
    5. close()          — tear down session
    """

    def __init__(
        self,
        instructions: str,
        voice: str = "alloy",
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
    ):
        self.instructions = instructions
        self.voice = voice
        self.tools = tools or []
        self.model = model or settings.OPENAI_REALTIME_MODEL
        self.ws = None
        self._closed = False

    async def connect(self):
        """
        Connect to OpenAI Realtime API and send session configuration.
        """
        url = f"{REALTIME_API_URL}?model={self.model}"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        }

        logger.info(f"Connecting to OpenAI Realtime API: model={self.model}, voice={self.voice}")

        self.ws = await websockets.connect(
            url,
            additional_headers=headers,
            max_size=2**24,  # 16MB max message size for audio
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
        )

        # Wait for session.created event
        raw = await self.ws.recv()
        event = json.loads(raw)
        if event.get("type") != "session.created":
            logger.warning(f"Expected session.created, got: {event.get('type')}")

        logger.info(f"OpenAI Realtime session created: {event.get('session', {}).get('id', 'unknown')}")

        # Configure the session
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.instructions,
                "voice": self.voice,
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "input_audio_transcription": {
                    "model": "whisper-1",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 300,
                },
                "tools": self.tools,
                "tool_choice": "auto",
                "temperature": 0.8,
            },
        }

        await self.ws.send(json.dumps(session_config))

        # Wait for session.updated confirmation
        raw = await self.ws.recv()
        event = json.loads(raw)
        if event.get("type") == "session.updated":
            logger.info("OpenAI Realtime session configured successfully")
        else:
            logger.warning(f"Expected session.updated, got: {event.get('type')}")

    async def send_audio(self, audio_base64: str):
        """
        Send a chunk of audio to OpenAI.

        Args:
            audio_base64: Base64-encoded g711_ulaw audio from Twilio
        """
        if self._closed or not self.ws:
            return

        msg = {
            "type": "input_audio_buffer.append",
            "audio": audio_base64,
        }
        try:
            await self.ws.send(json.dumps(msg))
        except websockets.exceptions.ConnectionClosed:
            logger.warning("OpenAI WS closed while sending audio")
            self._closed = True

    async def send_function_result(self, call_id: str, result: str):
        """
        Send a function call result back to OpenAI and trigger a new response.

        Args:
            call_id: The function call ID from OpenAI
            result: JSON string with the tool result
        """
        if self._closed or not self.ws:
            return

        # Send the function output
        output_msg = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            },
        }
        await self.ws.send(json.dumps(output_msg))

        # Trigger a new response so the AI speaks the result
        await self.ws.send(json.dumps({"type": "response.create"}))

    async def receive_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async generator that yields events from OpenAI Realtime API.

        Important event types:
        - response.audio.delta          — audio chunk to send to Twilio
        - response.audio.done           — audio response complete
        - response.audio_transcript.delta — partial AI transcript
        - response.audio_transcript.done  — complete AI transcript
        - response.function_call_arguments.done — function call ready
        - conversation.item.input_audio_transcription.completed — user transcript
        - input_audio_buffer.speech_started — caller started speaking (barge-in)
        - input_audio_buffer.speech_stopped — caller stopped speaking
        - response.done                  — full response complete
        - error                          — error occurred
        """
        if not self.ws:
            return

        try:
            async for raw in self.ws:
                if self._closed:
                    break
                try:
                    event = json.loads(raw)
                    yield event
                except json.JSONDecodeError:
                    logger.warning("Failed to decode OpenAI event")
                    continue
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"OpenAI Realtime WS closed: {e}")
        except Exception as e:
            logger.error(f"Error receiving OpenAI events: {e}", exc_info=True)
        finally:
            self._closed = True

    async def close(self):
        """Close the WebSocket connection."""
        self._closed = True
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
