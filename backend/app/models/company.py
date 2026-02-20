"""
klantenservice.ai - Company (Tenant) Model
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class SubscriptionPlan(str, Enum):
    starter = "starter"      # 1 AI-medewerker
    business = "business"    # 5 AI-medewerkers
    enterprise = "enterprise"  # 7 AI-medewerkers


class Company(Base):
    """
    Company model - represents a tenant in the multi-tenant system.
    Each company has their own AI workers, phone numbers, and settings.
    """
    __tablename__ = "companies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic info
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    
    # Address
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    postal_code = Column(String(10), nullable=True)
    country = Column(String(50), default="Nederland")
    
    # KvK (Dutch Chamber of Commerce)
    kvk_number = Column(String(20), nullable=True)
    btw_number = Column(String(20), nullable=True)
    
    # Subscription
    subscription_plan = Column(
        SQLEnum(SubscriptionPlan),
        default=SubscriptionPlan.starter,
        nullable=False
    )
    subscription_status = Column(String(20), default="active")  # active, paused, cancelled
    subscription_started_at = Column(DateTime, nullable=True)
    subscription_ends_at = Column(DateTime, nullable=True)
    
    # Stripe
    stripe_customer_id = Column(String(255), nullable=True, unique=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    
    # Trial tracking - once True, company cannot start another trial
    trial_used = Column(Boolean, default=False)
    
    # AI Worker limits based on plan
    max_ai_workers = Column(Integer, default=1)
    
    # Settings
    disclosure_message = Column(
        Text,
        default="{greeting}, met {ai_worker_name} van {company_name}, waarmee kan ik u helpen?"
    )
    default_language = Column(String(10), default="nl-NL")
    timezone = Column(String(50), default="Europe/Amsterdam")
    
    # Privacy & Compliance
    data_retention_days = Column(Integer, default=90)
    call_recording_enabled = Column(Boolean, default=False)
    call_recording_consent_required = Column(Boolean, default=True)
    # Registration consents (set at signup)
    terms_accepted_at = Column(DateTime, nullable=True)  # When user agreed to terms & privacy
    marketing_consent = Column(Boolean, default=False)  # Opt-in for email marketing
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Admin Controls (platform admin only)
    is_kill_switched = Column(Boolean, default=False)  # Stop all calls immediately
    feature_flags = Column(JSON, default=dict)  # Feature toggles per company
    
    # Hidden Admin Overrides (only visible to platform admin)
    # Contains: force_language, force_u_form, orchestrator_model_override,
    # rag_threshold_override, audio_segment_ms_override, max_calls_per_minute,
    # disable_auto_booking, etc.
    admin_overrides = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    ai_workers = relationship("AIWorker", back_populates="company", cascade="all, delete-orphan")
    phone_numbers = relationship("PhoneNumber", back_populates="company", cascade="all, delete-orphan")
    calendar_integrations = relationship("CalendarIntegration", back_populates="company", cascade="all, delete-orphan")
    website_knowledge = relationship("WebsiteKnowledge", back_populates="company", cascade="all, delete-orphan")
    training_rules = relationship("TrainingRule", back_populates="company", cascade="all, delete-orphan")
    example_answers = relationship("ExampleAnswer", back_populates="company", cascade="all, delete-orphan")
    call_logs = relationship("CallLog", back_populates="company", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="company", cascade="all, delete-orphan")
    internal_notes = relationship("InternalNote", back_populates="company", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Company {self.name}>"
    
    @property
    def ai_worker_limit(self) -> int:
        """Get the AI worker limit based on subscription plan."""
        limits = {
            SubscriptionPlan.starter: 1,
            SubscriptionPlan.business: 5,
            SubscriptionPlan.enterprise: 7,
        }
        return limits.get(self.subscription_plan, 1)
