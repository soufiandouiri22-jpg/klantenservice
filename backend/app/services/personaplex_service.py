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
import time
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
        
        # Pre-warmed sessions: worker_id -> ConversationSession
        # These sessions are initialized before a call comes in so
        # PersonaPlex can respond immediately when someone calls.
        self._warm_sessions: Dict[str, ConversationSession] = {}
        self._warming_in_progress: set = set()  # worker_ids currently warming
        
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
        disclosure_message: Optional[str] = None,
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
        
        # Format disclosure message if provided
        formatted_disclosure = ""
        if disclosure_message:
            formatted_disclosure = disclosure_message.format(
                company_name=company_name,
                ai_worker_name=worker.name
            )
        
        # Build disclosure section if provided
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
            ping_interval=20,   # Send WebSocket protocol ping every 20s (keeps connection alive)
            ping_timeout=20,    # Allow 20s for pong response (GPU init runs in thread, event loop is free)
            close_timeout=10,
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
        preset = None
        
        # 1. Check company-level override
        if company and company.admin_overrides:
            preset = company.admin_overrides.get("voice_preset")
            if preset:
                logger.debug(f"Using company voice preset: {preset}")
        
        # 2. Check platform-wide default
        if not preset and db:
            try:
                config = db.query(GlobalConfig).filter(
                    GlobalConfig.key == "voice_default_preset"
                ).first()
                if config and config.value:
                    preset = config.value
                    logger.debug(f"Using platform voice preset: {preset}")
            except Exception as e:
                logger.warning(f"Could not get platform voice preset: {e}")
        
        # 3. Hardcoded fallback
        if not preset:
            preset = "NATF2"
            logger.debug("Using hardcoded fallback voice preset: NATF2")
        
        # Ensure .pt extension is present
        if not preset.endswith('.pt'):
            preset = preset + '.pt'
        
        return preset

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
        # Get disclosure message from company
        disclosure_message = company.disclosure_message if company else None
        
        # Build persona prompt
        persona_prompt = self.build_persona_prompt(
            worker=worker,
            company_name=company.name,
            disclosure_message=disclosure_message,
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
            
            # Wait for "initialized" confirmation, ignoring "initializing" progress pings
            # The pod sends keepalive pings every 10s during step_system_prompts
            # On A40, step_system_prompts can take 200+ seconds with large prompts
            deadline = asyncio.get_event_loop().time() + 300
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError()
                response = await asyncio.wait_for(ws.recv(), timeout=remaining)
                response_data = json.loads(response)
                
                if response_data.get("status") == "initialized":
                    logger.info(f"Session {session_id} initialized successfully")
                    break
                elif response_data.get("status") == "initializing":
                    logger.debug(f"Session {session_id} still initializing...")
                else:
                    logger.warning(f"Unexpected init response: {response_data}")
                    break
            
        except asyncio.TimeoutError:
            logger.error(f"Session init timeout for {session_id} (300s)")
            # Clean up: close the orphaned WS and remove stale session
            # so the next pre-warm attempt starts fresh.
            # NOTE: the pod may still be running _init_session_sync in a
            # background thread.  When it finishes, it stores the session
            # in its sessions dict.  On the next backend attempt the pod
            # will find the existing session and skip step_system_prompts.
            if session.websocket:
                try:
                    await session.websocket.close()
                except Exception:
                    pass
                session.websocket = None
            session.is_active = False
            self.active_sessions.pop(session_id, None)
            raise
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}", exc_info=True)
            # Clean up on any failure
            if session.websocket:
                try:
                    await session.websocket.close()
                except Exception:
                    pass
                session.websocket = None
            session.is_active = False
            self.active_sessions.pop(session_id, None)
            raise
        
        return session
    
    async def pre_warm_session(
        self,
        worker: AIWorker,
        company: Company,
        db,
    ) -> Optional[ConversationSession]:
        """
        Pre-warm a PersonaPlex session for an AI worker.
        
        This runs the heavy GPU initialization (step_system_prompts) in advance
        so that when a call comes in, the session is ready and PersonaPlex can
        respond immediately with the greeting.
        """
        worker_id = str(worker.id)
        
        # Skip if already warming or already warm
        if worker_id in self._warming_in_progress:
            logger.debug(f"Already warming session for worker {worker_id}")
            return None
        if worker_id in self._warm_sessions:
            logger.debug(f"Session already warm for worker {worker_id}")
            return self._warm_sessions[worker_id]
        
        if self.mock_mode:
            logger.debug("Mock mode: skipping pre-warm")
            return None
        
        self._warming_in_progress.add(worker_id)
        
        try:
            # Use a temporary session_id for pre-warming
            warm_session_id = f"warm-{worker_id}"
            
            # Get all context needed for the prompt
            knowledge_context = None
            training_rules = []
            example_answers = []
            system_prompts = self.get_system_prompts(db)
            
            # Get knowledge context
            try:
                from app.models.website_knowledge import WebsiteKnowledge, KnowledgeChunk
                sources = db.query(WebsiteKnowledge).filter(
                    WebsiteKnowledge.company_id == company.id,
                    WebsiteKnowledge.is_active == True,
                    WebsiteKnowledge.status == "completed"
                ).all()
                if sources:
                    parts = []
                    for source in sources:
                        chunks = db.query(KnowledgeChunk).filter(
                            KnowledgeChunk.website_id == source.id
                        ).limit(10).all()
                        for chunk in chunks:
                            if chunk.content:
                                parts.append(chunk.content[:500])
                    if parts:
                        knowledge_context = "\n\n---\n\n".join(parts)[:8000]
            except Exception as e:
                logger.warning(f"Pre-warm: could not get knowledge context: {e}")
            
            # Get training rules
            try:
                from app.models.training import TrainingRule
                rules = db.query(TrainingRule).filter(
                    TrainingRule.company_id == company.id,
                    TrainingRule.is_enabled == True
                ).all()
                training_rules = [
                    {"key": r.rule_key, "name": r.rule_name, "description": r.rule_description}
                    for r in rules
                ]
            except Exception as e:
                logger.warning(f"Pre-warm: could not get training rules: {e}")
            
            # Get example answers
            try:
                from app.models.training import ExampleAnswer
                examples = db.query(ExampleAnswer).filter(
                    ExampleAnswer.company_id == company.id,
                    ExampleAnswer.is_active == True,
                    ExampleAnswer.is_verified == True
                ).all()
                example_answers = [
                    {"question": ex.question, "answer": ex.answer, "category": ex.category}
                    for ex in examples
                ]
            except Exception as e:
                logger.warning(f"Pre-warm: could not get example answers: {e}")
            
            logger.info(f"Pre-warming session for worker {worker.name} ({worker_id})")
            
            session = await self.create_session(
                session_id=warm_session_id,
                worker=worker,
                company=company,
                db=db,
                knowledge_context=knowledge_context,
                training_rules=training_rules,
                example_answers=example_answers,
                system_prompts=system_prompts
            )
            
            # Store in warm pool
            self._warm_sessions[worker_id] = session
            logger.info(f"Session pre-warmed for worker {worker.name} ({worker_id})")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to pre-warm session for worker {worker_id}: {e}")
            return None
        finally:
            self._warming_in_progress.discard(worker_id)
    
    async def _mark_session_unhealthy(self, session: ConversationSession, session_id: str):
        """
        Mark a session as unhealthy after a timeout or connection error.
        Closes the WS, removes from active/warm pools, and logs clearly.
        """
        logger.warning(
            "[SESSION_UNHEALTHY] session=%s worker=%s — closing WS and removing from pools",
            session_id, session.worker_id
        )
        session.is_active = False
        
        # Close the WS connection (best-effort)
        if session.websocket:
            try:
                await session.websocket.close()
            except Exception:
                pass
            session.websocket = None
        
        # Remove from active and warm pools
        self.active_sessions.pop(session_id, None)
        self._warm_sessions.pop(session.worker_id, None)
    
    async def is_session_alive(self, session: ConversationSession) -> bool:
        """
        Check if a pre-warmed session's WebSocket is still alive.
        
        Sends a ping over the existing WebSocket and waits for pong.
        Returns True if alive, False if dead or timed out.
        """
        if not session or not session.websocket:
            return False
        
        try:
            await session.websocket.send(json.dumps({"action": "ping"}))
            response = await asyncio.wait_for(session.websocket.recv(), timeout=3.0)
            data = json.loads(response)
            if data.get("action") == "pong":
                return True
            return False
        except Exception:
            return False
    
    async def claim_warm_session(self, worker_id: str, new_session_id: str) -> Optional[ConversationSession]:
        """
        Claim a pre-warmed session for an actual call.
        
        Verifies the session is alive before claiming. If dead, discards it
        and returns None so the caller falls back to fresh init.
        """
        worker_id = str(worker_id)
        
        session = self._warm_sessions.get(worker_id)
        if not session:
            logger.info(f"No warm session for worker {worker_id}")
            return None
        
        # Verify the session is still alive
        alive = await self.is_session_alive(session)
        if not alive:
            logger.warning(f"Claim failed: warm session dead for worker {worker_id} -> fallback init")
            self._warm_sessions.pop(worker_id, None)
            self.active_sessions.pop(session.session_id, None)
            return None
        
        # Remove from warm pool
        self._warm_sessions.pop(worker_id, None)
        
        # Move from warm pool to active sessions with new id
        old_id = session.session_id
        session.session_id = new_session_id
        
        self.active_sessions.pop(old_id, None)
        self.active_sessions[new_session_id] = session
        
        logger.info(f"Claim warm session OK for worker {worker_id}: {old_id} -> {new_session_id}")
        return session
    
    async def _warm_keepalive_loop(self):
        """
        Periodic background task that ensures warm sessions are always available.
        
        - When all workers have a live warm session: check every 2 minutes.
        - When pre-warming fails or no warm session exists: retry every 10 seconds.
        
        This fast-retry ensures that after a deploy (pod or backend), the warm
        session is established as quickly as possible.
        """
        from app.core.database import SessionLocal
        
        rewarm_lock = asyncio.Lock()
        
        INTERVAL_OK = 120       # 2 min when everything is warm
        INTERVAL_RETRY = 10     # 10 s when we need to (re)warm
        
        # Wait for app to fully start
        await asyncio.sleep(5)
        
        logger.info("[KEEPALIVE] Warm keepalive loop started (pod_url=%s)", self.pod_url[:60] if self.pod_url else "NONE")
        
        iteration = 0
        while True:
            iteration += 1
            all_warm = True
            t0 = time.time()
            db = SessionLocal()
            try:
                async with rewarm_lock:
                    from app.models.ai_worker import AIWorker, AIWorkerStatus
                    from app.models.company import Company
                    
                    workers = db.query(AIWorker).join(Company, AIWorker.company_id == Company.id).filter(
                        AIWorker.is_active == True,
                        AIWorker.status == AIWorkerStatus.AVAILABLE,
                        Company.is_kill_switched == False,
                    ).all()
                    
                    pool_target = settings.WARM_POOL_SIZE
                    
                    if not workers:
                        logger.info("[KEEPALIVE] iter=%d No available workers found (or all kill-switched)", iteration)
                        all_warm = False
                    
                    warmed_count = 0
                    for worker in workers:
                        worker_id = str(worker.id)
                        
                        session = self._warm_sessions.get(worker_id)
                        
                        if session:
                            alive = await self.is_session_alive(session)
                            if alive:
                                logger.info(
                                    "[KEEPALIVE] iter=%d worker=%s (%s) -> ALIVE",
                                    iteration, worker.name, worker_id[:8]
                                )
                            else:
                                logger.warning(
                                    "[KEEPALIVE] iter=%d worker=%s (%s) -> DEAD, re-warming",
                                    iteration, worker.name, worker_id[:8]
                                )
                                all_warm = False
                                self._warm_sessions.pop(worker_id, None)
                                self.active_sessions.pop(session.session_id, None)
                                
                                company = db.query(Company).filter(Company.id == worker.company_id).first()
                                if company:
                                    await self.pre_warm_session(worker, company, db)
                        else:
                            all_warm = False
                            if worker_id not in self._warming_in_progress:
                                company = db.query(Company).filter(Company.id == worker.company_id).first()
                                if company:
                                    logger.info(
                                        "[KEEPALIVE] iter=%d worker=%s (%s) -> NO SESSION, pre-warming",
                                        iteration, worker.name, worker_id[:8]
                                    )
                                    await self.pre_warm_session(worker, company, db)
                            else:
                                logger.info(
                                    "[KEEPALIVE] iter=%d worker=%s (%s) -> warming in progress, skipping",
                                    iteration, worker.name, worker_id[:8]
                                )
                        
                        warmed_count += 1
                        if warmed_count >= pool_target:
                            break
                    
                    logger.info(
                        "[KEEPALIVE] iter=%d pool_target=%d pool_current=%d",
                        iteration, pool_target, len(self._warm_sessions)
                    )
                        
            except Exception as e:
                logger.error("[KEEPALIVE] iter=%d ERROR: %s", iteration, e, exc_info=True)
                all_warm = False
            finally:
                db.close()
            
            # Double-check we actually have warm sessions
            if all_warm and len(self._warm_sessions) == 0:
                all_warm = False
            
            elapsed_ms = int((time.time() - t0) * 1000)
            interval = INTERVAL_OK if all_warm else INTERVAL_RETRY
            logger.info(
                "[KEEPALIVE] iter=%d done in %dms, warm_count=%d, next_check=%ds",
                iteration, elapsed_ms, len(self._warm_sessions), interval
            )
            await asyncio.sleep(interval)
    
    async def pre_warm_available_workers(self, db):
        """
        Pre-warm sessions for available AI workers up to WARM_POOL_SIZE.
        Called after each call ends for fast recovery.
        The keepalive loop handles periodic health checks.
        """
        try:
            from app.models.ai_worker import AIWorker, AIWorkerStatus
            from app.models.company import Company
            
            pool_target = settings.WARM_POOL_SIZE
            
            workers = db.query(AIWorker).join(Company, AIWorker.company_id == Company.id).filter(
                AIWorker.is_active == True,
                AIWorker.status == AIWorkerStatus.AVAILABLE,
                Company.is_kill_switched == False,
            ).all()
            
            warmed_count = 0
            for worker in workers:
                worker_id = str(worker.id)
                if worker_id not in self._warm_sessions and worker_id not in self._warming_in_progress:
                    company = db.query(Company).filter(Company.id == worker.company_id).first()
                    if company:
                        asyncio.create_task(self.pre_warm_session(worker, company, db))
                        warmed_count += 1
                        if warmed_count >= pool_target:
                            break
        except Exception as e:
            logger.error(f"Error pre-warming workers: {e}")
    
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
        
        POD_RECV_TIMEOUT = 45.0  # seconds per recv (transcript + audio)
        
        try:
            async with session._lock:
                # Send audio segment bytes
                await ws.send(audio_segment)
                
                assistant_text = ""
                audio_response = None
                received_turn_id = turn_id
                
                # First: receive JSON (transcript_final)
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=POD_RECV_TIMEOUT)
                    
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
                    logger.error(
                        "[POD_TIMEOUT] Timeout waiting for transcript_final "
                        "session=%s turn=%d timeout=%.0fs ws_open=%s",
                        session_id, turn_id, POD_RECV_TIMEOUT,
                        ws.open if hasattr(ws, 'open') else 'unknown'
                    )
                    # Mark session as unhealthy — close WS and remove from active
                    await self._mark_session_unhealthy(session, session_id)
                    return None, "", turn_id
                
                # Second: receive audio bytes (if not already received)
                if audio_response is None:
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=POD_RECV_TIMEOUT)
                        
                        if isinstance(response, bytes):
                            audio_response = response
                            logger.debug(f"Received {len(audio_response)} bytes audio for turn {received_turn_id}")
                        elif isinstance(response, str):
                            # Might be an error
                            data = json.loads(response)
                            if "error" in data:
                                logger.error(f"Pod error during audio recv: {data['error']}")
                    
                    except asyncio.TimeoutError:
                        logger.error(
                            "[POD_TIMEOUT] Timeout waiting for audio response "
                            "session=%s turn=%d timeout=%.0fs",
                            session_id, turn_id, POD_RECV_TIMEOUT
                        )
                        await self._mark_session_unhealthy(session, session_id)
                
                return audio_response, assistant_text, received_turn_id
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket closed for session {session_id}: {e}")
            await self._mark_session_unhealthy(session, session_id)
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
