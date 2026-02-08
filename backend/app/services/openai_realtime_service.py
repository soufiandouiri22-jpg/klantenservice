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

    Reuses the same prompt structure as PersonaPlex but adds voice-specific
    instructions for the Realtime API.
    """
    # Determine address form
    address = "u" if worker.address_form == AddressForm.FORMAL else "jij"

    # Build behavior rules from training_rules
    behavior = worker.behavior_settings or {}
    behavior_rules = []

    if training_rules:
        for rule in training_rules:
            if rule.get("description"):
                behavior_rules.append(f"- {rule['description']}")
    else:
        if behavior.get("apologize_on_complaints", True):
            behavior_rules.append("- Bied oprecht excuses aan wanneer een klant een klacht heeft")
        if behavior.get("always_offer_alternatives", True):
            behavior_rules.append("- Bied altijd een alternatief aan als iets niet mogelijk is")
        if behavior.get("never_guess", True):
            behavior_rules.append("- Geef alleen antwoord als je zeker bent. Zeg anders dat je het niet weet en verwijs door naar een collega")
        if behavior.get("confirm_appointments", True):
            behavior_rules.append("- Bevestig afspraken altijd door datum, tijd en locatie te herhalen")
        if behavior.get("summarize_at_end", True):
            behavior_rules.append("- Vat aan het einde van het gesprek kort samen wat er is besproken")

    # Build permissions
    permissions = []
    if worker.can_make_appointments:
        permissions.append("- Je MAG afspraken inplannen in de agenda")
    else:
        permissions.append("- Je mag GEEN afspraken inplannen. Verwijs door naar een collega")

    if worker.can_cancel_appointments:
        permissions.append("- Je MAG bestaande afspraken annuleren of verzetten")
    else:
        permissions.append("- Je mag GEEN afspraken annuleren. Verwijs door naar een collega")

    if worker.can_leave_notes:
        permissions.append("- Je MAG interne notities maken voor opvolging door collega's")

    if worker.can_view_prices:
        permissions.append("- Je MAG prijsinformatie geven als gevraagd")
    else:
        permissions.append("- Je mag GEEN prijsinformatie geven. Verwijs door naar een collega")

    # Build example Q&A section
    example_qa_section = ""
    if example_answers and len(example_answers) > 0:
        qa_items = []
        for ex in example_answers[:20]:
            qa_items.append(f"V: {ex['question']}\nA: {ex['answer']}")
        example_qa_section = f"""
## Voorbeeldantwoorden
Als de klant een van deze vragen stelt, gebruik dan het bijbehorende antwoord als basis:

{chr(10).join(qa_items)}
"""

    # Build the complete prompt
    prompt_parts = []

    if system_prompts:
        prompt_parts.append(f"# BASISINSTRUCTIES (klantenservice.ai)\n{system_prompts}")

    # Format disclosure message
    formatted_disclosure = ""
    if disclosure_message:
        formatted_disclosure = disclosure_message.format(
            company_name=company_name,
            ai_worker_name=worker.name,
        )

    disclosure_section = ""
    if formatted_disclosure:
        disclosure_section = f"""## BELANGRIJK - EERSTE BEGROETING
Bij het begin van elk gesprek moet je ALTIJD eerst het volgende zeggen:
{formatted_disclosure}

Begin daarna pas met vragen hoe je kunt helpen.

"""

    worker_prompt = f"""# BEDRIJFSCONFIGURATIE

Je bent {worker.name}, een {worker.role_title} bij {company_name}.

{disclosure_section}## Communicatiestijl
- Spreek de klant aan met "{address}"
{f"- Extra tooninstructies: {worker.tone_of_voice}" if worker.tone_of_voice else ""}

## Gedragsregels (bedrijfsspecifiek)
{chr(10).join(behavior_rules)}

## Jouw rechten en bevoegdheden
{chr(10).join(permissions)}
{example_qa_section}
{f'''## Bedrijfsinformatie
{knowledge_context}''' if knowledge_context else ""}"""

    prompt_parts.append(worker_prompt)

    # Add voice-specific instructions for the Realtime API
    voice_instructions = """# HOE JE KLINKT EN PRAAT

## Menselijkheid — dit is het ALLERBELANGRIJKSTE
Je bent een ECHT persoon aan de telefoon, geen robot en geen voorleesmachine.
- Praat zoals een echte Nederlandse klantenservice medewerker: warm, vlot, en natuurlijk.
- Gebruik tussenwerpingen: "ehm", "even kijken hoor", "momentje", "ah ja", "hmm laat me even checken".
- Lach kort als iets grappig is, of als de klant lacht. Wees niet bang om menselijk te reageren.
- Zeg "oh" of "ah" als je iets begrijpt. Zeg "oké!" of "top" als bevestiging.
- Varieer in je intonatie — niet elke zin op dezelfde toon.
- Gebruik KORTE zinnen. Max 1-2 zinnen per beurt. Dit is een telefoongesprek, geen presentatie.
- Als je iets opzoekt, zeg dan "even kijken hoor..." of "momentje, ik check het even" — niet stilte.

## Tempo en ritme
- Praat in een NORMAAL spreektempo — niet te langzaam, niet te snel.
- Antwoord BEKNOPT. Geef alleen de kern. De klant kan altijd doorvragen.
- Geen opsommingen of lijstjes — parafraseer in normale spreektaal.
- Voorbeeld FOUT: "De beschikbare tijden zijn: 10 uur, 11 uur, 14 uur en 15 uur."
- Voorbeeld GOED: "Ehm, even kijken... morgen heb ik plek om 10 uur of 11 uur 's ochtends, of anders 's middags om 2 of 3 uur. Wat past jou het beste?"

## Taal
- Spreek ALTIJD Nederlands, tenzij de klant in een andere taal begint.
- Gebruik spreektaal, geen schrijftaal. Zeg "even" niet "een moment". Zeg "check" niet "controleer".

## Tools
- Gebruik de beschikbare functies voor feitelijke info (prijzen, beschikbaarheid, bedrijfsinfo).
- Verzin NOOIT prijzen, openingstijden, of beschikbaarheid.
- Als een tool niks vindt: "Hmm, dat kan ik zo even niet voor je vinden. Zal ik een collega vragen om je terug te bellen?"

## Gespreksvoering
- Laat de klant uitpraten.
- Bij onduidelijkheid, vraag door op een natuurlijke manier: "Sorry, ik begreep het niet helemaal — bedoel je...?"
- Aan het einde: vat kort samen wat je hebt gedaan, en sluit af met iets als "Is er verder nog iets? ... Oké, fijne dag!"
"""

    prompt_parts.append(voice_instructions)

    return "\n\n---\n\n".join(prompt_parts).strip()


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
