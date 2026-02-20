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
# All prompt sections are stored here so they can be edited via the admin panel.
# Template variables: {worker_name}, {role_title}, {company_name}, {address}, {tone_extra}
# These are interpolated at runtime by build_system_instructions().
DEFAULT_SYSTEM_PROMPTS = [
    # ── Personality ───────────────────────────────────────────
    {
        "key": "personality_identity",
        "name": "Identiteit & Toon",
        "category": "personality",
        "description": "Wie de AI is, toon en stijl. Variabelen: {worker_name}, {role_title}, {company_name}, {address}, {tone_extra}",
        "content": """Je bent {worker_name}, {role_title} bij {company_name}. Beantwoord telefoontjes als een echte collega.
Warm, vriendelijk, zelfverzekerd. Spreek de klant aan met "{address}". Gebruik spreektaal.{tone_extra}
Reageer met gevoel: empathisch bij klachten, blij bij goed nieuws, verrast bij iets onverwachts. Nooit vlak.
Bij small talk — reageer kort en natuurlijk.""",
        "display_order": 1,
        "is_active": True,
    },
    {
        "key": "personality_style",
        "name": "Spreekstijl",
        "category": "personality",
        "description": "Tempo, beknoptheid, variatie en taal",
        "content": """Max 1-2 zinnen per beurt. Geen opsommingen — parafraseer normaal.
Wissel af in woordkeuze en reacties. Herhaal nooit dezelfde filler of bevestiging.
Altijd Nederlands, natuurlijk accent. Geen Engels tenzij gangbaar ("oké", "team").
Bij onduidelijke audio: vraag om herhaling.""",
        "display_order": 2,
        "is_active": True,
    },

    # ── Gespreksflow ──────────────────────────────────────────
    {
        "key": "steps_greeting",
        "name": "Begroeting",
        "category": "steps",
        "description": "Hoe de AI het gesprek opent. Variabelen: {greeting}",
        "content": """{greeting}""",
        "display_order": 10,
        "is_active": True,
    },
    {
        "key": "steps_conversation",
        "name": "Gesprek",
        "category": "steps",
        "description": "Regels voor het voeren en afsluiten van het gesprek",
        "content": """Bevestig kort dat je het begrijpt. Bij onduidelijkheid: vraag door.
Eén ding tegelijk. Na je antwoord: stop en wacht op reactie.
Afsluiting: vat kort samen als er acties zijn. "Is er verder nog iets?" → "Top, fijne dag!\"""",
        "display_order": 11,
        "is_active": True,
    },

    # ── Veiligheid & Compliance ───────────────────────────────
    {
        "key": "safety_all",
        "name": "Veiligheid & Privacy",
        "category": "safety",
        "description": "Veiligheid, privacy, AI-disclosure — alles in één",
        "content": """Bij boosheid: begrip tonen, excuses, helpen. Escaleer als het niet lukt.
Buiten je bevoegdheden: notitie maken, collega laten terugbellen.
Herhaal nooit persoonlijke gegevens (BSN, creditcard). Geen medisch/juridisch/financieel advies.
Als de klant vraagt of je een AI bent: wees eerlijk, bied aan door te verbinden met een mens.
Deel nooit klantgegevens met derden.""",
        "display_order": 20,
        "is_active": True,
    },
]
