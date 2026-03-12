"""
klantenservice.ai - Structured Business Facts Models

Deterministic business data extracted during indexing.
Queried at runtime *before* RAG for pricing, contact, hours, etc.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, Float,
    ForeignKey, JSON, Numeric, Time,
)
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class PricingPlan(Base):
    __tablename__ = "business_pricing_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(100), nullable=False)
    price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="EUR")
    billing_period = Column(String(20), nullable=True)
    price_type = Column(String(20), nullable=False, default="fixed")
    description = Column(Text, nullable=True)
    features = Column(JSON, nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContactInfo(Base):
    __tablename__ = "business_contact_info"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="SET NULL"), nullable=True)
    label = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(255), nullable=True)
    whatsapp = Column(String(30), nullable=True)
    contact_url = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OpeningHours(Base):
    __tablename__ = "business_opening_hours"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="SET NULL"), nullable=True)
    weekday = Column(Integer, nullable=False)
    open_time = Column(Time, nullable=True)
    close_time = Column(Time, nullable=True)
    closed = Column(Boolean, nullable=False, default=False)
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BusinessLocation(Base):
    __tablename__ = "business_locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    postal_code = Column(String(10), nullable=True)
    country = Column(String(50), nullable=False, default="Nederland")
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BusinessService(Base):
    __tablename__ = "business_services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    price = Column(Numeric(10, 2), nullable=True)
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
