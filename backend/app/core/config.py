"""
klantenservice.ai - Application Configuration
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "klantenservice.ai"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # AI / LLM
    LLM_API_URL: str = "http://localhost:8080/v1"
    LLM_MODEL_NAME: str = "personaplex-7b"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.7
    
    # OpenAI (for Orchestrator + STT + Realtime Voice)
    OPENAI_API_KEY: str = ""
    ORCHESTRATOR_MODEL: str = "gpt-4o-mini"  # Model for intent detection + function calling
    OPENAI_REALTIME_MODEL: str = "gpt-realtime"  # Latest production speech-to-speech model (Aug 2025)
    OPENAI_REALTIME_VOICE: str = "ash"  # alloy, ash, ballad, coral, echo, sage, shimmer, verse, cedar, marin
    
    # Hugging Face (for PersonaPlex model)
    HUGGINGFACE_TOKEN: str = ""
    
    # PersonaPlex Dedicated Pod
    PERSONAPLEX_POD_URL: str = ""  # URL of the dedicated GPU pod (e.g., https://pod-id.runpod.net)
    PERSONAPLEX_POD_TOKEN: str = ""  # Authentication token for the pod
    WARM_POOL_SIZE: int = 1  # Max workers to keep pre-warmed (1 per pod; increase when adding pods)
    
    # RunPod (legacy - for serverless fallback)
    RUNPOD_API_KEY: str = ""
    RUNPOD_ENDPOINT_ID: str = ""  # Deprecated: use PERSONAPLEX_POD_URL instead
    
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_ADDRESS_SID: str = ""  # Address SID for purchasing NL phone numbers (required by Twilio regulations)
    
    # WebSocket (for Twilio Media Streams)
    WEBSOCKET_URL: str = ""  # Set via environment variable
    
    # Google OAuth (used for both Calendar and Auth)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""  # Calendar redirect
    GOOGLE_AUTH_REDIRECT_URI: str = "http://localhost:3000/login/callback"  # Auth redirect
    
    # Microsoft
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_REDIRECT_URI: str = ""
    
    # ChromaDB
    CHROMA_PERSIST_DIRECTORY: str = "/data/chroma"
    
    # Sentry
    SENTRY_DSN: str = ""
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Encryption
    ENCRYPTION_KEY: str = ""
    
    # Resend (Email)
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "no-reply@klantenservice.ai"
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    # Price IDs (monthly and yearly)
    STRIPE_PRICE_STARTER_MONTHLY: str = ""
    STRIPE_PRICE_STARTER_YEARLY: str = ""
    STRIPE_PRICE_BUSINESS_MONTHLY: str = ""
    STRIPE_PRICE_BUSINESS_YEARLY: str = ""
    STRIPE_PRICE_ENTERPRISE_MONTHLY: str = ""
    STRIPE_PRICE_ENTERPRISE_YEARLY: str = ""
    
    # KVK (Kamer van Koophandel)
    KVK_API_KEY: str = "l7xx1f2691f2520d487b902f4e0b57a0b197"  # Test key; replace with production key
    KVK_API_URL: str = "https://api.kvk.nl/test/api/v2"  # Use https://api.kvk.nl/api/v2 for production
    
    # Frontend URL (for invite links)
    FRONTEND_URL: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
