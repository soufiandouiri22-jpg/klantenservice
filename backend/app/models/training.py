"""
klantenservice.ai - Training Rules & Example Answers Models
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class TrainingRule(Base):
    """
    Training Rule model - represents behavior rules for AI workers.
    These are toggleable settings that affect how the AI responds.
    """
    __tablename__ = "training_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    
    # Rule definition
    rule_key = Column(String(100), nullable=False)  # e.g., "use_formal_address"
    rule_name = Column(String(255), nullable=False)  # e.g., "Gebruik u-vorm"
    rule_description = Column(Text, nullable=True)
    
    # Rule value
    is_enabled = Column(Boolean, default=True)
    
    # Ordering
    display_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="training_rules")
    
    def __repr__(self):
        return f"<TrainingRule {self.rule_key}>"


class ExampleAnswer(Base):
    """
    Example Answer model - Q&A pairs that train the AI how to respond.
    "Als de klant X vraagt, antwoord dan Y"
    """
    __tablename__ = "example_answers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    
    # Question/trigger
    question = Column(Text, nullable=False)  # e.g., "Wat zijn jullie openingstijden?"
    question_variations = Column(JSON, default=list)  # Alternative phrasings
    
    # Answer
    answer = Column(Text, nullable=False)
    
    # Categorization
    category = Column(String(100), nullable=True)  # e.g., "Openingstijden", "Prijzen"
    tags = Column(JSON, default=list)
    
    # Source (how was this Q&A created?)
    source = Column(String(50), default="manual")  # manual, detected, imported
    detected_count = Column(Integer, default=0)  # How often was this question asked
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=True)  # Verified by admin
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationships
    company = relationship("Company", back_populates="example_answers")
    
    def __repr__(self):
        return f"<ExampleAnswer {self.question[:50]}...>"


# Default training rules that every company gets
DEFAULT_TRAINING_RULES = [
    {
        "rule_key": "use_formal_address",
        "rule_name": "Gebruik u-vorm",
        "rule_description": "Spreek de klant aan met 'u' in plaats van 'jij'.",
        "is_enabled": True,
        "display_order": 1,
    },
    {
        "rule_key": "apologize_on_complaints",
        "rule_name": "Excuses bij klachten",
        "rule_description": "Bied excuses aan wanneer een klant een klacht heeft.",
        "is_enabled": True,
        "display_order": 2,
    },
    {
        "rule_key": "offer_alternatives",
        "rule_name": "Altijd alternatieven aanbieden",
        "rule_description": "Bied altijd een alternatief aan als iets niet mogelijk is.",
        "is_enabled": True,
        "display_order": 3,
    },
    {
        "rule_key": "never_guess",
        "rule_name": "Nooit gokken",
        "rule_description": "Geef nooit informatie waar je niet zeker van bent. Verwijs door indien nodig.",
        "is_enabled": True,
        "display_order": 4,
    },
    {
        "rule_key": "confirm_appointments",
        "rule_name": "Afspraken bevestigen",
        "rule_description": "Herhaal altijd de datum en tijd van een afspraak ter bevestiging.",
        "is_enabled": True,
        "display_order": 5,
    },
    {
        "rule_key": "summarize_at_end",
        "rule_name": "Samenvatten aan einde",
        "rule_description": "Vat aan het einde van het gesprek kort samen wat er is besproken.",
        "is_enabled": True,
        "display_order": 6,
    },
    {
        "rule_key": "collect_callback_number",
        "rule_name": "Terugbelnummer vragen",
        "rule_description": "Vraag om een terugbelnummer als de vraag niet direct beantwoord kan worden.",
        "is_enabled": True,
        "display_order": 7,
    },
]
