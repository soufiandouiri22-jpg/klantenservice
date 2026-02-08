"""
klantenservice.ai - System Prompts Model

Global prompts that apply to all AI workers across all companies.
Managed by superadmins via the /admin interface.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class SystemPrompt(Base):
    """
    System Prompt model - global prompts that apply to all AI workers.
    These are managed by superadmins and affect all companies.
    """
    __tablename__ = "system_prompts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identification
    key = Column(String(100), unique=True, nullable=False)  # e.g., "language_rules"
    name = Column(String(255), nullable=False)  # e.g., "Taal & Spraak"
    description = Column(Text, nullable=True)  # Admin description
    
    # Categorization
    category = Column(String(100), nullable=False, default="general")
    # Categories: communication, safety, privacy, quality, edge_cases, general
    
    # Content
    content = Column(Text, nullable=False)  # The actual prompt text
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Ordering
    display_order = Column(Integer, default=0)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Relationships
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    
    def __repr__(self):
        return f"<SystemPrompt {self.key}>"


# Default system prompts that are created on first run.
# Only policies that are admin-editable and not covered by the code-level prompt.
# Personality, tone, conversation flow, safety, and language rules are all
# handled in build_system_instructions() — no need to duplicate here.
DEFAULT_SYSTEM_PROMPTS = [
    {
        "key": "privacy_gdpr",
        "name": "Privacy & GDPR",
        "category": "privacy",
        "description": "Privacy- en GDPR-gerelateerde beleidsregels (juridisch aanpasbaar)",
        "content": """- Verwerk alleen gegevens die noodzakelijk zijn voor het beantwoorden van de vraag
- De klant heeft recht op inzage in zijn/haar gegevens — verwijs naar de klantenservice
- Deel nooit klantgegevens met derden zonder toestemming""",
        "display_order": 1,
        "is_active": True,
    },
    {
        "key": "ai_disclosure",
        "name": "AI Disclosure",
        "category": "compliance",
        "description": "Transparantie over AI — aanpasbaar per bedrijfswens",
        "content": """- Als een klant vraagt of ze met een mens of robot praten, antwoord eerlijk dat je een AI-assistent bent
- Bied aan om door te verbinden met een menselijke medewerker als de klant dat wenst""",
        "display_order": 2,
        "is_active": True,
    },
]
