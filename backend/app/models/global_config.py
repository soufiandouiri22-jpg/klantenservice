"""
klantenservice.ai - Global Configuration Model

Platform-wide settings that apply to all companies.
Categories: policies, model, voice, thresholds
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


# Default configurations that will be seeded
DEFAULT_CONFIGS = [
    # Policies - Non-negotiable platform rules
    {
        "key": "policy_never_guess",
        "value": True,
        "category": "policies",
        "description": "AI mag nooit informatie verzinnen - alleen feiten uit tools gebruiken"
    },
    {
        "key": "policy_confirm_appointments",
        "value": True,
        "category": "policies",
        "description": "Verplichte bevestiging van afspraken (datum + tijd herhalen)"
    },
    {
        "key": "policy_pii_mask_logs",
        "value": True,
        "category": "policies",
        "description": "PII masking in logs (telefoon, email, adres)"
    },
    {
        "key": "policy_max_tool_calls",
        "value": 10,
        "category": "policies",
        "description": "Maximum aantal tool calls per gesprek"
    },
    {
        "key": "policy_escalate_on_complaint",
        "value": True,
        "category": "policies",
        "description": "Escaleer naar dashboard bij klachten"
    },
    {
        "key": "policy_escalate_on_low_confidence",
        "value": True,
        "category": "policies",
        "description": "Escaleer bij lage confidence scores"
    },
    
    # Model & Routing
    {
        "key": "model_default",
        "value": "gpt-4o-mini",
        "category": "model",
        "description": "Standaard orchestrator model"
    },
    {
        "key": "model_fallback",
        "value": "gpt-3.5-turbo",
        "category": "model",
        "description": "Fallback model bij fouten"
    },
    {
        "key": "model_use_big_on_unknown",
        "value": True,
        "category": "model",
        "description": "Gebruik groter model bij onbekende vragen"
    },
    {
        "key": "model_big",
        "value": "gpt-4o",
        "category": "model",
        "description": "Groot model voor complexe situaties"
    },
    {
        "key": "model_token_budget_daily",
        "value": 1000000,
        "category": "model",
        "description": "Dagelijks token budget (platform-wide)"
    },
    {
        "key": "model_rate_limit_rpm",
        "value": 500,
        "category": "model",
        "description": "Rate limit: requests per minuut"
    },
    
    # Voice / Audio Tuning
    {
        "key": "voice_default_preset",
        "value": "NATF0",
        "category": "voice",
        "description": "Standaard PersonaPlex voice preset voor alle gesprekken"
    },
    {
        "key": "voice_auto_respond",
        "value": True,
        "category": "voice",
        "description": "VAD/auto-respond standaard aan voor nieuwe bedrijven"
    },
    {
        "key": "voice_segment_ms",
        "value": 2500,
        "category": "voice",
        "description": "Audio segment lengte in milliseconden"
    },
    {
        "key": "voice_vad_sensitivity",
        "value": 0.5,
        "category": "voice",
        "description": "Voice Activity Detection gevoeligheid (0-1)"
    },
    {
        "key": "voice_interrupt_policy",
        "value": "allow",
        "category": "voice",
        "description": "Interrupt policy: allow, queue, ignore"
    },
    {
        "key": "voice_max_latency_ms",
        "value": 3000,
        "category": "voice",
        "description": "Maximum latency budget in ms"
    },
    {
        "key": "voice_queue_max_size",
        "value": 5,
        "category": "voice",
        "description": "Maximum queue grootte voor backpressure"
    },
    
    # Thresholds
    {
        "key": "threshold_rag_confidence",
        "value": 0.7,
        "category": "thresholds",
        "description": "Minimum RAG confidence score (0-1)"
    },
    {
        "key": "threshold_intent_confidence",
        "value": 0.8,
        "category": "thresholds",
        "description": "Minimum intent detection confidence (0-1)"
    },
    {
        "key": "threshold_unknown_sensitivity",
        "value": 0.6,
        "category": "thresholds",
        "description": "Gevoeligheid voor onbekende vragen (0-1)"
    },
    {
        "key": "threshold_max_turns_no_progress",
        "value": 5,
        "category": "thresholds",
        "description": "Max turns zonder vooruitgang -> handoff"
    },
]


class GlobalConfig(Base):
    """
    Global Configuration model - platform-wide settings.
    
    Categories:
    - policies: Non-negotiable rules (never guess, confirm appointments, etc.)
    - model: LLM selection and routing
    - voice: Audio/realtime tuning
    - thresholds: Confidence thresholds
    """
    __tablename__ = "global_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Config key (unique identifier)
    key = Column(String(100), unique=True, nullable=False, index=True)
    
    # Value (JSON to support different types: bool, int, float, string, object)
    value = Column(JSON, nullable=False)
    
    # Category for grouping
    category = Column(String(50), nullable=False, index=True)
    
    # Human-readable description
    description = Column(Text, nullable=True)
    
    # Audit trail
    updated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    
    def __repr__(self):
        return f"<GlobalConfig {self.key}={self.value}>"
