"""
klantenservice.ai - Voice WebSocket Handler
Handles Twilio Media Streams and routes audio through PersonaPlex-7B

Architecture (Orchestrator Integration):
1. Twilio sends audio chunks (20ms each)
2. We buffer chunks into "utterance segments" (2-3 seconds)
3. Each segment gets a turn_id
4. When segment is ready:
   a. Send start_turn(turn_id) to pod
   b. Send audio segment to pod -> receive transcript_final + audio
   c. Run STT (Whisper) on user audio to get user_transcript
   d. Run orchestrator (LLM + tools) -> get facts + instructions
   e. Send update_context(turn_id, facts, instructions) to pod
   f. Send audio response to Twilio

Goal: PersonaPlex NEVER hallucinates. Prices, availability, policies
come ONLY from orchestrator tool results.

Reference: https://www.twilio.com/docs/voice/media-streams
"""
import asyncio
import base64
import io
import json
import logging
import time
from datetime import datetime
from typing import Optional, List, Tuple

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.models.company import Company
from app.models.call_log import CallLog, CallStatus, CallOutcome
from app.models.phone_number import PhoneNumber
from app.models.website_knowledge import WebsiteKnowledge
from app.models.training import TrainingRule, ExampleAnswer
from app.models.latency_log import LatencyLog
from app.models.usage_log import UsageLog
from app.models.global_config import GlobalConfig
from app.services.personaplex_service import personaplex_service
from app.services.question_detector import analyze_call_transcript
from app.services.audio_utils import AudioConverter

settings = get_settings()
logger = logging.getLogger(__name__)

# Configuration for audio buffering
SEGMENT_DURATION_SECONDS = 2.5  # Buffer audio for this long before processing
SILENCE_THRESHOLD_SECONDS = 0.8  # Detect end of utterance after this silence
MIN_SEGMENT_DURATION_SECONDS = 0.5  # Minimum segment to process


class VoiceCallHandler:
    """
    Handles a single voice call through Twilio Media Streams.
    
    This class manages:
    - The WebSocket connection with Twilio
    - Audio conversion (mulaw <-> PCM)
    - Audio buffering into utterance segments
    - Turn-based communication with PersonaPlex
    - STT + Orchestrator integration for context injection
    - Call logging and transcription
    """
    
    def __init__(
        self,
        websocket: WebSocket,
        db: Session,
        call_sid: str,
        stream_sid: str
    ):
        self.websocket = websocket
        self.db = db
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        
        # Will be set after initialization
        self.phone_number: Optional[PhoneNumber] = None
        self.ai_worker: Optional[AIWorker] = None
        self.company: Optional[Company] = None
        self.call_log: Optional[CallLog] = None
        self.session_id: Optional[str] = None
        
        # Audio converter
        self.audio_converter = AudioConverter()
        
        # Queue for sending audio back to Twilio
        self.send_queue: asyncio.Queue[bytes] = asyncio.Queue()
        
        # Running flag
        self.is_running = False
        
        # Turn-based processing
        self._turn_id: int = 0
        self._audio_buffer: List[bytes] = []
        self._buffer_start_time: Optional[float] = None
        self._last_audio_time: Optional[float] = None
        
        # Conversation history for orchestrator
        self._user_transcripts: List[str] = []
        self._assistant_transcripts: List[str] = []
        
        # Calendar ID (if known from availability check)
        self._calendar_id: Optional[str] = None
        
        # Auto-respond setting (from GlobalConfig, set in initialize)
        self._auto_respond: bool = True
    
    async def initialize_from_phone_number(self, to_number: str, from_number: str):
        """
        Initialize the call handler with phone number lookup.
        
        Args:
            to_number: The Twilio number that received the call
            from_number: The caller's phone number
        """
        # Find the phone number in the database
        self.phone_number = self.db.query(PhoneNumber).filter(
            PhoneNumber.number == to_number,
            PhoneNumber.is_active == True
        ).first()
        
        if not self.phone_number:
            logger.error(f"Phone number {to_number} not found in database")
            raise ValueError(f"Unknown phone number: {to_number}")
        
        # Get the assigned AI worker
        self.ai_worker = self.db.query(AIWorker).filter(
            AIWorker.id == self.phone_number.ai_worker_id,
            AIWorker.status != AIWorkerStatus.OFFLINE
        ).first()
        
        if not self.ai_worker:
            logger.error(f"No active AI worker for phone number {to_number}")
            raise ValueError("No AI worker available")
        
        # Get the company
        self.company = self.db.query(Company).filter(
            Company.id == self.ai_worker.company_id
        ).first()
        
        if not self.company:
            logger.error(f"Company not found for AI worker {self.ai_worker.id}")
            raise ValueError("Company not found")
        
        # Look up existing call log (created by webhook) or create new one
        self.call_log = self.db.query(CallLog).filter(
            CallLog.twilio_call_sid == self.call_sid
        ).first()
        
        if not self.call_log:
            # Create call log if webhook didn't create one
            self.call_log = CallLog(
                company_id=self.company.id,
                ai_worker_id=self.ai_worker.id,
                phone_number_id=self.phone_number.id,
                caller_number=from_number,
                called_number=to_number,
                twilio_call_sid=self.call_sid,
                status=CallStatus.IN_PROGRESS,
            )
            self.db.add(self.call_log)
            self.db.commit()
            self.db.refresh(self.call_log)
        else:
            logger.info(f"Found existing call log for {self.call_sid}")
        
        self.session_id = str(self.call_log.id)
        
        # Get auto-respond setting from GlobalConfig (platform-wide)
        auto_respond_config = self.db.query(GlobalConfig).filter(
            GlobalConfig.key == "voice_auto_respond"
        ).first()
        self._auto_respond = auto_respond_config.value if auto_respond_config else True
        
        logger.info(
            f"Call initialized: {from_number} -> {to_number}, "
            f"AI Worker: {self.ai_worker.name}, Company: {self.company.name}, "
            f"Auto-respond: {self._auto_respond}"
        )
    
    async def get_knowledge_context(self) -> Optional[str]:
        """
        Get relevant knowledge context from website scraping.
        """
        from app.models.website_knowledge import KnowledgeChunk
        
        # Get active website knowledge for this company
        knowledge_sources = self.db.query(WebsiteKnowledge).filter(
            WebsiteKnowledge.company_id == self.company.id,
            WebsiteKnowledge.is_active == True,
            WebsiteKnowledge.status == "completed"
        ).all()
        
        if not knowledge_sources:
            return None
        
        # Combine knowledge content from chunks
        context_parts = []
        for source in knowledge_sources:
            # Get chunks for this website (limit to most relevant)
            chunks = self.db.query(KnowledgeChunk).filter(
                KnowledgeChunk.website_id == source.id
            ).limit(10).all()
            
            for chunk in chunks:
                if chunk.content:
                    context_parts.append(chunk.content[:500])  # Limit per chunk
        
        if context_parts:
            return "\n\n---\n\n".join(context_parts)[:8000]  # Total limit
        
        return None
    
    def get_training_rules(self) -> list:
        """
        Get enabled training rules for this company.
        """
        rules = self.db.query(TrainingRule).filter(
            TrainingRule.company_id == self.company.id,
            TrainingRule.is_enabled == True
        ).order_by(TrainingRule.display_order).all()
        
        return [
            {
                "key": rule.rule_key,
                "name": rule.rule_name,
                "description": rule.rule_description
            }
            for rule in rules
        ]
    
    def get_example_answers(self) -> list:
        """
        Get active example Q&A pairs for this company.
        """
        examples = self.db.query(ExampleAnswer).filter(
            ExampleAnswer.company_id == self.company.id,
            ExampleAnswer.is_active == True,
            ExampleAnswer.is_verified == True
        ).all()
        
        return [
            {
                "question": ex.question,
                "answer": ex.answer,
                "category": ex.category
            }
            for ex in examples
        ]
    
    async def _send_twilio_silence(self, duration_seconds: float = 1.0):
        """Send silence audio to Twilio to keep the connection alive."""
        # Generate mulaw silence (8kHz, 1 byte per sample)
        num_samples = int(8000 * duration_seconds)
        # mulaw silence byte is 0xFF (127 in mulaw = ~0 in linear)
        silence_mulaw = b'\xff' * num_samples
        
        media_message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {
                "payload": base64.b64encode(silence_mulaw).decode("utf-8")
            }
        }
        await self.websocket.send_text(json.dumps(media_message))
    
    async def _keepalive_loop(self, stop_event: asyncio.Event):
        """Send silence to Twilio every 5 seconds until stop_event is set."""
        while not stop_event.is_set():
            try:
                await self._send_twilio_silence(0.5)
                await asyncio.sleep(5)
            except Exception:
                break
    
    async def start(self):
        """
        Start handling the voice call.
        Uses pre-warmed PersonaPlex session if available for instant response.
        Falls back to creating a new session with Twilio keepalive.
        """
        self.is_running = True
        
        # Update AI worker status
        self.ai_worker.status = AIWorkerStatus.BUSY
        self.db.commit()
        
        # Try to claim a pre-warmed session first (instant path)
        worker_id = str(self.ai_worker.id)
        warm_session = await personaplex_service.claim_warm_session(worker_id, self.session_id)
        
        if warm_session:
            logger.info(f"Using pre-warmed session for worker {self.ai_worker.name}")
        else:
            logger.info(f"No pre-warmed session available, initializing fresh (with keepalive)")
            
            # Start sending silence to Twilio to keep the connection alive
            # while PersonaPlex initializes (30-60 seconds)
            stop_keepalive = asyncio.Event()
            keepalive_task = asyncio.create_task(self._keepalive_loop(stop_keepalive))
            
            try:
                # Get knowledge context for RAG
                knowledge_context = await self.get_knowledge_context()
                
                # Get training rules and example answers
                training_rules = self.get_training_rules()
                example_answers = self.get_example_answers()
                
                # Get system-wide prompts (from /admin)
                system_prompts = personaplex_service.get_system_prompts(self.db)
                
                # Create PersonaPlex session (establishes WebSocket to pod)
                await personaplex_service.create_session(
                    session_id=self.session_id,
                    worker=self.ai_worker,
                    company=self.company,
                    db=self.db,
                    voice_prompt_path=None,
                    knowledge_context=knowledge_context,
                    training_rules=training_rules,
                    example_answers=example_answers,
                    system_prompts=system_prompts
                )
            finally:
                # Stop keepalive once session is ready
                stop_keepalive.set()
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except asyncio.CancelledError:
                    pass
        
        # Trigger initial greeting from PersonaPlex
        # Send a short silence segment to trigger PersonaPlex to generate initial greeting
        try:
            await personaplex_service.start_turn(self.session_id, turn_id=0)
            # Create a short silence audio segment (0.5 seconds of silence at 24kHz, 16-bit mono)
            silence_duration_ms = 500
            silence_samples = int(24000 * silence_duration_ms / 1000)
            silence_audio = b'\x00\x00' * silence_samples  # 16-bit PCM silence
            
            initial_audio, initial_text, _ = await personaplex_service.process_audio_segment(
                self.session_id,
                silence_audio,
                turn_id=0
            )
            
            # Queue initial greeting audio if received
            if initial_audio:
                chunk_size = 4800  # 100ms at 24kHz
                for i in range(0, len(initial_audio), chunk_size):
                    chunk = initial_audio[i:i+chunk_size]
                    await self.send_queue.put(chunk)
                logger.info(f"Initial greeting generated: {initial_text[:50] if initial_text else 'no transcript'}")
            else:
                logger.warning("No initial greeting audio received from PersonaPlex")
        except Exception as e:
            logger.error(f"Failed to generate initial greeting: {e}", exc_info=True)
            # Continue anyway - call will still work when user speaks
        
        # NOTE: Do NOT pre-warm here. The pod has one global model set, so
        # initializing a new session while this call is active would corrupt
        # the model state (reset_streaming mid-inference). Re-warm happens
        # in cleanup() after the call ends and the session is released.
        
        # Start tasks for receiving and sending audio
        receive_task = asyncio.create_task(self._receive_audio_loop())
        send_task = asyncio.create_task(self._send_audio_loop())
        
        try:
            await asyncio.gather(receive_task, send_task)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for call {self.call_sid}")
        except Exception as e:
            logger.error(f"Error in voice call handler: {e}")
        finally:
            await self.cleanup()
    
    async def _receive_audio_loop(self):
        """
        Receive audio from Twilio and buffer into utterance segments.
        
        When a segment is ready (based on duration or silence detection),
        process it through PersonaPlex + STT + Orchestrator.
        """
        while self.is_running:
            try:
                # Receive message from Twilio
                message = await self.websocket.receive_text()
                data = json.loads(message)
                
                event_type = data.get("event")
                
                if event_type == "media":
                    # Audio data from caller
                    payload = data.get("media", {}).get("payload", "")
                    mulaw_audio = base64.b64decode(payload)
                    
                    # Convert mulaw to PCM for PersonaPlex
                    pcm_audio = self.audio_converter.mulaw_to_pcm(mulaw_audio)
                    
                    # Buffer the audio
                    now = time.time()
                    self._audio_buffer.append(pcm_audio)
                    self._last_audio_time = now
                    
                    if self._buffer_start_time is None:
                        self._buffer_start_time = now
                    
                    # Check if segment is ready
                    segment_ready = False
                    elapsed = now - self._buffer_start_time
                    
                    if self._auto_respond:
                        # VAD mode: automatically detect when to process based on duration
                        # Ready if: duration exceeded (voice activity detection)
                        if elapsed >= SEGMENT_DURATION_SECONDS:
                            segment_ready = True
                    # When auto_respond is False, we only process on:
                    # - "stop" event (call ending)
                    # - "mark" event with specific trigger (manual mode)
                    
                    # Process segment if ready
                    if segment_ready and elapsed >= MIN_SEGMENT_DURATION_SECONDS:
                        await self._process_segment()
                
                elif event_type == "stop":
                    # Process any remaining buffer before stopping
                    if self._audio_buffer and self._buffer_start_time:
                        elapsed = time.time() - self._buffer_start_time
                        if elapsed >= MIN_SEGMENT_DURATION_SECONDS:
                            await self._process_segment()
                    
                    logger.info(f"Received stop event for call {self.call_sid}")
                    self.is_running = False
                    break
                
                elif event_type == "mark":
                    # Playback marker - can be used for interrupt handling or manual trigger
                    mark_name = data.get("mark", {}).get("name", "")
                    logger.debug(f"Mark received: {mark_name}")
                    
                    # In manual mode (auto_respond=False), a specific mark can trigger processing
                    if not self._auto_respond and mark_name == "process_segment":
                        if self._audio_buffer and self._buffer_start_time:
                            elapsed = time.time() - self._buffer_start_time
                            if elapsed >= MIN_SEGMENT_DURATION_SECONDS:
                                await self._process_segment()
                
            except WebSocketDisconnect:
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Error receiving audio: {e}")
                continue
    
    async def _process_segment(self):
        """
        Process a buffered audio segment through the full pipeline:
        1. Increment turn_id
        2. Send start_turn to pod
        3. Send audio segment to pod -> get transcript_final + response audio
        4. Run STT on user audio -> get user_transcript
        5. Run orchestrator (LLM + tools) -> get facts + instructions
        6. Send update_context to pod
        7. Queue response audio for Twilio
        8. Log latencies
        """
        if not self._audio_buffer:
            return
        
        # Combine buffered chunks into one segment
        segment = b"".join(self._audio_buffer)
        self._audio_buffer = []
        self._buffer_start_time = None
        
        # Increment turn_id
        self._turn_id += 1
        turn_id = self._turn_id
        
        logger.info(f"Processing segment for turn {turn_id} ({len(segment)} bytes)")
        
        # Track latencies
        total_start = time.time()
        stt_latency_ms = 0
        orchestrator_latency_ms = 0
        pod_latency_ms = 0
        
        try:
            # 1. Start turn on pod
            await personaplex_service.start_turn(self.session_id, turn_id)
            
            # 2. Send segment to pod and get response (timed)
            pod_start = time.time()
            response_audio, assistant_text, recv_turn_id = await personaplex_service.process_audio_segment(
                self.session_id,
                segment,
                turn_id
            )
            pod_latency_ms = int((time.time() - pod_start) * 1000)
            
            # Store assistant transcript
            if assistant_text:
                self._assistant_transcripts.append(assistant_text)
            
            # 3. Run STT on user segment to get user_transcript (timed)
            stt_start = time.time()
            user_transcript, stt_seconds = await self._transcribe_audio(segment)
            stt_latency_ms = int((time.time() - stt_start) * 1000)
            
            if user_transcript:
                self._user_transcripts.append(user_transcript)
            
            logger.debug(f"Turn {turn_id} - User: {user_transcript[:50] if user_transcript else '(none)'}...")
            logger.debug(f"Turn {turn_id} - Assistant: {assistant_text[:50] if assistant_text else '(none)'}...")
            
            # 4. Run orchestrator to get context injection (timed)
            orchestrator_start = time.time()
            facts, instructions = await self._run_orchestrator(
                user_transcript or "",
                " ".join(self._assistant_transcripts),
                turn_id
            )
            orchestrator_latency_ms = int((time.time() - orchestrator_start) * 1000)
            
            # 5. Send context update to pod (for next turn)
            if facts or instructions:
                await personaplex_service.update_context(
                    self.session_id,
                    turn_id,
                    facts,
                    instructions
                )
                logger.debug(f"Turn {turn_id} - Context: facts={facts[:50] if facts else ''}...")
            
            # 6. Queue response audio for Twilio
            if response_audio:
                # Send in chunks for smoother playback
                chunk_size = 4800  # 100ms at 24kHz (will be resampled)
                for i in range(0, len(response_audio), chunk_size):
                    chunk = response_audio[i:i+chunk_size]
                    await self.send_queue.put(chunk)
            
            # 7. Log latencies and STT usage
            total_latency_ms = int((time.time() - total_start) * 1000)
            
            try:
                if self.call_log:
                    # Log latency
                    latency_log = LatencyLog(
                        call_log_id=self.call_log.id,
                        turn_id=turn_id,
                        stt_latency_ms=stt_latency_ms,
                        orchestrator_latency_ms=orchestrator_latency_ms,
                        pod_latency_ms=pod_latency_ms,
                        total_latency_ms=total_latency_ms,
                    )
                    self.db.add(latency_log)
                    
                    # Log STT usage
                    if stt_seconds > 0:
                        usage_log = UsageLog(
                            company_id=self.company.id,
                            call_log_id=self.call_log.id,
                            turn_id=turn_id,
                            stt_seconds=stt_seconds,
                            stt_model="whisper-1",
                        )
                        usage_log.calculate_costs()
                        self.db.add(usage_log)
                    
                    self.db.commit()
            except Exception as log_err:
                logger.warning(f"Failed to log latency/usage: {log_err}")
            
            logger.info(f"Turn {turn_id} completed: STT={stt_latency_ms}ms, Orch={orchestrator_latency_ms}ms, Pod={pod_latency_ms}ms, Total={total_latency_ms}ms")
                    
        except Exception as e:
            logger.error(f"Error processing segment for turn {turn_id}: {e}", exc_info=True)
    
    async def _transcribe_audio(self, pcm_audio: bytes) -> Tuple[str, float]:
        """
        Transcribe PCM audio using OpenAI Whisper API.
        
        Args:
            pcm_audio: Raw PCM audio bytes (24kHz, 16-bit, mono)
            
        Returns:
            Tuple of (transcribed_text, audio_seconds)
        """
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not configured - STT disabled")
            return "", 0.0
        
        try:
            from openai import OpenAI
            import wave
            
            # Calculate audio duration (24kHz, 16-bit mono = 48000 bytes/second)
            audio_seconds = len(pcm_audio) / 48000
            
            # Convert PCM to WAV format for Whisper
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(24000)  # PersonaPlex uses 24kHz
                wav.writeframes(pcm_audio)
            wav_buffer.seek(0)
            wav_buffer.name = "audio.wav"
            
            # Call Whisper API
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=wav_buffer,
                language="nl",  # Dutch
                response_format="text"
            )
            
            return (transcript.strip() if transcript else ""), audio_seconds
            
        except Exception as e:
            logger.error(f"STT error: {e}")
            return "", 0.0
    
    async def _run_orchestrator(
        self,
        user_transcript: str,
        assistant_transcript_so_far: str,
        turn_id: int
    ) -> Tuple[str, str]:
        """
        Run the orchestrator to get context injection.
        
        Args:
            user_transcript: What the user said this turn
            assistant_transcript_so_far: Full assistant transcript
            turn_id: Current turn ID
            
        Returns:
            Tuple of (facts, instructions)
        """
        if not user_transcript.strip():
            return "", ""
        
        try:
            from app.services.orchestrator import build_context_payload
            import asyncio
            
            # Get caller phone from call log
            customer_phone = self.call_log.caller_number if self.call_log else None
            
            # Run orchestrator in thread pool (it's sync + does LLM calls)
            loop = asyncio.get_event_loop()
            facts, instructions = await loop.run_in_executor(
                None,
                build_context_payload,
                self.db,
                str(self.company.id),
                str(self.call_log.id) if self.call_log else None,
                self._calendar_id,
                user_transcript,
                assistant_transcript_so_far,
                customer_phone,
                turn_id,
            )
            
            return facts, instructions
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            return "", ""
    
    async def _send_audio_loop(self):
        """
        Send audio from PersonaPlex back to Twilio.
        """
        while self.is_running:
            try:
                # Get audio from queue (with timeout)
                try:
                    pcm_audio = await asyncio.wait_for(
                        self.send_queue.get(), 
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Convert PCM to mulaw for Twilio
                mulaw_audio = self.audio_converter.pcm_to_mulaw(pcm_audio)
                
                # Send to Twilio
                media_message = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": base64.b64encode(mulaw_audio).decode("utf-8")
                    }
                }
                
                await self.websocket.send_text(json.dumps(media_message))
                
            except WebSocketDisconnect:
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Error sending audio: {e}")
                continue
    
    async def cleanup(self):
        """
        Cleanup after call ends.
        """
        self.is_running = False
        
        # Get transcript from PersonaPlex and close session
        transcript = await personaplex_service.end_session(self.session_id)
        
        # Update call log
        if self.call_log:
            self.call_log.status = CallStatus.COMPLETED
            self.call_log.outcome = CallOutcome.HANDLED
            self.call_log.ended_at = datetime.utcnow()
            
            # Save transcript entries
            if transcript:
                from app.models.call_log import CallTranscript
                
                # Save user (caller) transcript
                if transcript.get("user"):
                    caller_transcript = CallTranscript(
                        call_log_id=self.call_log.id,
                        speaker="caller",
                        message=transcript["user"]
                    )
                    self.db.add(caller_transcript)
                
                # Save AI (assistant) transcript
                if transcript.get("assistant"):
                    ai_transcript = CallTranscript(
                        call_log_id=self.call_log.id,
                        speaker="ai",
                        message=transcript["assistant"]
                    )
                    self.db.add(ai_transcript)
                
                # Analyze transcript for unanswered questions
                try:
                    detected_questions = analyze_call_transcript(
                        db=self.db,
                        company_id=str(self.company.id),
                        user_transcript=transcript.get("user", ""),
                        assistant_transcript=transcript.get("assistant", "")
                    )
                    if detected_questions:
                        logger.info(
                            f"Detected {len(detected_questions)} unanswered questions "
                            f"in call {self.call_sid}"
                        )
                except Exception as e:
                    logger.error(f"Error analyzing transcript for questions: {e}")
            
            self.db.commit()
        
        # Update AI worker status back to available
        if self.ai_worker:
            self.ai_worker.status = AIWorkerStatus.AVAILABLE
            self.db.commit()
        
        logger.info(f"Call {self.call_sid} cleaned up successfully")
        
        # Now that the call is done and the pod's models are free,
        # pre-warm a new session for the next incoming call.
        asyncio.create_task(personaplex_service.pre_warm_available_workers(self.db))


async def voice_websocket_handler(
    websocket: WebSocket,
    db: Session
):
    """
    Main WebSocket handler for Twilio Media Streams.
    
    This is called when Twilio connects after answering a call.
    The first message contains call metadata (CallSid, phone numbers, etc.)
    """
    await websocket.accept()
    
    logger.info("Twilio Media Stream connected")
    
    # Variables to store call info
    call_sid = None
    stream_sid = None
    to_number = None
    from_number = None
    handler: Optional[VoiceCallHandler] = None
    
    try:
        # First message should be "connected" with metadata
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            event_type = data.get("event")
            
            if event_type == "connected":
                logger.info("Media stream connected, waiting for start...")
                continue
            
            elif event_type == "start":
                # Extract call metadata
                start_data = data.get("start", {})
                call_sid = start_data.get("callSid")
                stream_sid = start_data.get("streamSid")
                
                # Get custom parameters (set in TwiML)
                custom_params = start_data.get("customParameters", {})
                to_number = custom_params.get("to") or start_data.get("to")
                from_number = custom_params.get("from") or start_data.get("from")
                
                logger.info(
                    f"Media stream started - CallSid: {call_sid}, "
                    f"From: {from_number}, To: {to_number}"
                )
                
                # Create and initialize handler
                handler = VoiceCallHandler(
                    websocket=websocket,
                    db=db,
                    call_sid=call_sid,
                    stream_sid=stream_sid
                )
                
                await handler.initialize_from_phone_number(to_number, from_number)
                
                # Start processing (this will block until call ends)
                await handler.start()
                break
            
            elif event_type == "stop":
                logger.info("Stream stopped before starting")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"Error in voice WebSocket handler: {e}")
    finally:
        if handler:
            await handler.cleanup()
