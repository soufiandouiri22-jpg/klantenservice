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
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # OpenAI (for Orchestrator function calling)
    OPENAI_API_KEY: str = ""
    ORCHESTRATOR_MODEL: str = "gpt-4o-mini"
    
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
    
    # ElevenLabs (Conversational AI + TTS)
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_AGENT_ID: str = ""  # Created via API; used for register_call
    
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
