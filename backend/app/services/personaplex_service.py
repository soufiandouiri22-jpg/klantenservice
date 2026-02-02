"""
klantenservice.ai - PersonaPlex-7B Integration Service
Real-time speech-to-speech conversational AI for phone calls

This service connects to PersonaPlex-7B running on RunPod Serverless.
For local development without RunPod, it operates in mock mode.

PersonaPlex is NVIDIA's full-duplex speech-to-speech model that:
- Handles audio input directly (no separate STT needed)
- Generates audio output directly (no separate TTS needed)
- Supports natural conversation dynamics (interruptions, barge-ins)
- Can be conditioned with voice prompts and text personas

Reference: https://huggingface.co/nvidia/personaplex-7b-v1
"""
import asyncio
import aiohttp
import base64
import logging
import os
from typing import Optional, AsyncGenerator, Any
from dataclasses import dataclass

from app.core.config import get_settings
from app.models.ai_worker import AIWorker, AddressForm
from app.models.system_prompt import SystemPrompt

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
    conversation_history: list = None
    
    def __post_init__(self):
        if self.conversation_history is None:
            self.conversation_history = []


class PersonaPlexService:
    """
    Service for managing PersonaPlex-7B conversations via RunPod Serverless.
    
    This service handles:
    - Building persona prompts from AI worker settings
    - Managing conversation sessions
    - Sending audio to RunPod and receiving responses
    - Processing audio streams bidirectionally
    """
    
    def __init__(self):
        self.runpod_api_key = settings.RUNPOD_API_KEY
        self.runpod_endpoint_id = settings.RUNPOD_ENDPOINT_ID
        self.mock_mode = not self.runpod_api_key or not self.runpod_endpoint_id
        self.active_sessions: dict[str, ConversationSession] = {}
        
        if self.mock_mode:
            logger.warning(
                "PersonaPlex running in MOCK MODE (no RunPod endpoint configured). "
                "Set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID for production use."
            )
        else:
            logger.info(f"PersonaPlex configured with RunPod endpoint: {self.runpod_endpoint_id}")
    
    @property
    def runpod_url(self) -> str:
        """Get the RunPod API URL for the endpoint."""
        return f"https://api.runpod.ai/v2/{self.runpod_endpoint_id}"
    
    @property
    def headers(self) -> dict:
        """Get headers for RunPod API requests."""
        return {
            "Authorization": f"Bearer {self.runpod_api_key}",
            "Content-Type": "application/json"
        }
    
    def get_system_prompts(self, db) -> str:
        """
        Get combined system prompts from the database.
        These are platform-wide prompts that apply to ALL AI workers.
        
        Args:
            db: Database session
            
        Returns:
            Combined system prompt string
        """
        try:
            prompts = db.query(SystemPrompt).filter(
                SystemPrompt.is_active == True
            ).order_by(SystemPrompt.display_order).all()
            
            if not prompts:
                return ""
            
            # Combine all active prompts
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
        
        This prompt defines the AI's personality, behavior rules, and permissions
        that will guide the conversation.
        
        Args:
            worker: The AI worker configuration
            company_name: Name of the company for context
            knowledge_context: Optional RAG context from website knowledge
            training_rules: Optional list of enabled training rules
            example_answers: Optional list of Q&A pairs for common questions
            system_prompts: Optional pre-fetched system prompts string
            
        Returns:
            Formatted persona prompt string
        """
        # Determine address form
        address = "u" if worker.address_form == AddressForm.FORMAL else "jij"
        
        # Get behavior settings with defaults
        behavior = worker.behavior_settings or {}
        
        # Build behavior rules from training_rules if provided, otherwise use defaults
        behavior_rules = []
        
        if training_rules:
            # Use the company's custom training rules
            for rule in training_rules:
                if rule.get("description"):
                    behavior_rules.append(f"- {rule['description']}")
        else:
            # Fallback to default behavior settings
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
            for ex in example_answers[:20]:  # Limit to 20 examples
                qa_items.append(f"V: {ex['question']}\nA: {ex['answer']}")
            example_qa_section = f"""
## Voorbeeldantwoorden
Als de klant een van deze vragen stelt, gebruik dan het bijbehorende antwoord als basis:

{chr(10).join(qa_items)}
"""
        
        # Build the complete prompt with system prompts first
        prompt_parts = []
        
        # 1. System-wide base prompts (from /admin)
        if system_prompts:
            prompt_parts.append(f"""# BASISINSTRUCTIES (klantenservice.ai)
{system_prompts}""")
        
        # 2. Company/Worker specific configuration
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
    
    async def _call_runpod(self, payload: dict, timeout: int = 30) -> dict:
        """
        Make a synchronous call to RunPod endpoint.
        
        Args:
            payload: The request payload
            timeout: Request timeout in seconds
            
        Returns:
            Response from RunPod
        """
        async with aiohttp.ClientSession() as session:
            # Use /runsync for synchronous execution (waits for result)
            url = f"{self.runpod_url}/runsync"
            
            async with session.post(
                url,
                json={"input": payload},
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"RunPod API error: {response.status} - {error_text}")
                    return {"error": f"RunPod API error: {response.status}"}
                
                result = await response.json()
                
                # Check job status
                if result.get("status") == "COMPLETED":
                    return result.get("output", {})
                elif result.get("status") == "FAILED":
                    return {"error": result.get("error", "Unknown error")}
                else:
                    # Job might be queued or in progress
                    return {"status": result.get("status"), "id": result.get("id")}
    
    async def _call_runpod_async(self, payload: dict) -> str:
        """
        Start an async job on RunPod.
        
        Returns:
            Job ID for polling
        """
        async with aiohttp.ClientSession() as session:
            url = f"{self.runpod_url}/run"
            
            async with session.post(
                url,
                json={"input": payload},
                headers=self.headers
            ) as response:
                result = await response.json()
                return result.get("id")
    
    async def _poll_job_status(self, job_id: str, timeout: int = 60) -> dict:
        """Poll for job completion."""
        async with aiohttp.ClientSession() as session:
            url = f"{self.runpod_url}/status/{job_id}"
            
            start_time = asyncio.get_event_loop().time()
            
            while True:
                async with session.get(url, headers=self.headers) as response:
                    result = await response.json()
                    
                    status = result.get("status")
                    if status == "COMPLETED":
                        return result.get("output", {})
                    elif status == "FAILED":
                        return {"error": result.get("error", "Job failed")}
                    
                    # Check timeout
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        return {"error": "Job timeout"}
                    
                    # Wait before polling again
                    await asyncio.sleep(0.5)
    
    async def create_session(
        self,
        session_id: str,
        worker: AIWorker,
        company_name: str,
        voice_prompt_path: Optional[str] = None,
        knowledge_context: Optional[str] = None,
        training_rules: Optional[list] = None,
        example_answers: Optional[list] = None,
        system_prompts: Optional[str] = None
    ) -> ConversationSession:
        """
        Create a new conversation session.
        
        Args:
            session_id: Unique identifier for this session (usually call_log.id)
            worker: The AI worker handling this call
            company_name: Name of the company
            voice_prompt_path: Optional path to voice prompt audio for voice cloning
            knowledge_context: Optional RAG context from website knowledge
            training_rules: Optional list of enabled training rules
            example_answers: Optional list of Q&A pairs for common questions
            system_prompts: Optional pre-fetched system prompts string
            
        Returns:
            ConversationSession object
        """
        # Build persona prompt
        persona_prompt = self.build_persona_prompt(
            worker=worker,
            company_name=company_name,
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
        
        # Initialize session on RunPod (warm up)
        if not self.mock_mode:
            try:
                result = await self._call_runpod({
                    "action": "init",
                    "session_id": session_id
                }, timeout=60)
                logger.info(f"RunPod session initialized: {result}")
            except Exception as e:
                logger.error(f"Failed to initialize RunPod session: {e}")
        
        return session
    
    async def process_audio(
        self,
        session_id: str,
        audio_chunk: bytes
    ) -> AsyncGenerator[bytes, None]:
        """
        Process incoming audio and yield response audio chunks.
        
        This is the main processing loop that:
        1. Receives audio from the caller
        2. Sends it to RunPod
        3. Yields response audio chunks
        
        Args:
            session_id: The session identifier
            audio_chunk: PCM audio bytes at 24kHz
            
        Yields:
            Response audio chunks (PCM at 24kHz)
        """
        session = self.active_sessions.get(session_id)
        
        if not session or not session.is_active:
            logger.warning(f"Session {session_id} not found or inactive")
            return
        
        # Mock mode: just log that we received audio (no response)
        if self.mock_mode:
            logger.debug(f"Mock mode: received {len(audio_chunk)} bytes for session {session_id}")
            return
        
        try:
            # Encode audio as base64
            audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
            
            # Send to RunPod
            result = await self._call_runpod({
                "action": "process",
                "session_id": session_id,
                "audio": audio_b64,
                "persona_prompt": session.persona_prompt
            }, timeout=10)
            
            if "error" in result:
                logger.error(f"RunPod processing error: {result['error']}")
                return
            
            # Get response audio
            response_audio_b64 = result.get("audio")
            if response_audio_b64:
                response_bytes = base64.b64decode(response_audio_b64)
                
                # Yield in chunks for streaming
                chunk_size = 4800  # 100ms at 24kHz
                for i in range(0, len(response_bytes), chunk_size):
                    yield response_bytes[i:i+chunk_size]
            
            # Store transcript if available
            transcript = result.get("transcript", {})
            if transcript:
                session.conversation_history.append(transcript)
                    
        except asyncio.TimeoutError:
            logger.warning(f"RunPod request timeout for session {session_id}")
        except Exception as e:
            logger.error(f"Error processing audio for session {session_id}: {e}")
    
    async def get_transcript(self, session_id: str) -> Optional[dict]:
        """
        Get the transcript from the session.
        
        Returns:
            Dictionary with 'user' and 'assistant' transcript texts
        """
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
        """
        End a conversation session and cleanup resources.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Final transcript if available
        """
        session = self.active_sessions.get(session_id)
        
        if not session:
            logger.warning(f"Session {session_id} not found")
            return None
        
        logger.info(f"Ending PersonaPlex session {session_id}")
        
        # Get final transcript before closing
        transcript = await self.get_transcript(session_id)
        
        # Notify RunPod to end session
        if not self.mock_mode:
            try:
                await self._call_runpod({
                    "action": "end",
                    "session_id": session_id
                }, timeout=5)
            except Exception as e:
                logger.error(f"Error ending RunPod session: {e}")
        
        # Mark as inactive and remove
        session.is_active = False
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        return transcript
    
    def get_active_session_count(self) -> int:
        """Get the number of active sessions"""
        return len(self.active_sessions)


# Singleton instance
personaplex_service = PersonaPlexService()
