"""
klantenservice.ai - CRM Integration Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.crm_integration import CRMProvider


class CRMIntegrationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider: CRMProvider


class CRMIntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    sync_contacts_on_call: Optional[bool] = None
    write_call_notes: Optional[bool] = None
    auto_create_contacts: Optional[bool] = None
    is_active: Optional[bool] = None


class CRMIntegrationResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    provider: CRMProvider
    hubspot_portal_id: Optional[str] = None
    sync_contacts_on_call: bool
    write_call_notes: bool
    auto_create_contacts: bool
    last_sync_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    is_active: bool
    is_connected: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CRMContactResponse(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    notes: List[str] = []
    last_contact: Optional[str] = None
