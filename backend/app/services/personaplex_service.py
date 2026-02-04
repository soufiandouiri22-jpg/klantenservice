"""
klantenservice.ai - PersonaPlex-7B Integration Service
Real-time speech-to-speech conversational AI for phone calls

This service connects to PersonaPlex-7B running on a dedicated RunPod GPU Pod
via WebSocket for low-latency bidirectional audio streaming.

PersonaPlex is NVIDIA's full-duplex speech-to-speech model that:
- Handles audio input directly (no separate STT needed)
- Generates audio output directly (no separate TTS needed)
- Supports natural conversation dynamics (interruptions, barge-ins)
- Can be conditioned with voice prompts and text personas

Reference: https://huggingface.co/nvidia/personaplex-7b-v1
"""
import asyncio
import json
import logging
from typing import Optional, AsyncGenerator, Dict, Tuple
from dataclasses import dataclass, field

import websockets
from websockets.client import WebSocketClientProtocol
import aiohttp

from app.core.config import get_settings
from app.models.ai_worker import AIWorker, AddressForm
from app.models.system_prompt import SystemPrompt
from app.models.company import Company
from app.models.global_config import GlobalConfig

settings = get_settings()
logger = logging.getLogger(__name__)


@dataclass
class ConversationSession:
    """Represents an active conversation session with PersonaPlex"""
    session_id: str
    persona_prompt: str
    worker_id: str
    company_id: str
    is_active: bool = True
    websocket: Optional[WebSocketClientProtocol] = None
    conversation_history: list = field(default_factory=list)  # List of {turn_id, user, assistant}
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    current_turn: int = 0


class PersonaPlexService:
    """
    Service for managing PersonaPlex-7B conversations via WebSocket.
    
    This service handles:
    - Building persona prompts from AI worker settings
    - Managing WebSocket connections to the dedicated pod
    - Bidirectional audio streaming
    - Session lifecycle management
    """
    
    def __init__(self):
        self.pod_url = settings.PERSONAPLEX_POD_URL
        self.pod_token = settings.PERSONAPLEX_POD_TOKEN
        self.mock_mode = not self.pod_url
        self.active_sessions: Dict[str, ConversationSession] = {}
        
        if self.mock_mode:
            logger.warning(
                "PersonaPlex running in MOCK MODE (no pod URL configured). "
                "Set PERSONAPLEX_POD_URL for production use."
            )
        else:
            logger.info(f"PersonaPlex configured with pod URL: {self.pod_url}")
    
    @property
    def ws_url(self) -> str:
        """Get the WebSocket URL for audio streaming."""
        # Convert http(s) to ws(s)
        url = self.pod_url.replace("https://", "wss://").replace("http://", "ws://")
        return url.rstrip("/")
    
    @property
    def http_url(self) -> str:
        """Get the HTTP URL for REST endpoints."""
        return self.pod_url.rstrip("/")
    
    @property
    def headers(self) -> dict:
        """Get headers for HTTP requests."""
        headers = {"Content-Type": "application/json"}
        if self.pod_token:
            headers["Authorization"] = f"Bearer {self.pod_token}"
        return headers
    
    def get_system_prompts(self, db) -> str:
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
    
    def build_persona_prompt(
        self, 
        worker: AIWorker, 
        company_name: str,
        knowledge_context: Optional[str] = None,
        training_rules: Optional[list] = None,
        example_answers: Optional[list] = None,
        system_prompts: Optional[str] = None
    ) -> str:
        """
        Build a persona prompt for PersonaPlex from AI worker settings.
        """
        # Determine address form
        address = "u" if worker.address_form == AddressForm.FORMAL else "jij"
        
        # Get behavior settings with defaults
        behavior = worker.behavior_settings or {}
        
        # Build behavior rules from training_rules if provided
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
            prompt_parts.append(f"""# BASISINSTRUCTIES (klantenservice.ai)
{system_prompts}""")
        
        worker_prompt = f"""# BEDRIJFSCONFIGURATIE

Je bent {worker.name}, een {worker.role_title} bij {company_name}.

## Communicatiestijl
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
        
        return "\n\n---\n\n".join(prompt_parts).strip()
    
    async def _check_pod_health(self) -> bool:
        """Check if the pod is healthy and ready."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.http_url}/health",
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("model_loaded", False)
                    return False
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def _connect_websocket(self, session_id: str) -> WebSocketClientProtocol:
        """Establish WebSocket connection to the pod."""
        url = f"{self.ws_url}/stream/{session_id}"
        if self.pod_token:
            url += f"?token={self.pod_token}"
        
        logger.info(f"Connecting WebSocket to {url}")
        
        ws = await websockets.connect(
            url,
            ping_interval=20,
            ping_timeout=10,
            close_timeout=5,
            max_size=10 * 1024 * 1024,  # 10MB max message size
        )
        
        logger.info(f"WebSocket connected for session {session_id}")
        return ws
    
    def _get_voice_preset(self, company: Optional[Company], db) -> str:
        """
        Get voice preset: company override > platform default > hardcoded fallback.
        
        Args:
            company: The company (may have admin_overrides)
            db: Database session
            
        Returns:
            Voice preset filename (e.g., "NATF2.pt")
        """
        # 1. Check company-level override
        if company and company.admin_overrides:
            preset = company.admin_overrides.get("voice_preset")
            if preset:
                logger.debug(f"Using company voice preset: {preset}")
                return preset
        
        # 2. Check platform-wide default
        if db:
            try:
                config = db.query(GlobalConfig).filter(
                    GlobalConfig.key == "voice_default_preset"
                ).first()
                if config and config.value:
                    logger.debug(f"Using platform voice preset: {config.value}")
                    return config.value
            except Exception as e:
                logger.warning(f"Could not get platform voice preset: {e}")
        
        # 3. Hardcoded fallback
        logger.debug("Using hardcoded fallback voice preset: NATF2.pt")
        return "NATF2.pt"

    async def create_session(
        self,
        session_id: str,
        worker: AIWorker,
        company: Company,
        db,
        voice_prompt_path: Optional[str] = None,
        knowledge_context: Optional[str] = None,
        training_rules: Optional[list] = None,
        example_answers: Optional[list] = None,
        system_prompts: Optional[str] = None
    ) -> ConversationSession:
        """
        Create a new conversation session with WebSocket connection.
        
        Args:
            session_id: Unique session identifier
            worker: The AI worker handling this call
            company: The company (for name + admin_overrides)
            db: Database session (for platform defaults lookup)
            voice_prompt_path: Override voice preset (optional)
            knowledge_context: RAG context from website scraping
            training_rules: Company-specific training rules
            example_answers: Company-specific example Q&A
            system_prompts: Platform-wide system prompts
        """
        # Build persona prompt
        persona_prompt = self.build_persona_prompt(
            worker=worker,
            company_name=company.name,
            knowledge_context=knowledge_context,
            training_rules=training_rules,
            example_answers=example_answers,
            system_prompts=system_prompts
        )
        
        logger.info(f"Creating PersonaPlex session {session_id} for worker {worker.name}")
        
        session = ConversationSession(
            session_id=session_id,
            persona_prompt=persona_prompt,
            worker_id=str(worker.id),
            company_id=str(worker.company_id),
            is_active=True
        )
        
        self.active_sessions[session_id] = session
        
        if self.mock_mode:
            logger.info(f"Mock mode: session {session_id} created (no real connection)")
            return session
        
        # Get voice preset: explicit param > company override > platform default
        voice_preset = voice_prompt_path or self._get_voice_preset(company, db)
        
        try:
            # Connect WebSocket
            ws = await self._connect_websocket(session_id)
            session.websocket = ws
            
            # Send initialization message
            init_message = {
                "persona_prompt": persona_prompt,
                "voice_prompt": voice_preset
            }
            await ws.send(json.dumps(init_message))
            
            logger.info(f"Session {session_id} using voice preset: {voice_preset}")
            
            # Wait for confirmation
            response = await asyncio.wait_for(ws.recv(), timeout=120)
            response_data = json.loads(response)
            
            if response_data.get("status") == "initialized":
                logger.info(f"Session {session_id} initialized successfully")
            else:
                logger.warning(f"Unexpected init response: {response_data}")
            
        except asyncio.TimeoutError:
            logger.error(f"Session init timeout for {session_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}", exc_info=True)
            raise
        
        return session
    
    async def start_turn(self, session_id: str, turn_id: int) -> bool:
        """
        Start a new turn before sending audio segment.
        Must be called before process_audio_segment.
        """
        session = self.active_sessions.get(session_id)
        
        if not session or not session.is_active:
            logger.warning(f"Session {session_id} not found or inactive")
            return False
        
        session.current_turn = turn_id
        
        if self.mock_mode:
            logger.debug(f"Mock mode: started turn {turn_id}")
            return True
        
        ws = session.websocket
        if not ws:
            logger.error(f"No WebSocket connection for session {session_id}")
            return False
        
        try:
            await ws.send(json.dumps({
                "action": "start_turn",
                "turn_id": turn_id
            }))
            
            # Wait for confirmation
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data.get("status") == "turn_started":
                logger.debug(f"Session {session_id}: turn {turn_id} started")
                return True
            else:
                logger.warning(f"Unexpected start_turn response: {data}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting turn: {e}")
            return False
    
    async def process_audio_segment(
        self,
        session_id: str,
        audio_segment: bytes,
        turn_id: int
    ) -> Tuple[Optional[bytes], str, int]:
        """
        Process a complete audio segment (one utterance) and return response.
        
        This is called once per utterance-segment (not per Twilio chunk).
        Returns: (audio_bytes, assistant_transcript, turn_id)
        
        Protocol:
        1. start_turn must have been called first
        2. Send audio bytes
        3. Receive JSON (transcript_final) first
        4. Receive audio bytes second
        """
        session = self.active_sessions.get(session_id)
        
        if not session or not session.is_active:
            logger.warning(f"Session {session_id} not found or inactive")
            return None, "", turn_id
        
        if self.mock_mode:
            logger.debug(f"Mock mode: received {len(audio_segment)} bytes segment for turn {turn_id}")
            return None, "[Mock mode - no transcript]", turn_id
        
        ws = session.websocket
        if not ws:
            logger.error(f"No WebSocket connection for session {session_id}")
            return None, "", turn_id
        
        try:
            async with session._lock:
                # Send audio segment bytes
                await ws.send(audio_segment)
                
                assistant_text = ""
                audio_response = None
                received_turn_id = turn_id
                
                # First: receive JSON (transcript_final)
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    
                    if isinstance(response, str):
                        data = json.loads(response)
                        if data.get("event") == "transcript_final":
                            assistant_text = data.get("assistant", "")
                            received_turn_id = data.get("turn_id", turn_id)
                            logger.debug(f"Received transcript_final for turn {received_turn_id}")
                            
                            # Store in conversation history
                            session.conversation_history.append({
                                "turn_id": received_turn_id,
                                "user": data.get("user", ""),
                                "assistant": assistant_text
                            })
                        elif "error" in data:
                            logger.error(f"Pod error: {data['error']}")
                            return None, "", turn_id
                    elif isinstance(response, bytes):
                        # Unexpected: bytes first (shouldn't happen with new protocol)
                        logger.warning("Received bytes before JSON - old protocol?")
                        audio_response = response
                
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for transcript_final")
                    return None, "", turn_id
                
                # Second: receive audio bytes (if not already received)
                if audio_response is None:
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        
                        if isinstance(response, bytes):
                            audio_response = response
                            logger.debug(f"Received {len(audio_response)} bytes audio for turn {received_turn_id}")
                        elif isinstance(response, str):
                            # Might be an error
                            data = json.loads(response)
                            if "error" in data:
                                logger.error(f"Pod error during audio recv: {data['error']}")
                    
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout waiting for audio response")
                
                return audio_response, assistant_text, received_turn_id
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket closed for session {session_id}: {e}")
            session.websocket = None
            # Try to reconnect
            try:
                ws = await self._connect_websocket(session_id)
                session.websocket = ws
                # Re-init session
                await ws.send(json.dumps({
                    "persona_prompt": session.persona_prompt
                }))
                logger.info(f"Reconnected WebSocket for session {session_id}")
            except Exception as reconnect_error:
                logger.error(f"Failed to reconnect: {reconnect_error}")
            return None, "", turn_id
        except Exception as e:
            logger.error(f"Error processing audio segment for session {session_id}: {e}")
            return None, "", turn_id
    
    async def update_context(
        self,
        session_id: str,
        turn_id: int,
        facts: str,
        instructions: str
    ) -> bool:
        """
        Send context update to the pod for a specific turn.
        
        This does NOT reset streaming - the pod stores it and applies
        at the start of the next process_audio call.
        """
        session = self.active_sessions.get(session_id)
        
        if not session or not session.is_active:
            logger.warning(f"Session {session_id} not found or inactive")
            return False
        
        if self.mock_mode:
            logger.debug(f"Mock mode: update_context for turn {turn_id}")
            return True
        
        ws = session.websocket
        if not ws:
            logger.error(f"No WebSocket connection for session {session_id}")
            return False
        
        try:
            await ws.send(json.dumps({
                "action": "update_context",
                "turn_id": turn_id,
                "facts": facts or "",
                "instructions": instructions or ""
            }))
            
            # Wait for confirmation
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(response)
            
            if data.get("status") == "context_updated":
                logger.debug(f"Session {session_id}: context updated for turn {turn_id}")
                return True
            else:
                logger.warning(f"Unexpected update_context response: {data}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating context: {e}")
            return False
    
    async def process_audio(
        self,
        session_id: str,
        audio_chunk: bytes
    ) -> AsyncGenerator[bytes, None]:
        """
        DEPRECATED: Use start_turn + process_audio_segment instead.
        
        This method is kept for backwards compatibility but should not be used
        with the new turn-based protocol.
        """
        session = self.active_sessions.get(session_id)
        
        if not session or not session.is_active:
            logger.warning(f"Session {session_id} not found or inactive")
            return
        
        if self.mock_mode:
            logger.debug(f"Mock mode: received {len(audio_chunk)} bytes for session {session_id}")
            return
        
        ws = session.websocket
        if not ws:
            logger.error(f"No WebSocket connection for session {session_id}")
            return
        
        try:
            async with session._lock:
                # Send audio bytes directly
                await ws.send(audio_chunk)
                
                # Receive response with timeout
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    
                    if isinstance(response, bytes):
                        # Audio response
                        logger.debug(f"Received {len(response)} bytes audio response")
                        
                        # Yield in chunks for streaming
                        chunk_size = 4800  # 100ms at 24kHz
                        for i in range(0, len(response), chunk_size):
                            yield response[i:i+chunk_size]
                    
                    elif isinstance(response, str):
                        # JSON response (possibly error or transcript)
                        data = json.loads(response)
                        if "error" in data:
                            logger.error(f"Pod error: {data['error']}")
                        elif data.get("event") == "transcript_final":
                            session.conversation_history.append({
                                "turn_id": data.get("turn_id", 0),
                                "user": data.get("user", ""),
                                "assistant": data.get("assistant", "")
                            })
                            # Now wait for audio
                            try:
                                audio_response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                                if isinstance(audio_response, bytes):
                                    chunk_size = 4800
                                    for i in range(0, len(audio_response), chunk_size):
                                        yield audio_response[i:i+chunk_size]
                            except asyncio.TimeoutError:
                                pass
                
                except asyncio.TimeoutError:
                    # No response yet, that's okay for streaming
                    pass
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket closed for session {session_id}: {e}")
            session.websocket = None
            # Try to reconnect
            try:
                ws = await self._connect_websocket(session_id)
                session.websocket = ws
                # Re-init session
                await ws.send(json.dumps({
                    "persona_prompt": session.persona_prompt
                }))
                logger.info(f"Reconnected WebSocket for session {session_id}")
            except Exception as reconnect_error:
                logger.error(f"Failed to reconnect: {reconnect_error}")
        except Exception as e:
            logger.error(f"Error processing audio for session {session_id}: {e}")
    
    async def get_transcript(self, session_id: str) -> Optional[dict]:
        """Get the transcript from the session."""
        session = self.active_sessions.get(session_id)
        
        if not session:
            return None
        
        if self.mock_mode:
            return {
                "user": "[Mock mode - no transcript available]",
                "assistant": "[Mock mode - no transcript available]"
            }
        
        # Combine all conversation history
        user_parts = []
        assistant_parts = []
        
        for entry in session.conversation_history:
            if entry.get("user"):
                user_parts.append(entry["user"])
            if entry.get("assistant"):
                assistant_parts.append(entry["assistant"])
        
        return {
            "user": " ".join(user_parts),
            "assistant": " ".join(assistant_parts)
        }
    
    async def end_session(self, session_id: str) -> Optional[dict]:
        """End a conversation session and cleanup resources."""
        session = self.active_sessions.get(session_id)
        
        if not session:
            logger.warning(f"Session {session_id} not found")
            return None
        
        logger.info(f"Ending PersonaPlex session {session_id}")
        
        # Get final transcript
        transcript = await self.get_transcript(session_id)
        
        # Close WebSocket
        if session.websocket:
            try:
                # Send end message
                await session.websocket.send(json.dumps({"action": "end"}))
                
                # Wait for transcript response
                try:
                    response = await asyncio.wait_for(session.websocket.recv(), timeout=5)
                    data = json.loads(response)
                    if "transcript" in data:
                        transcript = data["transcript"]
                except asyncio.TimeoutError:
                    pass
                
                await session.websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        # Cleanup
        session.is_active = False
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        return transcript
    
    def get_active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self.active_sessions)


# Singleton instance
personaplex_service = PersonaPlexService()
