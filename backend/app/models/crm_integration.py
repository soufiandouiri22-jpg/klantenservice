"""
klantenservice.ai - CRM Integration Model
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class CRMProvider(str, Enum):
    HUBSPOT = "hubspot"
    PIPEDRIVE = "pipedrive"
    SALESFORCE = "salesforce"
    SALESDOCK = "salesdock"


class CRMIntegration(Base):
    """
    CRM Integration model - represents a connected CRM system.
    Used to look up callers and write back call notes.
    """
    __tablename__ = "crm_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    name = Column(String(100), nullable=False)
    provider = Column(
        SQLEnum(CRMProvider, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # OAuth tokens (encrypted)
    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    # PKCE (stored between auth URL generation and OAuth callback)
    pkce_code_verifier = Column(Text, nullable=True)

    # Provider-specific IDs
    hubspot_portal_id = Column(String(50), nullable=True)

    # Salesdock-specific fields (API key auth, no OAuth)
    api_key_encrypted = Column(Text, nullable=True)
    account_domain = Column(String(100), nullable=True)

    # Feature toggles
    sync_contacts_on_call = Column(Boolean, default=True)
    write_call_notes = Column(Boolean, default=True)
    auto_create_contacts = Column(Boolean, default=False)

    # Sync status
    last_sync_at = Column(DateTime, nullable=True)
    sync_error = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="crm_integrations")

    def __repr__(self):
        return f"<CRMIntegration {self.name} ({self.provider})>"

    @property
    def is_token_expired(self) -> bool:
        if not self.token_expires_at:
            return True
        return datetime.utcnow() >= self.token_expires_at
