"""
klantenservice.ai - System Prompt Schemas
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID


class SystemPromptBase(BaseModel):
    """Base schema for system prompts."""
    key: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: str = Field(default="general", max_length=100)
    content: str = Field(..., min_length=1)
    is_active: bool = True
    display_order: int = 0


class SystemPromptCreate(SystemPromptBase):
    """Schema for creating a system prompt."""
    pass


class SystemPromptUpdate(BaseModel):
    """Schema for updating a system prompt."""
    key: Optional[str] = Field(None, min_length=1, max_length=100)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    content: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class SystemPromptResponse(SystemPromptBase):
    """Schema for system prompt response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    updated_by_id: Optional[UUID] = None
    updated_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class SystemPromptListResponse(BaseModel):
    """Response schema for list of system prompts."""
    prompts: List[SystemPromptResponse]
    total: int


class SystemPromptPreview(BaseModel):
    """Preview of the combined system prompt."""
    combined_prompt: str
    active_prompts: int
    categories: List[str]
