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
    
    # Hugging Face (for PersonaPlex model)
    HUGGINGFACE_TOKEN: str = ""
    
    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    
    # WebSocket (for Twilio Media Streams)
    WEBSOCKET_URL: str = "wss://api.klantenservice.ai/ws/voice"
    
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
    RESEND_FROM_EMAIL: str = "noreply@klantenservice.ai"
    
    # Frontend URL (for invite links)
    FRONTEND_URL: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
