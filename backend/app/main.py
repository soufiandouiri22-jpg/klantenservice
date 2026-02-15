"""
klantenservice.ai - Main FastAPI Application
"""
import logging
import os
import sys

from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
import structlog

from app.core.config import settings
from app.core.database import get_db
from app.api.v1.router import api_router
from app.websockets.voice_handler import voice_websocket_handler

# ── Logging ──────────────────────────────────────────────────────────
# Ensure the root logger has a StreamHandler to stdout so that ALL
# application loggers (voice_handler, openai_realtime_service, etc.) have
# their output captured by Render / Docker / systemd.
_root = logging.getLogger()
if not any(isinstance(h, logging.StreamHandler) for h in _root.handlers):
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _root.addHandler(_handler)
_root.setLevel(logging.INFO)

# Configure structured logging (used by main.py only)
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


async def _prewarm_voice_previews():
    """
    Pre-generate voice previews for all ElevenLabs voices at startup.
    Runs in the background so it doesn't block server startup.
    """
    import asyncio
    import httpx
    from app.core.voices import ELEVENLABS_VOICES, VOICE_SAMPLE_TEXT
    from app.api.v1.endpoints.ai_workers import _voice_preview_cache

    if not settings.ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set — skipping voice preview pre-warm")
        return

    logger.info(f"Pre-warming {len(ELEVENLABS_VOICES)} voice previews...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for voice in ELEVENLABS_VOICES:
            voice_id = voice["id"]
            if voice_id in _voice_preview_cache:
                continue  # Already cached
            try:
                resp = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                    headers={
                        "xi-api-key": settings.ELEVENLABS_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": VOICE_SAMPLE_TEXT,
                        "model_id": "eleven_v3",
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.8,
                        },
                    },
                )
                resp.raise_for_status()
                audio_bytes = resp.content
                if len(audio_bytes) >= 1000:
                    _voice_preview_cache[voice_id] = audio_bytes
                    logger.info(f"Pre-warmed voice preview: {voice['name']} ({len(audio_bytes)} bytes)")
                else:
                    logger.warning(f"Pre-warm skipped {voice['name']}: audio too small ({len(audio_bytes)} bytes)")
            except Exception as e:
                logger.warning(f"Pre-warm failed for {voice['name']}: {e}")
            # Small delay between requests to avoid rate limiting
            await asyncio.sleep(1)

    logger.info(f"Voice preview pre-warm complete ({len(_voice_preview_cache)} cached)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    import asyncio

    # Startup
    effective_port = os.environ.get("PORT", "8000")
    logger.info(
        "Starting klantenservice.ai API",
        version="1.0.0",
        port=effective_port,
        env=settings.APP_ENV,
    )
    
    # Initialize Sentry if configured
    if settings.SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=settings.APP_ENV,
        )
        logger.info("Sentry initialized")
    
    # ElevenLabs Conversational AI — no startup needed (calls registered on demand)
    if settings.ELEVENLABS_API_KEY:
        logger.info("ElevenLabs Conversational AI configured")
    else:
        logger.warning("ELEVENLABS_API_KEY not set — voice calls will fail")
    
    # Pre-warm voice previews in the background (non-blocking)
    asyncio.create_task(_prewarm_voice_previews())
    
    yield
    
    # Shutdown
    logger.info("Shutting down klantenservice.ai API")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-telefonisten voor bedrijven - API",
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
    redirect_slashes=False,  # Prevent 307 redirects for trailing slashes
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoints
@app.get("/health")
@app.get("/healthz")
async def health_check():
    """Health check endpoint for load balancers. Always fast, no dependencies."""
    return {"status": "healthy", "service": "klantenservice.ai"}


@app.get("/ready")
async def readiness_check():
    """
    Readiness check — returns 200 when the service is ready to handle calls.
    With OpenAI Realtime API, we're always ready if the API key is configured.
    """
    try:
        if settings.OPENAI_API_KEY:
            return {"status": "ready", "engine": "openai_realtime"}
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "OPENAI_API_KEY not configured"},
        )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "unknown"},
        )


# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Serve cached TTS audio files as static assets
_tts_dir = Path("/tmp/tts_cache")
_tts_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/tts", StaticFiles(directory=str(_tts_dir)), name="tts_static")


# WebSocket endpoint for Twilio Media Streams
@app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    
    Twilio connects here when a call is answered and streams audio
    bidirectionally through OpenAI Realtime API for AI conversation.
    
    TwiML should include:
    <Stream url="wss://your-domain.com/ws/voice">
        <Parameter name="to" value="{{To}}" />
        <Parameter name="from" value="{{From}}" />
    </Stream>
    """
    # Get database session
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        await voice_websocket_handler(websocket, db)
    finally:
        db.close()


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.DEBUG,
    )
