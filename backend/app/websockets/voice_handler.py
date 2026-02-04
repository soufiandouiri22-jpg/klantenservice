"""
klantenservice.ai - Voice WebSocket Handler
Handles Twilio Media Streams and routes audio through PersonaPlex-7B

Twilio Media Streams:
- Connect via WebSocket when a call is answered
- Send audio as base64-encoded mulaw (8kHz, mono)
- Receive audio as base64-encoded mulaw to play back

The PersonaPlex service now uses a persistent WebSocket connection to a
dedicated GPU pod, eliminating the need for audio buffering workarounds.

Reference: https://www.twilio.com/docs/voice/media-streams
"""
import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.models.company import Company
from app.models.call_log import CallLog, CallStatus, CallOutcome
from app.models.phone_number import PhoneNumber
from app.models.website_knowledge import WebsiteKnowledge
from app.models.training import TrainingRule, ExampleAnswer
from app.services.personaplex_service import personaplex_service
from app.services.question_detector import analyze_call_transcript
from app.services.audio_utils import AudioConverter

logger = logging.getLogger(__name__)


class VoiceCallHandler:
    """
    Handles a single voice call through Twilio Media Streams.
    
    This class manages:
    - The WebSocket connection with Twilio
    - Audio conversion (mulaw <-> PCM)
    - Communication with PersonaPlex via WebSocket
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
        
        logger.info(
            f"Call initialized: {from_number} -> {to_number}, "
            f"AI Worker: {self.ai_worker.name}, Company: {self.company.name}"
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
    
    async def start(self):
        """
        Start handling the voice call.
        """
        self.is_running = True
        
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
            company_name=self.company.name,
            voice_prompt_path=None,  # Voice cloning not yet implemented
            knowledge_context=knowledge_context,
            training_rules=training_rules,
            example_answers=example_answers,
            system_prompts=system_prompts
        )
        
        # Update AI worker status
        self.ai_worker.status = AIWorkerStatus.BUSY
        self.db.commit()
        
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
        Receive audio from Twilio and stream to PersonaPlex.
        
        With the dedicated pod and WebSocket connection, we can stream
        audio directly without buffering.
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
                    
                    # Stream directly to PersonaPlex (no buffering needed)
                    # The WebSocket connection handles the streaming efficiently
                    async for response_audio in personaplex_service.process_audio(
                        self.session_id, 
                        pcm_audio
                    ):
                        await self.send_queue.put(response_audio)
                
                elif event_type == "stop":
                    logger.info(f"Received stop event for call {self.call_sid}")
                    self.is_running = False
                    break
                
                elif event_type == "mark":
                    # Playback marker - can be used for interrupt handling
                    mark_name = data.get("mark", {}).get("name", "")
                    logger.debug(f"Mark received: {mark_name}")
                
            except WebSocketDisconnect:
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Error receiving audio: {e}")
                continue
    
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
