"""
klantenservice.ai - PersonaPlex Dedicated Pod Server
Real-time speech-to-speech conversational AI using NVIDIA PersonaPlex

This server runs on a dedicated RunPod GPU Pod and handles:
- WebSocket connections for bidirectional audio streaming
- Session management for concurrent calls
- Health checks for monitoring

Unlike the serverless handler, this maintains persistent sessions
in memory, eliminating routing issues and reducing latency.
"""
import os
import asyncio
import base64
import logging
import json
from typing import Optional, Dict, Tuple
from pathlib import Path
from contextlib import asynccontextmanager

import numpy as np
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Moshi IndexError patch - fixes 4 overflow bugs in transformer.py
from patch_moshi import apply_moshi_patch

# Global model instances (loaded once at startup)
mimi = None
other_mimi = None
lm_gen = None
text_tokenizer = None
frame_size = None
device = "cuda" if torch.cuda.is_available() else "cpu"

# Session storage - persistent in memory
sessions: Dict[str, "MoshiSession"] = {}

# Global lock: one process_audio at a time (prompt state is global in lm_gen)
_process_audio_lock = asyncio.Lock()

# Threading lock: serializes session init (runs in thread executor, shares global models)
import threading
_init_lock = threading.Lock()

# Authentication token (set via environment)
API_TOKEN = os.getenv("PERSONAPLEX_API_TOKEN", "")


class MoshiSession:
    """Represents an active Moshi conversation session with turn-based context."""
    
    def __init__(self, session_id: str, persona_prompt: str, voice_prompt: str = "NATF2.pt"):
        self.session_id = session_id
        self.persona_prompt = persona_prompt
        self.voice_prompt = voice_prompt
        self.transcript_user: list = []
        self.transcript_assistant: list = []
        self.is_active = True
        
        # Turn-based context management
        self.current_turn: int = 0
        self.context_by_turn: Dict[int, Tuple[str, str]] = {}  # turn_id -> (facts, instructions)
        
        # Skip step_system_prompts on first process_audio since init already did it
        self._init_prompts_active = True
    
    def start_turn(self, turn_id: int):
        """Start a new turn (called before process_audio for this segment)."""
        self.current_turn = turn_id
        logger.debug(f"Session {self.session_id}: started turn {turn_id}")
    
    def update_context(self, turn_id: int, facts: str = "", instructions: str = ""):
        """Store context for a turn. Does NOT reset streaming - that happens in process_audio."""
        self.context_by_turn[turn_id] = (facts.strip(), instructions.strip())
        logger.debug(f"Session {self.session_id}: stored context for turn {turn_id}")
        # Clean up old turns (keep last 10)
        if len(self.context_by_turn) > 10:
            old_turns = sorted(self.context_by_turn.keys())[:-10]
            for t in old_turns:
                del self.context_by_turn[t]
    
    def _get_effective_prompt(self) -> str:
        """Build effective prompt: persona + context for current turn."""
        parts = [self.persona_prompt]
        
        # Get context for current turn (or most recent applicable turn)
        facts, instructions = "", ""
        if self.current_turn in self.context_by_turn:
            facts, instructions = self.context_by_turn[self.current_turn]
        elif self.context_by_turn:
            # Fallback: use most recent turn <= current_turn
            applicable = [t for t in self.context_by_turn.keys() if t <= self.current_turn]
            if applicable:
                facts, instructions = self.context_by_turn[max(applicable)]
        
        if facts:
            parts.append("\n\n[ACTUELE FEITEN - ALLEEN DEZE GEBRUIKEN]\n" + facts)
        if instructions:
            parts.append("\n\n[INSTRUCTIES]\n" + instructions)
        
        return "".join(parts)
    
    def _process_audio_sync(self, audio_bytes: bytes) -> Tuple[bytes, str]:
        """
        Synchronous audio processing (runs in thread executor).
        
        Contains all blocking GPU operations for processing an audio segment.
        """
        global mimi, other_mimi, lm_gen, text_tokenizer, frame_size
        
        from moshi.models.lm import _iterate_audio as lm_iterate_audio
        from moshi.models.lm import encode_from_sphn as lm_encode_from_sphn
        
        # On first turn after init, skip step_system_prompts (already done during init)
        # This makes the initial greeting response fast (~2-3s instead of 30-60s)
        if self._init_prompts_active:
            logger.info(f"Session {self.session_id}: using init prompts (fast path)")
            self._init_prompts_active = False
        else:
            # Apply this session's prompt + context (safe boundary: start of utterance segment)
            effective_prompt = self._get_effective_prompt()
            lm_gen.text_prompt_tokens = text_tokenizer.encode(wrap_with_system_tags(effective_prompt))
            lm_gen.step_system_prompts(mimi)
            mimi.reset_streaming()
        
        # Convert bytes to tensor - shape must be (1, T) for _iterate_audio
        # Keep on CPU: _iterate_audio uses numpy ops internally;
        # encode_from_sphn handles the CPU→GPU transfer.
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        user_audio = torch.from_numpy(audio_np).unsqueeze(0)
        
        generated_frames = []
        generated_text = []
        
        # Process through model
        for user_encoded in lm_encode_from_sphn(
            mimi,
            lm_iterate_audio(user_audio, sample_interval_size=frame_size, pad=True),
            max_batch=1,
        ):
            steps = user_encoded.shape[-1]
            for c in range(steps):
                try:
                    step_in = user_encoded[:, :, c : c + 1]
                    tokens = lm_gen.step(step_in)
                    
                    if tokens is None:
                        continue
                    
                    # Decode audio
                    pcm = mimi.decode(tokens[:, 1:9])
                    _ = other_mimi.decode(tokens[:, 1:9])
                    pcm_np = pcm.detach().cpu().numpy()[0, 0]
                    generated_frames.append(pcm_np)
                    
                    # Decode text token
                    text_token = tokens[0, 0, 0].item()
                    if text_token not in (0, 3):  # Skip PAD tokens
                        text = text_tokenizer.id_to_piece(text_token)
                        text = text.replace("▁", " ")
                        generated_text.append(text)
                except IndexError as e:
                    logger.error(f"Index error at step {c}/{steps}: {e}")
                    # Break on index error to return what we have so far
                    break
                except Exception as e:
                    logger.error(f"Error processing step {c}: {e}")
                    continue
        
        if len(generated_frames) == 0:
            return b"", ""
        
        # Concatenate and convert to bytes
        output_pcm = np.concatenate(generated_frames, axis=-1)
        output_bytes = (output_pcm * 32768).astype(np.int16).tobytes()
        
        # Store transcript
        assistant_text = "".join(generated_text)
        if assistant_text:
            self.transcript_assistant.append(assistant_text)
        
        return output_bytes, assistant_text

    async def process_audio(self, audio_bytes: bytes) -> Tuple[bytes, str]:
        """
        Process audio input and return (response_audio, assistant_text).
        
        This is called once per utterance-segment (not per Twilio chunk).
        Runs blocking GPU operations in a thread executor so the event loop
        stays responsive for WebSocket ping/pong handling.
        """
        global _process_audio_lock
        
        async with _process_audio_lock:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._process_audio_sync,
                audio_bytes
            )


def load_models():
    """Load PersonaPlex/Moshi models from HuggingFace."""
    global mimi, other_mimi, lm_gen, text_tokenizer, frame_size
    
    if mimi is not None:
        logger.info("Models already loaded")
        return
    
    logger.info(f"Loading PersonaPlex models on {device}...")
    
    from moshi.models import loaders, LMGen
    import sentencepiece
    from huggingface_hub import hf_hub_download
    
    # Apply Moshi patches BEFORE any model inference
    apply_moshi_patch()
    
    hf_repo = "nvidia/personaplex-7b-v1"
    
    # Download config
    hf_hub_download(hf_repo, "config.json")
    
    # Load Mimi encoders/decoders
    logger.info("Loading Mimi encoder/decoder...")
    mimi_weight = hf_hub_download(hf_repo, loaders.MIMI_NAME)
    mimi = loaders.get_mimi(mimi_weight, device)
    other_mimi = loaders.get_mimi(mimi_weight, device)
    
    # Load tokenizer
    logger.info("Loading tokenizer...")
    tokenizer_path = hf_hub_download(hf_repo, loaders.TEXT_TOKENIZER_NAME)
    text_tokenizer = sentencepiece.SentencePieceProcessor(tokenizer_path)
    
    # Load Moshi LM
    logger.info("Loading Moshi LM (this may take a while)...")
    moshi_weight = hf_hub_download(hf_repo, loaders.MOSHI_NAME)
    lm = loaders.get_moshi_lm(moshi_weight, device=device)
    lm.eval()
    
    # Create LMGen
    frame_size = int(mimi.sample_rate / mimi.frame_rate)
    lm_gen = LMGen(
        lm,
        audio_silence_frame_cnt=int(0.5 * mimi.frame_rate),
        sample_rate=mimi.sample_rate,
        device=device,
        frame_rate=mimi.frame_rate,
        save_voice_prompt_embeddings=False,
        use_sampling=True,
        temp=0.8,
        temp_text=0.7,
        top_k=250,
        top_k_text=25,
    )
    
    # Set streaming mode
    mimi.streaming_forever(1)
    other_mimi.streaming_forever(1)
    lm_gen.streaming_forever(1)
    
    # Warmup
    logger.info("Warming up models...")
    warmup()
    
    logger.info("PersonaPlex models loaded successfully!")


def warmup():
    """Run warmup to initialize CUDA graphs."""
    global mimi, other_mimi, lm_gen, frame_size
    
    try:
        for _ in range(4):
            chunk = torch.zeros(1, 1, frame_size, dtype=torch.float32, device=device)
            codes = mimi.encode(chunk)
            _ = other_mimi.encode(chunk)
            # Process steps - if IndexError occurs, we catch it and continue
            for c in range(codes.shape[-1]):
                try:
                    tokens = lm_gen.step(codes[:, :, c : c + 1])
                    if tokens is None:
                        continue
                    _ = mimi.decode(tokens[:, 1:9])
                    _ = other_mimi.decode(tokens[:, 1:9])
                except IndexError as e:
                    logger.warning(f"Index error during warmup at step {c}: {e}")
                    # Skip rest of warmup but continue startup
                    break
        
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        
        logger.info("Warmup completed successfully")
    except Exception as e:
        logger.error(f"Error during warmup: {e}", exc_info=True)
        logger.info("Continuing without full warmup - first requests may be slower")
        # Continue anyway - model may still work


def wrap_with_system_tags(text: str) -> str:
    """Add system tags as the model expects."""
    cleaned = text.strip()
    if cleaned.startswith("<|system|>") and cleaned.endswith("<|/system|>"):
        return cleaned
    return f"<|system|> {cleaned} <|/system|>"


def _init_session_sync(session_id: str, persona_prompt: str, voice_prompt: str = "NATF2.pt") -> MoshiSession:
    """
    Synchronous session initialization (runs in thread executor).
    
    This contains all blocking GPU operations that would otherwise
    block the event loop and prevent WebSocket ping/pong handling.
    
    Uses _init_lock to serialize: the pod has one global model set,
    so concurrent inits would corrupt each other's streaming state.
    """
    global mimi, other_mimi, lm_gen, text_tokenizer
    
    from huggingface_hub import hf_hub_download
    import tarfile
    
    logger.info(f"Waiting for init lock for session {session_id}")
    with _init_lock:
        logger.info(f"Initializing session {session_id}")
        
        # Download voice prompts if needed
        hf_repo = "nvidia/personaplex-7b-v1"
        voices_tgz = hf_hub_download(hf_repo, "voices.tgz")
        voices_tgz = Path(voices_tgz)
        voices_dir = voices_tgz.parent / "voices"
        
        if not voices_dir.exists():
            logger.info("Extracting voice prompts...")
            with tarfile.open(voices_tgz, "r:gz") as tar:
                tar.extractall(path=voices_tgz.parent)
        
        # Ensure voice prompt has .pt extension
        if not voice_prompt.endswith('.pt'):
            voice_prompt = voice_prompt + '.pt'
        
        voice_prompt_path = str(voices_dir / voice_prompt)
        
        # Reset streaming state
        mimi.reset_streaming()
        other_mimi.reset_streaming()
        lm_gen.reset_streaming()
        
        # Load voice prompt
        if voice_prompt_path.endswith('.pt'):
            lm_gen.load_voice_prompt_embeddings(voice_prompt_path)
        else:
            lm_gen.load_voice_prompt(voice_prompt_path)
        
        # Set text prompt
        if persona_prompt:
            lm_gen.text_prompt_tokens = text_tokenizer.encode(wrap_with_system_tags(persona_prompt))
        else:
            lm_gen.text_prompt_tokens = None
        
        # Run system prompts phase (heavy GPU operation)
        lm_gen.step_system_prompts(mimi)
        mimi.reset_streaming()
        
        # Create and store session
        session = MoshiSession(session_id, persona_prompt, voice_prompt)
        sessions[session_id] = session
        
        logger.info(f"Session {session_id} initialized")
        return session


async def init_session(session_id: str, persona_prompt: str, voice_prompt: str = "NATF2.pt") -> MoshiSession:
    """
    Initialize a new conversation session.
    
    Runs the blocking GPU operations in a thread executor so the
    event loop stays responsive for WebSocket ping/pong handling.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,  # default thread pool
        _init_session_sync,
        session_id,
        persona_prompt,
        voice_prompt
    )


def verify_token(authorization: Optional[str] = Header(None)) -> bool:
    """Verify the API token."""
    if not API_TOKEN:
        return True  # No token configured, allow all
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    # Expected format: "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    if parts[1] != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return True


# Lifespan for model loading
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    load_models()
    yield
    # Cleanup on shutdown
    logger.info("Shutting down, cleaning up sessions...")
    sessions.clear()


# Create FastAPI app
app = FastAPI(
    title="PersonaPlex Pod Server",
    description="Real-time speech-to-speech AI server",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - allows admin UI to fetch voices and voice samples directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for voice preview
    allow_credentials=False,
    allow_methods=["GET"],  # Only GET needed for /voices and /voice-sample
    allow_headers=["*"],
)


# Request/Response models
class SessionCreateRequest(BaseModel):
    session_id: str
    persona_prompt: str
    voice_prompt: str = "NATF2.pt"


class SessionResponse(BaseModel):
    status: str
    session_id: str
    message: str = ""


class TranscriptResponse(BaseModel):
    session_id: str
    user: str
    assistant: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    active_sessions: int
    device: str


class VoicesResponse(BaseModel):
    voices: list


# REST Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse(
        status="healthy" if mimi is not None else "loading",
        model_loaded=mimi is not None,
        active_sessions=len(sessions),
        device=device
    )


@app.get("/voices", response_model=VoicesResponse)
async def list_voices():
    """
    List available PersonaPlex voice presets.
    
    Returns voice IDs (without .pt extension) that can be used
    in session creation as voice_prompt parameter.
    
    This endpoint does not require authentication so the admin UI
    can easily fetch the available voices.
    """
    from huggingface_hub import hf_hub_download
    import tarfile
    
    hf_repo = "nvidia/personaplex-7b-v1"
    
    try:
        # Ensure voices are downloaded and extracted
        voices_tgz = hf_hub_download(hf_repo, "voices.tgz")
        voices_dir = Path(voices_tgz).parent / "voices"
        
        if not voices_dir.exists():
            logger.info("Extracting voice prompts for /voices endpoint...")
            with tarfile.open(voices_tgz, "r:gz") as tar:
                tar.extractall(path=Path(voices_tgz).parent)
        
        # List .pt files and return without extension
        voices = sorted([f.stem for f in voices_dir.glob("*.pt")])
        
        if not voices:
            # Fallback if directory is empty
            voices = ["NATF0", "NATF1", "NATF2", "NATF3", "NATF4", "NATF5"]
        
        logger.info(f"Available voices: {voices}")
        return VoicesResponse(voices=voices)
        
    except Exception as e:
        logger.error(f"Error listing voices: {e}")
        # Return hardcoded fallback
        return VoicesResponse(
            voices=["NATF0", "NATF1", "NATF2", "NATF3", "NATF4", "NATF5"]
        )


class VoiceSampleResponse(BaseModel):
    voice_id: str
    audio_base64: str
    sample_rate: int = 24000
    duration_ms: int


@app.get("/voice-sample/{voice_id}")
async def get_voice_sample(voice_id: str):
    """
    Generate a voice sample for preview.
    
    Creates a short audio sample using the selected voice.
    Uses a simple prompt to trigger the model to speak.
    
    This endpoint does not require authentication for admin UI access.
    """
    global mimi, other_mimi, lm_gen, text_tokenizer, frame_size, _process_audio_lock
    
    if mimi is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    
    from moshi.models.lm import _iterate_audio as lm_iterate_audio
    from moshi.models.lm import encode_from_sphn as lm_encode_from_sphn
    from huggingface_hub import hf_hub_download
    import tarfile
    
    # Validate voice_id
    hf_repo = "nvidia/personaplex-7b-v1"
    voices_tgz = hf_hub_download(hf_repo, "voices.tgz")
    voices_dir = Path(voices_tgz).parent / "voices"
    
    if not voices_dir.exists():
        with tarfile.open(voices_tgz, "r:gz") as tar:
            tar.extractall(path=Path(voices_tgz).parent)
    
    voice_file = voices_dir / f"{voice_id}.pt"
    if not voice_file.exists():
        raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")
    
    try:
        async with _process_audio_lock:
            # Load voice prompt
            voice_prompt = torch.load(voice_file, map_location=device, weights_only=True)
            lm_gen.voice_prompt_tokens = voice_prompt
            
            # Set a simple greeting prompt
            sample_prompt = "Je bent een vriendelijke AI assistent. Zeg: Hallo, dit is een voorbeeld van mijn stem."
            lm_gen.text_prompt_tokens = text_tokenizer.encode(wrap_with_system_tags(sample_prompt))
            lm_gen.step_system_prompts(mimi)
            mimi.reset_streaming()
            
            # Generate audio by feeding short silence and capturing response
            # Create 0.5 seconds of near-silence (very quiet audio triggers the model to speak)
            silence_duration = 0.5  # seconds
            sample_rate = 24000
            silence_samples = int(silence_duration * sample_rate)
            
            # Very quiet noise (not complete silence, to trigger response)
            # Keep on CPU: _iterate_audio uses numpy ops internally;
            # encode_from_sphn handles the CPU→GPU transfer.
            silence_audio = torch.randn(1, silence_samples) * 0.001
            
            generated_frames = []
            
            # Process through model
            for user_encoded in lm_encode_from_sphn(
                mimi,
                lm_iterate_audio(silence_audio, sample_interval_size=frame_size, pad=True),
                max_batch=1,
            ):
                steps = user_encoded.shape[-1]
                for c in range(steps):
                    try:
                        step_in = user_encoded[:, :, c : c + 1]
                        tokens = lm_gen.step(step_in)
                        
                        if tokens is None:
                            continue
                        
                        # Decode audio
                        pcm = mimi.decode(tokens[:, 1:9])
                        _ = other_mimi.decode(tokens[:, 1:9])
                        pcm_np = pcm.detach().cpu().numpy()[0, 0]
                        generated_frames.append(pcm_np)
                    except IndexError as e:
                        logger.error(f"Index error in voice sample at step {c}/{steps}: {e}")
                        break
                    except Exception as e:
                        logger.error(f"Error in voice sample at step {c}: {e}")
                        continue
            
            if len(generated_frames) == 0:
                raise HTTPException(status_code=500, detail="No audio generated")
            
            # Concatenate and convert to bytes
            output_pcm = np.concatenate(generated_frames, axis=-1)
            
            # Limit to max 3 seconds
            max_samples = sample_rate * 3
            if len(output_pcm) > max_samples:
                output_pcm = output_pcm[:max_samples]
            
            # Convert to int16 bytes
            output_bytes = (output_pcm * 32768).astype(np.int16).tobytes()
            
            # Encode as base64
            audio_base64 = base64.b64encode(output_bytes).decode('utf-8')
            
            duration_ms = int(len(output_pcm) / sample_rate * 1000)
            
            logger.info(f"Generated voice sample for {voice_id}: {duration_ms}ms")
            
            return VoiceSampleResponse(
                voice_id=voice_id,
                audio_base64=audio_base64,
                sample_rate=sample_rate,
                duration_ms=duration_ms
            )
            
    except Exception as e:
        logger.error(f"Error generating voice sample: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate sample: {str(e)}")


@app.post("/session", response_model=SessionResponse, dependencies=[Depends(verify_token)])
async def create_session(request: SessionCreateRequest):
    """Create a new conversation session."""
    if request.session_id in sessions:
        return SessionResponse(
            status="exists",
            session_id=request.session_id,
            message="Session already exists"
        )
    
    try:
        await init_session(
            request.session_id,
            request.persona_prompt,
            request.voice_prompt
        )
        return SessionResponse(
            status="created",
            session_id=request.session_id,
            message="Session initialized successfully"
        )
    except Exception as e:
        logger.error(f"Failed to create session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/session/{session_id}", response_model=TranscriptResponse, dependencies=[Depends(verify_token)])
async def end_session(session_id: str):
    """End a session and return the transcript."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    transcript = TranscriptResponse(
        session_id=session_id,
        user=" ".join(session.transcript_user),
        assistant=" ".join(session.transcript_assistant)
    )
    
    # Cleanup
    session.is_active = False
    del sessions[session_id]
    
    logger.info(f"Session {session_id} ended")
    return transcript


@app.get("/session/{session_id}", dependencies=[Depends(verify_token)])
async def get_session_status(session_id: str):
    """Get session status."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    return {
        "session_id": session_id,
        "is_active": session.is_active,
        "transcript_length": len(session.transcript_assistant)
    }


# WebSocket Endpoint
@app.websocket("/stream/{session_id}")
async def audio_stream(websocket: WebSocket, session_id: str):
    """
    Bidirectional audio streaming endpoint with turn-based context injection.
    
    Protocol:
    - Client sends JSON: {"action": "start_turn", "turn_id": N} before each audio segment
    - Client sends raw PCM audio bytes (24kHz, 16-bit, mono) - one segment per turn
    - Server responds with JSON: {"event": "transcript_final", "turn_id": N, "assistant": "..."}
    - Server then sends raw PCM audio bytes
    - Client can send: {"action": "update_context", "turn_id": N, "facts": "...", "instructions": "..."}
    """
    await websocket.accept()
    
    # Check authorization from query params or first message
    token = websocket.query_params.get("token", "")
    if API_TOKEN and token != API_TOKEN:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    logger.info(f"WebSocket connected for session {session_id}")
    
    session = sessions.get(session_id)
    
    try:
        while True:
            # Receive data (can be bytes or text)
            message = await websocket.receive()
            
            if "bytes" in message:
                # Audio data (one segment per turn)
                audio_bytes = message["bytes"]
                
                if not session:
                    await websocket.send_json({
                        "error": "Session not initialized",
                        "hint": "Send JSON with persona_prompt first or call POST /session"
                    })
                    continue
                
                # Process audio (step_system_prompts + reset happens here, once per segment)
                try:
                    response_audio, assistant_text = await session.process_audio(audio_bytes)
                    
                    # Always send transcript_final JSON first (with turn_id)
                    await websocket.send_json({
                        "event": "transcript_final",
                        "turn_id": session.current_turn,
                        "user": "",  # Pod has no ASR; backend provides via STT
                        "assistant": assistant_text or ""
                    })
                    
                    # Then send audio bytes
                    if response_audio:
                        await websocket.send_bytes(response_audio)
                        
                except Exception as e:
                    logger.error(f"Error processing audio: {e}")
                    await websocket.send_json({"error": str(e), "turn_id": session.current_turn if session else 0})
            
            elif "text" in message:
                # JSON command
                try:
                    data = json.loads(message["text"])
                    
                    if "persona_prompt" in data:
                        # Initialize session via WebSocket
                        persona_prompt = data["persona_prompt"]
                        voice_prompt = data.get("voice_prompt", "NATF2.pt")
                        
                        # Send immediate ping so connection has traffic from the start (no idle gap)
                        await websocket.send_json({
                            "status": "initializing",
                            "session_id": session_id
                        })
                        
                        # Run init in background while sending keepalive pings
                        # This prevents Render's proxy from closing the idle WebSocket
                        loop = asyncio.get_event_loop()
                        init_task = loop.run_in_executor(
                            None, _init_session_sync, session_id, persona_prompt, voice_prompt
                        )
                        
                        while True:
                            try:
                                session = await asyncio.wait_for(
                                    asyncio.shield(init_task), timeout=10.0
                                )
                                # Init completed
                                break
                            except asyncio.TimeoutError:
                                # Still initializing - send progress ping to keep connection alive
                                await websocket.send_json({
                                    "status": "initializing",
                                    "session_id": session_id
                                })
                                logger.debug(f"Session {session_id} still initializing, sent keepalive")
                        
                        await websocket.send_json({
                            "status": "initialized",
                            "session_id": session_id
                        })
                    
                    elif data.get("action") == "start_turn":
                        # Start a new turn (must be called before sending audio segment)
                        turn_id = data.get("turn_id", 0)
                        if session:
                            session.start_turn(turn_id)
                            await websocket.send_json({
                                "status": "turn_started",
                                "turn_id": turn_id
                            })
                        else:
                            await websocket.send_json({
                                "error": "Session not initialized",
                                "turn_id": turn_id
                            })
                    
                    elif data.get("action") == "update_context":
                        # Store context for a turn (does NOT reset streaming)
                        turn_id = data.get("turn_id", 0)
                        facts = data.get("facts", "")
                        instructions = data.get("instructions", "")
                        if session:
                            session.update_context(turn_id, facts, instructions)
                            await websocket.send_json({
                                "status": "context_updated",
                                "turn_id": turn_id
                            })
                        else:
                            await websocket.send_json({
                                "error": "Session not initialized",
                                "turn_id": turn_id
                            })
                    
                    elif data.get("action") == "ping":
                        await websocket.send_json({"action": "pong"})
                    
                    elif data.get("action") == "end":
                        # End session
                        if session:
                            transcript = {
                                "user": " ".join(session.transcript_user),
                                "assistant": " ".join(session.transcript_assistant)
                            }
                            session.is_active = False
                            if session_id in sessions:
                                del sessions[session_id]
                            await websocket.send_json({
                                "status": "ended",
                                "transcript": transcript
                            })
                        break
                    
                except json.JSONDecodeError:
                    await websocket.send_json({"error": "Invalid JSON"})
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}", exc_info=True)
    finally:
        # Keep session alive even after WebSocket disconnect
        # (allows reconnection)
        pass


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "pod_server:app",
        host=host,
        port=port,
        log_level="info",
        reload=False  # Don't reload in production
    )
