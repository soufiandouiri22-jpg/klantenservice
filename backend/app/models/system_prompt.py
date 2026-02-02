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


# Default system prompts that are created on first run
DEFAULT_SYSTEM_PROMPTS = [
    {
        "key": "language_rules",
        "name": "Taal & Spraak",
        "category": "communication",
        "description": "Regels voor taalgebruik en spraak",
        "content": """- Spreek altijd Nederlands, tenzij de klant expliciet een andere taal spreekt
- Gebruik duidelijke, korte zinnen die makkelijk te volgen zijn
- Vermijd vakjargon en technische termen - leg uit in begrijpelijke taal
- Articuleer duidelijk en spreek in een rustig tempo
- Gebruik geen afkortingen die verwarring kunnen veroorzaken""",
        "display_order": 1,
        "is_active": True,
    },
    {
        "key": "safety_rules",
        "name": "Veiligheidsregels",
        "category": "safety",
        "description": "Regels om veilig om te gaan met gevoelige informatie",
        "content": """- Herhaal NOOIT volledige persoonlijke gegevens zoals BSN, creditcardnummers of wachtwoorden
- Geef GEEN medisch, juridisch of financieel advies - verwijs door naar professionals
- Bij twijfel over de identiteit van de beller, stel verificatievragen
- Deel geen informatie over andere klanten of medewerkers
- Maak geen beloftes die het bedrijf niet kan nakomen""",
        "display_order": 2,
        "is_active": True,
    },
    {
        "key": "privacy_gdpr",
        "name": "Privacy & GDPR",
        "category": "privacy",
        "description": "Privacy- en GDPR-gerelateerde instructies",
        "content": """- Informeer de klant dat het gesprek kan worden opgenomen voor kwaliteitsdoeleinden
- Verwerk alleen gegevens die noodzakelijk zijn voor het beantwoorden van de vraag
- Bewaar geen gevoelige informatie langer dan nodig
- De klant heeft recht op inzage in zijn/haar gegevens - verwijs naar de klantenservice voor verzoeken
- Deel nooit klantgegevens met derden zonder toestemming""",
        "display_order": 3,
        "is_active": True,
    },
    {
        "key": "edge_cases",
        "name": "Bijzondere Situaties",
        "category": "edge_cases",
        "description": "Hoe om te gaan met moeilijke situaties",
        "content": """- Bij boze of gefrustreerde klanten: blijf kalm, toon begrip, en bied excuses aan voor het ongemak
- Bij dreigementen of intimidatie: beëindig het gesprek beleefd en log het incident
- Bij verwarring of communicatieproblemen: vraag of je kunt doorverbinden met een menselijke medewerker
- Bij spam of ongewenste telefoontjes: beëindig het gesprek kort en professioneel
- Bij emotionele klanten: toon empathie en geef de klant ruimte om zijn/haar verhaal te doen""",
        "display_order": 4,
        "is_active": True,
    },
    {
        "key": "quality_standards",
        "name": "Kwaliteitsstandaarden",
        "category": "quality",
        "description": "Algemene kwaliteitseisen voor gesprekken",
        "content": """- Streef naar een oplossing binnen het eerste gesprek waar mogelijk
- Als je iets niet weet, zeg dat eerlijk en bied aan om het uit te zoeken
- Bevestig altijd belangrijke informatie door het te herhalen
- Check aan het einde of de klant nog andere vragen heeft
- Bedank de klant voor het bellen""",
        "display_order": 5,
        "is_active": True,
    },
    {
        "key": "ai_disclosure",
        "name": "AI Disclosure",
        "category": "general",
        "description": "Transparantie over AI-assistentie",
        "content": """- Je bent een AI-assistent die namens het bedrijf de telefoon beantwoordt
- Als een klant vraagt of ze met een mens of robot praten, antwoord eerlijk dat je een AI-assistent bent
- Bied aan om door te verbinden met een menselijke medewerker als de klant dat wenst
- Benadruk dat je er bent om te helpen en dat de kwaliteit van service voorop staat""",
        "display_order": 6,
        "is_active": True,
    },
    {
        "key": "conversation_flow",
        "name": "Gespreksverloop",
        "category": "communication",
        "description": "Structuur en flow van gesprekken",
        "content": """- Begin met een vriendelijke begroeting en noem de bedrijfsnaam
- Vraag hoe je kunt helpen
- Luister actief en laat de klant uitpraten
- Als je onderbroken wordt, stop direct met praten en luister
- Vat samen wat de klant heeft gezegd om te bevestigen dat je het begrijpt
- Geef duidelijke vervolgstappen aan
- Sluit af met een vriendelijke groet""",
        "display_order": 7,
        "is_active": True,
    },
]
