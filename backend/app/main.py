"""
klantenservice.ai - Main FastAPI Application
"""
from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.core.database import get_db
from app.api.v1.router import api_router
from app.websockets.voice_handler import voice_websocket_handler

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting klantenservice.ai API", version="1.0.0")
    
    # Initialize Sentry if configured
    if settings.SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=settings.APP_ENV,
        )
        logger.info("Sentry initialized")
    
    # Pre-load PersonaPlex model if enabled
    if settings.LLM_API_URL:
        try:
            from app.services.personaplex_service import personaplex_service
            # Model loading is deferred to first call for faster startup
            logger.info("PersonaPlex service initialized")
        except Exception as e:
            logger.warning(f"PersonaPlex not available: {e}")
    
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
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    return {"status": "healthy", "service": "klantenservice.ai"}


# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# WebSocket endpoint for Twilio Media Streams
@app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    
    Twilio connects here when a call is answered and streams audio
    bidirectionally through PersonaPlex-7B for AI conversation.
    
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
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
