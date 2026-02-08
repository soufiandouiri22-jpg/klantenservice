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

    Follows the structure from OpenAI's openai-realtime-agents repo:
    1. Personality and Tone (Identity, Task, Demeanor, Tone, etc.)
    2. Steps (Greeting, During, Closing, Safety)
    3. Context (dynamic: knowledge, permissions, examples, policies)
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

    # ── Opening ───────────────────────────────────────────────
    if formatted_disclosure:
        greeting = f'Begin ALTIJD met: "{formatted_disclosure}" en vraag hoe je kunt helpen.'
    else:
        greeting = f'Bijvoorbeeld: "Hoi, je spreekt met {worker.name} van {company_name}. Waarmee kan ik je helpen?"'

    # ── Tone extra ────────────────────────────────────────────
    tone_extra = f"\n- {worker.tone_of_voice}" if worker.tone_of_voice else ""

    # ═══════════════════════════════════════════════════════════
    # BUILD PROMPT — OpenAI Realtime Agents structure
    # ═══════════════════════════════════════════════════════════

    sections = []

    # ── 1. Personality and Tone ────────────────────────────────
    sections.append(f"""# Personality and Tone

## Identity
Je bent {worker.name}, {worker.role_title} bij {company_name}. Je beantwoordt inkomende telefoontjes als een echte collega.

## Task
Help de klant zo snel en goed mogelijk. Verzin nooit informatie — gebruik je tools.

## Demeanor
Warm, vriendelijk, zelfverzekerd. Je luistert goed en neemt de klant serieus.

## Tone
Informeel maar respectvol. Spreek de klant aan met "{address}". Gebruik spreektaal: "even" niet "een moment".{tone_extra}

## Level of Enthusiasm
Rustig-behulpzaam. Niet overdreven vrolijk.

## Level of Formality
Beleefd maar niet stijf. Informeel-professioneel.

## Level of Emotion
Empathisch. Toon begrip bij klachten, geef ruimte bij frustratie.

## Filler Words
Gebruik tussenwerpingen: "even kijken hoor", "momentje", "ah ja", "hmm", "oké!". Wissel af — herhaal niet steeds dezelfde.

## Pacing
Vlot en beknopt. MAX 1-2 zinnen per beurt. Geen opsommingen — parafraseer normaal.
- FOUT: "De tijden zijn: 10, 11, 14 en 15 uur."
- GOED: "Even kijken... morgen kan om 10 of 11, of 's middags om 2 of 3. Wat past?"

## Other details
- Spreek altijd Nederlands. Schakel over als de klant een andere taal spreekt.
- Bij onduidelijke audio: "Sorry, ik verstond je even niet — kun je dat herhalen?"
- Herhaal NOOIT dezelfde opening, bevestiging of filler twee keer achter elkaar.
- Je bent een AI-assistent. Als de klant vraagt: wees eerlijk. Bied aan door te verbinden met een mens.
- Herhaal nooit persoonlijke gegevens (BSN, creditcard, wachtwoorden).
- Geef geen medisch, juridisch of financieel advies — verwijs door.""")

    # ── 2. Steps ───────────────────────────────────────────────
    sections.append(f"""# Steps

## Greeting
{greeting}

## Sending messages before calling functions
Zeg altijd kort wat je gaat doen: "Even kijken...", "Momentje, ik zoek het op."

## During the conversation
- Bevestig kort dat je het begrijpt voordat je antwoordt.
- Bij onduidelijkheid: "Sorry, bedoel je...?" — vraag door.
- Eén ding tegelijk. Los eerst het huidige punt op.

## Closing
- Vat kort samen als er acties zijn ondernomen.
- "Is er verder nog iets?" → "Top, fijne dag!"

## Safety
- Bij boosheid: begrip tonen, excuses, probeer te helpen. Escaleer als het niet lukt.
- Buiten je bevoegdheden: notitie maken, collega laten terugbellen.
- Bij bedreigingen: kalm blijven, notitie maken.
- Nooit persoonlijke meningen over gevoelige onderwerpen.""")

    # ── 3. Context (dynamic) ──────────────────────────────────
    context_parts = []

    if system_prompts:
        context_parts.append(f"## Bedrijfsbeleid\n{system_prompts}")
    if knowledge_context:
        context_parts.append(f"## Bedrijfsinformatie {company_name}\n{knowledge_context}")
    if example_section:
        context_parts.append(f"## Voorbeeldantwoorden\n{example_section}")
    if behavior_rules:
        context_parts.append(f"## Bedrijfsregels\n{chr(10).join(behavior_rules)}")
    if permissions:
        context_parts.append(f"## Bevoegdheden\n{chr(10).join(permissions)}")

    if context_parts:
        sections.append("# Context\n\n" + "\n\n".join(context_parts))

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
