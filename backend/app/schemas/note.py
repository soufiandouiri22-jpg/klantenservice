"""
klantenservice.ai - Internal Note Schemas
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from uuid import UUID

from app.models.internal_note import NotePriority


class InternalNoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    category: Optional[str] = Field(None, max_length=100)
    priority: NotePriority = NotePriority.NORMAL


class InternalNoteCreate(InternalNoteBase):
    """Schema for creating an internal note."""
    tags: Optional[List[str]] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[EmailStr] = None
    action_required: bool = False
    action_description: Optional[str] = None
    action_due_at: Optional[datetime] = None


class InternalNoteUpdate(BaseModel):
    """Schema for updating an internal note."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    priority: Optional[NotePriority] = None
    action_required: Optional[bool] = None
    action_description: Optional[str] = None
    action_due_at: Optional[datetime] = None


class InternalNoteResponse(InternalNoteBase):
    """Schema for internal note response."""
    id: UUID
    company_id: UUID
    call_log_id: Optional[UUID]
    tags: List[str]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    action_required: bool
    action_description: Optional[str]
    action_due_at: Optional[datetime]
    is_resolved: bool
    resolved_at: Optional[datetime]
    resolved_by_user_id: Optional[UUID]
    resolution_notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InternalNoteListResponse(BaseModel):
    """Paginated list of internal notes."""
    items: List[InternalNoteResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class NoteResolveRequest(BaseModel):
    """Request to resolve a note."""
    resolution_notes: Optional[str] = None


class NoteFilterParams(BaseModel):
    """Filter parameters for internal notes."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    priority: Optional[NotePriority] = None
    category: Optional[str] = None
    is_resolved: Optional[bool] = None
    action_required: Optional[bool] = None
    search: Optional[str] = None  # Search in title, content, customer name
