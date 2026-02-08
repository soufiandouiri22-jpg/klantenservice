"""
klantenservice.ai - Voice WebSocket Handler (OpenAI Realtime API)

Bridges Twilio Media Streams with OpenAI Realtime API for AI conversations.

Architecture:
1. Twilio sends mulaw audio (g711_ulaw, 8kHz)
2. We forward it directly to OpenAI Realtime API (same format — no conversion!)
3. OpenAI returns audio + handles STT, LLM, TTS, and function calling
4. We forward audio back to Twilio and handle function calls via call_tools.py

Key features:
- Full-duplex: AI listens while talking
- Barge-in: AI stops when caller speaks
- No audio conversion needed (Twilio and OpenAI both use g711_ulaw)
- No warm pool / GPU pod required
- Function calling for availability, booking, knowledge, prices, notes
- Instant response — no initialization delay

Reference: https://www.twilio.com/docs/voice/media-streams
"""
import asyncio
import base64
import json
import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_worker import AIWorker, AIWorkerStatus
from app.models.company import Company
from app.models.call_log import CallLog, CallStatus, CallOutcome
from app.models.phone_number import PhoneNumber
from app.models.website_knowledge import WebsiteKnowledge
from app.models.training import TrainingRule, ExampleAnswer
from app.models.global_config import GlobalConfig
from app.services.openai_realtime_service import (
    OpenAIRealtimeSession,
    build_realtime_tools,
    build_system_instructions,
    get_system_prompts,
)
from app.services.orchestrator import _run_tool
from app.services.question_detector import analyze_call_transcript

settings = get_settings()
logger = logging.getLogger(__name__)


class RealtimeCallHandler:
    """
    Handles a single voice call by bridging Twilio <-> OpenAI Realtime API.

    The handler:
    1. Looks up the AI worker and company from the phone number
    2. Builds system instructions with persona, knowledge, rules
    3. Opens an OpenAI Realtime session with tools
    4. Runs two parallel loops:
       a) twilio_to_openai: forward caller audio to OpenAI
       b) openai_to_twilio: forward AI audio to Twilio + handle function calls
    5. Saves transcripts and call metadata on cleanup
    """

    def __init__(
        self,
        websocket: WebSocket,
        db: Session,
        call_sid: str,
        stream_sid: str,
    ):
        self.websocket = websocket
        self.db = db
        self.call_sid = call_sid
        self.stream_sid = stream_sid

        # Will be populated in initialize_from_phone_number
        self.phone_number: Optional[PhoneNumber] = None
        self.ai_worker: Optional[AIWorker] = None
        self.company: Optional[Company] = None
        self.call_log: Optional[CallLog] = None
        self.session_id: Optional[str] = None

        # OpenAI Realtime session
        self.openai_session: Optional[OpenAIRealtimeSession] = None

        # State
        self.is_running = False

        # Transcript collection
        self._user_transcript_parts: list[str] = []
        self._ai_transcript_parts: list[str] = []

        # Metrics
        self._inbound_media_frames = 0
        self._outbound_media_frames = 0
        self._function_calls_count = 0
        self._openai_errors = 0

    async def initialize_from_phone_number(self, to_number: str, from_number: str):
        """
        Look up the phone number, AI worker, and company.
        Create or find the call log.
        """
        # Find the phone number in the database
        self.phone_number = self.db.query(PhoneNumber).filter(
            PhoneNumber.number == to_number,
            PhoneNumber.is_active == True,
        ).first()

        if not self.phone_number:
            logger.error(f"Phone number {to_number} not found in database")
            raise ValueError(f"Unknown phone number: {to_number}")

        # Get the assigned AI worker
        self.ai_worker = self.db.query(AIWorker).filter(
            AIWorker.id == self.phone_number.ai_worker_id,
            AIWorker.status != AIWorkerStatus.OFFLINE,
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

        # Check kill switch
        if self.company.is_kill_switched:
            logger.warning(
                f"Call rejected in WS handler: kill switch active for {self.company.name}"
            )
            raise ValueError("Company is kill-switched")

        # Look up existing call log (created by webhook) or create new one
        self.call_log = self.db.query(CallLog).filter(
            CallLog.twilio_call_sid == self.call_sid
        ).first()

        if not self.call_log:
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

    async def _get_knowledge_context(self) -> Optional[str]:
        """Get relevant knowledge context from the website linked to this AI worker."""
        from app.models.website_knowledge import KnowledgeChunk

        # Only fetch website knowledge linked to this specific AI worker (strict 1:1)
        knowledge_sources = self.db.query(WebsiteKnowledge).filter(
            WebsiteKnowledge.ai_worker_id == self.ai_worker.id,
            WebsiteKnowledge.is_active == True,
            WebsiteKnowledge.status == "completed",
        ).all()

        if not knowledge_sources:
            return None

        context_parts = []
        for source in knowledge_sources:
            chunks = self.db.query(KnowledgeChunk).filter(
                KnowledgeChunk.website_id == source.id
            ).all()

            for chunk in chunks:
                if chunk.content:
                    context_parts.append(chunk.content)

        if context_parts:
            return "\n\n---\n\n".join(context_parts)[:60000]
        return None

    def _get_training_rules(self) -> list:
        """Get enabled training rules for this company."""
        rules = self.db.query(TrainingRule).filter(
            TrainingRule.company_id == self.company.id,
            TrainingRule.is_enabled == True,
        ).order_by(TrainingRule.display_order).all()

        return [
            {
                "key": rule.rule_key,
                "name": rule.rule_name,
                "description": rule.rule_description,
            }
            for rule in rules
        ]

    def _get_example_answers(self) -> list:
        """Get active example Q&A pairs for this company."""
        examples = self.db.query(ExampleAnswer).filter(
            ExampleAnswer.company_id == self.company.id,
            ExampleAnswer.is_active == True,
            ExampleAnswer.is_verified == True,
        ).all()

        return [
            {
                "question": ex.question,
                "answer": ex.answer,
                "category": ex.category,
            }
            for ex in examples
        ]

    async def start(self):
        """
        Start the voice call: connect to OpenAI and bridge audio.

        1. Gather context and build system instructions
        2. Connect to OpenAI Realtime API
        3. Run twilio_to_openai and openai_to_twilio in parallel
        """
        t_start = time.time()
        self.is_running = True

        # Update AI worker status
        self.ai_worker.status = AIWorkerStatus.BUSY
        self.db.commit()

        try:
            # ── 1. Build system instructions ──────────────────────
            knowledge_context = await self._get_knowledge_context()
            training_rules = self._get_training_rules()
            example_answers = self._get_example_answers()
            system_prompts = get_system_prompts(self.db)

            # Get disclosure message from company settings
            disclosure_message = None
            if self.company.disclosure_message:
                disclosure_message = self.company.disclosure_message

            instructions = build_system_instructions(
                worker=self.ai_worker,
                company_name=self.company.name,
                disclosure_message=disclosure_message,
                knowledge_context=knowledge_context,
                training_rules=training_rules,
                example_answers=example_answers,
                system_prompts=system_prompts,
            )

            t_instructions = time.time()
            logger.info(
                f"[TIMING] Instructions built in {int((t_instructions - t_start) * 1000)}ms "
                f"({len(instructions)} chars)"
            )

            # ── 2. Get voice setting ─────────────────────────────
            # Priority: worker voice_id > global config voice_default > env var fallback
            voice = settings.OPENAI_REALTIME_VOICE  # env var fallback
            try:
                voice_config = self.db.query(GlobalConfig).filter(
                    GlobalConfig.key == "voice_default"
                ).first()
                if voice_config and voice_config.value:
                    voice = str(voice_config.value)
            except Exception:
                pass
            if self.ai_worker.voice_id:
                voice = self.ai_worker.voice_id

            # ── 3. Build tools ───────────────────────────────────
            tools = build_realtime_tools()

            # ── 4. Connect to OpenAI Realtime API ────────────────
            self.openai_session = OpenAIRealtimeSession(
                instructions=instructions,
                voice=voice,
                tools=tools,
            )
            await self.openai_session.connect()

            t_connected = time.time()
            logger.info(
                f"[TIMING] OpenAI Realtime connected in "
                f"{int((t_connected - t_instructions) * 1000)}ms"
            )

            # ── 5. Run parallel bridge loops ─────────────────────
            twilio_task = asyncio.create_task(self._twilio_to_openai())
            openai_task = asyncio.create_task(self._openai_to_twilio())

            logger.info(
                f"[TIMING] Call {self.call_sid}: bridge started at "
                f"+{int((time.time() - t_start) * 1000)}ms"
            )

            # Wait for either loop to finish (call ended or error)
            done, pending = await asyncio.wait(
                [twilio_task, openai_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the other task
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

            # Check for errors in completed tasks
            for task in done:
                if task.exception():
                    logger.error(
                        f"Bridge task error: {task.exception()}", exc_info=task.exception()
                    )

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for call {self.call_sid}")
        except Exception as e:
            logger.error(f"Error in RealtimeCallHandler.start: {e}", exc_info=True)
        finally:
            await self.cleanup()

    async def _twilio_to_openai(self):
        """
        Forward audio from Twilio to OpenAI Realtime API.

        Twilio sends media events with base64-encoded g711_ulaw audio.
        We forward them directly — no conversion needed.
        """
        while self.is_running:
            try:
                message = await self.websocket.receive_text()
                data = json.loads(message)

                event_type = data.get("event")

                if event_type == "media":
                    self._inbound_media_frames += 1
                    payload = data.get("media", {}).get("payload", "")
                    if payload and self.openai_session:
                        await self.openai_session.send_audio(payload)

                elif event_type == "stop":
                    logger.info(f"Twilio stream stopped for call {self.call_sid}")
                    self.is_running = False
                    break

                elif event_type == "mark":
                    # Marks are used for synchronization, log but don't act
                    pass

            except WebSocketDisconnect:
                logger.info(f"Twilio WS disconnected for call {self.call_sid}")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Error in twilio_to_openai: {e}")
                continue

    async def _openai_to_twilio(self):
        """
        Receive events from OpenAI Realtime API and handle them.

        - Audio deltas → forward to Twilio
        - Function calls → execute via call_tools.py → send result back
        - Transcripts → collect for call log
        - Speech events → clear Twilio queue (barge-in)
        """
        if not self.openai_session:
            return

        async for event in self.openai_session.receive_events():
            if not self.is_running:
                break

            event_type = event.get("type", "")

            try:
                if event_type == "response.audio.delta":
                    # Forward audio chunk to Twilio
                    audio_b64 = event.get("delta", "")
                    if audio_b64 and self.stream_sid:
                        media_msg = {
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {"payload": audio_b64},
                        }
                        await self.websocket.send_text(json.dumps(media_msg))
                        self._outbound_media_frames += 1

                elif event_type == "response.audio_transcript.done":
                    # Complete AI transcript for this response
                    transcript = event.get("transcript", "")
                    if transcript:
                        self._ai_transcript_parts.append(transcript)
                        logger.info(
                            f"[AI] {self.call_sid}: {transcript[:100]}..."
                            if len(transcript) > 100
                            else f"[AI] {self.call_sid}: {transcript}"
                        )

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    # User (caller) transcript
                    transcript = event.get("transcript", "")
                    if transcript:
                        self._user_transcript_parts.append(transcript)
                        logger.info(
                            f"[CALLER] {self.call_sid}: {transcript[:100]}..."
                            if len(transcript) > 100
                            else f"[CALLER] {self.call_sid}: {transcript}"
                        )

                elif event_type == "response.function_call_arguments.done":
                    # Function call ready — execute tool
                    await self._handle_function_call(event)

                elif event_type == "input_audio_buffer.speech_started":
                    # Caller started speaking — barge-in
                    # Clear Twilio's audio queue so the AI audio stops
                    if self.stream_sid:
                        clear_msg = {
                            "event": "clear",
                            "streamSid": self.stream_sid,
                        }
                        await self.websocket.send_text(json.dumps(clear_msg))
                        logger.debug(f"[BARGE-IN] Cleared Twilio queue for {self.call_sid}")

                elif event_type == "error":
                    self._openai_errors += 1
                    error_info = event.get("error", {})
                    logger.error(
                        f"OpenAI Realtime error for {self.call_sid}: "
                        f"{error_info.get('type', 'unknown')}: {error_info.get('message', '')}"
                    )

                elif event_type == "response.done":
                    # Full response completed — log for debugging
                    response = event.get("response", {})
                    status = response.get("status", "unknown")
                    if status != "completed":
                        logger.warning(
                            f"OpenAI response status: {status} for {self.call_sid}"
                        )

            except WebSocketDisconnect:
                logger.info(f"Twilio WS disconnected during openai_to_twilio")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Error handling OpenAI event {event_type}: {e}", exc_info=True)
                continue

    async def _handle_function_call(self, event: dict):
        """
        Execute a function call from OpenAI and send the result back.
        """
        call_id = event.get("call_id", "")
        fn_name = event.get("name", "")
        fn_args_str = event.get("arguments", "{}")

        self._function_calls_count += 1
        t0 = time.time()

        logger.info(f"[TOOL] {self.call_sid}: {fn_name}({fn_args_str})")

        try:
            fn_args = json.loads(fn_args_str)
        except json.JSONDecodeError:
            fn_args = {}

        # Build context for tool execution
        context = {
            "db": self.db,
            "company_id": str(self.company.id),
            "ai_worker_id": str(self.ai_worker.id) if self.ai_worker else None,
            "call_log_id": self.session_id,
            "calendar_id": None,
            "customer_phone": self.call_log.caller_number if self.call_log else None,
        }

        # Execute tool (synchronous DB operations — run in executor)
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None, _run_tool, fn_name, fn_args, context
            )
        except Exception as e:
            logger.error(f"Tool execution error for {fn_name}: {e}", exc_info=True)
            result = {"ok": False, "reason": "error", "message": str(e)}

        result_str = json.dumps(result, ensure_ascii=False, default=str)
        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info(
            f"[TOOL] {self.call_sid}: {fn_name} completed in {elapsed_ms}ms "
            f"-> {result_str[:200]}"
        )

        # Send result back to OpenAI
        if self.openai_session:
            await self.openai_session.send_function_result(call_id, result_str)

    async def cleanup(self):
        """
        Cleanup after call ends: save transcripts, update call log, close sessions.
        """
        self.is_running = False

        # Close OpenAI session
        if self.openai_session:
            await self.openai_session.close()
            self.openai_session = None

        # Combine transcript parts
        user_transcript = " ".join(self._user_transcript_parts).strip()
        ai_transcript = " ".join(self._ai_transcript_parts).strip()

        # Update call log
        if self.call_log:
            self.call_log.status = CallStatus.COMPLETED
            self.call_log.outcome = CallOutcome.HANDLED
            self.call_log.ended_at = datetime.utcnow()

            # Save transcript entries
            if user_transcript or ai_transcript:
                from app.models.call_log import CallTranscript

                if user_transcript:
                    caller_entry = CallTranscript(
                        call_log_id=self.call_log.id,
                        speaker="caller",
                        message=user_transcript,
                    )
                    self.db.add(caller_entry)

                if ai_transcript:
                    ai_entry = CallTranscript(
                        call_log_id=self.call_log.id,
                        speaker="ai",
                        message=ai_transcript,
                    )
                    self.db.add(ai_entry)

                # Analyze transcript for unanswered questions
                try:
                    detected_questions = analyze_call_transcript(
                        db=self.db,
                        company_id=str(self.company.id),
                        user_transcript=user_transcript,
                        assistant_transcript=ai_transcript,
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

        # ── Per-call metrics ──────────────────────────────────────
        logger.info(
            "[METRICS] call=%s inbound_frames=%d outbound_frames=%d "
            "function_calls=%d openai_errors=%d "
            "user_transcript_len=%d ai_transcript_len=%d",
            self.call_sid,
            self._inbound_media_frames,
            self._outbound_media_frames,
            self._function_calls_count,
            self._openai_errors,
            len(user_transcript),
            len(ai_transcript),
        )

        # Diagnostic if no audio was ever sent to the caller
        if self._outbound_media_frames == 0:
            reason = "unknown"
            if self._openai_errors > 0:
                reason = "openai_errors"
            elif self._inbound_media_frames == 0:
                reason = "no_inbound_audio"
            else:
                reason = "no_ai_response"
            logger.error(
                "[NO_AUDIO_SENT_TO_TWILIO] call=%s reason=%s "
                "inbound_frames=%d openai_errors=%d",
                self.call_sid,
                reason,
                self._inbound_media_frames,
                self._openai_errors,
            )


async def voice_websocket_handler(
    websocket: WebSocket,
    db: Session,
):
    """
    Main WebSocket handler for Twilio Media Streams.

    CRITICAL: accept() must happen immediately so Twilio gets HTTP 101.
    All heavy work (OpenAI connection, context building) happens AFTER accept.
    """
    t_enter = time.time()

    await websocket.accept()
    t_accept = time.time()
    logger.info(f"[WS] accept() done in {int((t_accept - t_enter) * 1000)}ms")

    # Variables to store call info
    call_sid = None
    stream_sid = None
    to_number = None
    from_number = None
    handler: Optional[RealtimeCallHandler] = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            event_type = data.get("event")

            if event_type == "connected":
                t_connected = time.time()
                logger.info(
                    f"[WS] Twilio 'connected' event at "
                    f"+{int((t_connected - t_accept) * 1000)}ms"
                )
                continue

            elif event_type == "start":
                t_start = time.time()
                start_data = data.get("start", {})
                call_sid = start_data.get("callSid")
                stream_sid = start_data.get("streamSid")

                custom_params = start_data.get("customParameters", {})
                to_number = custom_params.get("to") or start_data.get("to")
                from_number = custom_params.get("from") or start_data.get("from")

                logger.info(
                    f"[WS] Twilio 'start' at +{int((t_start - t_accept) * 1000)}ms "
                    f"CallSid={call_sid} From={from_number} To={to_number}"
                )

                # Create and initialize handler
                handler = RealtimeCallHandler(
                    websocket=websocket,
                    db=db,
                    call_sid=call_sid,
                    stream_sid=stream_sid,
                )

                await handler.initialize_from_phone_number(to_number, from_number)

                # Start processing (blocks until call ends)
                await handler.start()
                break

            elif event_type == "stop":
                logger.info("Stream stopped before starting")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"Error in voice WebSocket handler: {e}", exc_info=True)
    finally:
        if handler:
            await handler.cleanup()
        t_end = time.time()
        logger.info(
            f"[WS] handler finished for call {call_sid}, "
            f"total={int((t_end - t_enter) * 1000)}ms"
        )
