"""
klantenservice.ai - PersonaPlex-7B Integration Service
Real-time speech-to-speech conversational AI for phone calls

PersonaPlex is NVIDIA's full-duplex speech-to-speech model that:
- Handles audio input directly (no separate STT needed)
- Generates audio output directly (no separate TTS needed)
- Supports natural conversation dynamics (interruptions, barge-ins)
- Can be conditioned with voice prompts and text personas

Reference: https://huggingface.co/nvidia/personaplex-7b-v1

NOTE: This model requires a GPU with at least 24GB VRAM (A100/H100 recommended).
For local development without GPU, the service will operate in "mock mode".
"""
import asyncio
import logging
import os
from typing import Optional, AsyncGenerator, Any
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.models.ai_worker import AIWorker, AddressForm

settings = get_settings()
logger = logging.getLogger(__name__)

# Check if we have GPU available
try:
    import torch
    HAS_CUDA = torch.cuda.is_available()
    if HAS_CUDA:
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
except ImportError:
    HAS_CUDA = False
    logger.warning("PyTorch not installed - PersonaPlex will run in mock mode")


@dataclass
class ConversationSession:
    """Represents an active conversation session with PersonaPlex"""
    session_id: str
    model_session: Any  # PersonaPlex session object
    worker_id: str
    company_id: str
    is_active: bool = True


class PersonaPlexService:
    """
    Service for managing PersonaPlex-7B conversations.
    
    This service handles:
    - Model loading and initialization
    - Building persona prompts from AI worker settings
    - Managing conversation sessions
    - Processing audio streams bidirectionally
    """
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.device = "cuda" if HAS_CUDA else "cpu"
        self.is_loaded = False
        self.mock_mode = not HAS_CUDA  # Run without actual model if no GPU
        self.active_sessions: dict[str, ConversationSession] = {}
        
    async def load_model(self):
        """
        Load the PersonaPlex-7B model from Hugging Face.
        This should be called once at startup.
        
        The model is loaded from: nvidia/personaplex-7b-v1
        """
        if self.is_loaded:
            return
        
        if self.mock_mode:
            logger.warning(
                "PersonaPlex running in MOCK MODE (no GPU detected). "
                "Audio will be passed through without AI processing. "
                "For production, use a server with NVIDIA GPU."
            )
            self.is_loaded = True
            return
            
        logger.info("Loading PersonaPlex-7B model from Hugging Face...")
        
        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
            
            model_id = "nvidia/personaplex-7b-v1"
            
            # Get Hugging Face token from settings
            hf_token = settings.HUGGINGFACE_TOKEN or None
            if hf_token:
                logger.info("Using Hugging Face token for authentication")
            
            # Load processor (handles audio input/output)
            self.processor = AutoProcessor.from_pretrained(
                model_id,
                token=hf_token,
                trust_remote_code=True,
            )
            
            # Load model with optimizations
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id,
                torch_dtype=torch.bfloat16,
                device_map="auto",  # Automatically distribute across GPUs
                trust_remote_code=True,  # Required for custom model code
                token=hf_token,
            )
            
            self.is_loaded = True
            logger.info("PersonaPlex-7B model loaded successfully")
            
        except ImportError as e:
            logger.error(f"Missing dependency: {e}")
            logger.error("Install with: pip install torch transformers accelerate")
            self.mock_mode = True
            self.is_loaded = True
        except Exception as e:
            logger.error(f"Failed to load PersonaPlex model: {e}")
            logger.warning("Falling back to mock mode")
            self.mock_mode = True
            self.is_loaded = True
    
    def build_persona_prompt(
        self, 
        worker: AIWorker, 
        company_name: str,
        knowledge_context: Optional[str] = None
    ) -> str:
        """
        Build a persona prompt for PersonaPlex from AI worker settings.
        
        This prompt defines the AI's personality, behavior rules, and permissions
        that will guide the conversation.
        
        Args:
            worker: The AI worker configuration
            company_name: Name of the company for context
            knowledge_context: Optional RAG context from website knowledge
            
        Returns:
            Formatted persona prompt string
        """
        # Determine address form
        address = "u" if worker.address_form == AddressForm.FORMAL else "jij"
        address_verb = "bent" if address == "u" else "bent"
        
        # Get behavior settings with defaults
        behavior = worker.behavior_settings or {}
        
        # Build behavior rules
        behavior_rules = []
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
        
        # Build the complete prompt
        prompt = f"""Je bent {worker.name}, een {worker.role_title} bij {company_name}.

## Communicatiestijl
- Spreek de klant aan met "{address}"
- Taal: Nederlands
- Toon: Vriendelijk, professioneel en behulpzaam
{f"- Extra tooninstructies: {worker.tone_of_voice}" if worker.tone_of_voice else ""}

## Gedragsregels
{chr(10).join(behavior_rules)}

## Jouw rechten en bevoegdheden
{chr(10).join(permissions)}

## Belangrijke instructies
- Begin elk gesprek met een vriendelijke begroeting en vraag hoe je kunt helpen
- Luister actief en laat de klant uitpraten
- Als je onderbroken wordt, stop dan met praten en luister
- Gebruik korte, duidelijke zinnen
- Beëindig het gesprek altijd met een vriendelijke afsluiting

{f'''## Bedrijfsinformatie
{knowledge_context}''' if knowledge_context else ""}
"""
        
        return prompt.strip()
    
    async def create_session(
        self,
        session_id: str,
        worker: AIWorker,
        company_name: str,
        voice_prompt_path: Optional[str] = None,
        knowledge_context: Optional[str] = None
    ) -> ConversationSession:
        """
        Create a new conversation session with PersonaPlex.
        
        Args:
            session_id: Unique identifier for this session (usually call_log.id)
            worker: The AI worker handling this call
            company_name: Name of the company
            voice_prompt_path: Optional path to voice prompt audio for voice cloning
            knowledge_context: Optional RAG context from website knowledge
            
        Returns:
            ConversationSession object
        """
        await self.load_model()
        
        # Build persona prompt
        persona_prompt = self.build_persona_prompt(
            worker=worker,
            company_name=company_name,
            knowledge_context=knowledge_context
        )
        
        logger.info(f"Creating PersonaPlex session {session_id} for worker {worker.name}")
        
        model_session = None
        
        if not self.mock_mode and self.model is not None:
            # Create actual model session
            # Store the persona prompt and voice settings for this session
            model_session = {
                "persona_prompt": persona_prompt,
                "voice_prompt_path": voice_prompt_path,
                "conversation_history": [],
                "user_transcript": [],
                "assistant_transcript": [],
            }
        
        session = ConversationSession(
            session_id=session_id,
            model_session=model_session,
            worker_id=str(worker.id),
            company_id=str(worker.company_id),
            is_active=True
        )
        
        self.active_sessions[session_id] = session
        
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
        2. Feeds it to PersonaPlex
        3. Yields response audio chunks in real-time
        
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
            # In mock mode, we don't generate responses
            # This is useful for testing the WebSocket/Twilio integration
            logger.debug(f"Mock mode: received {len(audio_chunk)} bytes for session {session_id}")
            return
        
        try:
            import torch
            import numpy as np
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Process through the model
            inputs = self.processor(
                audio=audio_array,
                sampling_rate=24000,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            # Add persona context
            if session.model_session and "persona_prompt" in session.model_session:
                # Include persona in the generation
                inputs["text_prompt"] = session.model_session["persona_prompt"]
            
            # Generate response audio
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=1024,
                    do_sample=True,
                    temperature=0.7,
                )
            
            # Convert output to audio bytes
            if hasattr(outputs, "audio"):
                response_audio = outputs.audio.cpu().numpy()
                # Convert back to int16 PCM
                response_bytes = (response_audio * 32768).astype(np.int16).tobytes()
                
                # Yield in chunks for streaming
                chunk_size = 4800  # 100ms at 24kHz
                for i in range(0, len(response_bytes), chunk_size):
                    yield response_bytes[i:i+chunk_size]
                    
        except Exception as e:
            logger.error(f"Error processing audio for session {session_id}: {e}")
            # Don't raise - just log and continue
    
    async def get_transcript(self, session_id: str) -> Optional[dict]:
        """
        Get the transcript from the PersonaPlex session.
        
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
        
        try:
            if session.model_session:
                return {
                    "user": " ".join(session.model_session.get("user_transcript", [])),
                    "assistant": " ".join(session.model_session.get("assistant_transcript", []))
                }
            return None
        except Exception as e:
            logger.error(f"Error getting transcript for session {session_id}: {e}")
            return None
    
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
        
        # Clean up session resources
        if session.model_session and not self.mock_mode:
            try:
                # Clear any cached data
                session.model_session.clear() if hasattr(session.model_session, 'clear') else None
            except Exception as e:
                logger.error(f"Error closing session {session_id}: {e}")
        
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
