"""
klantenservice.ai - Training Rules & Example Answers Schemas
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from uuid import UUID


class TrainingRuleBase(BaseModel):
    rule_key: str
    rule_name: str
    rule_description: Optional[str] = None


class TrainingRuleUpdate(BaseModel):
    """Schema for updating a training rule."""
    is_enabled: bool


class TrainingRuleResponse(TrainingRuleBase):
    """Schema for training rule response."""
    id: UUID
    company_id: UUID
    is_enabled: bool
    display_order: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ExampleAnswerBase(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    answer: str = Field(..., min_length=1, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)


class ExampleAnswerCreate(ExampleAnswerBase):
    """Schema for creating an example answer."""
    question_variations: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class ExampleAnswerUpdate(BaseModel):
    """Schema for updating an example answer."""
    question: Optional[str] = Field(None, min_length=3, max_length=500)
    question_variations: Optional[List[str]] = None
    answer: Optional[str] = Field(None, min_length=1, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ExampleAnswerResponse(ExampleAnswerBase):
    """Schema for example answer response."""
    id: UUID
    company_id: UUID
    question_variations: List[str]
    tags: List[str]
    source: str
    detected_count: int
    is_active: bool
    is_verified: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DetectedQuestionResponse(BaseModel):
    """Schema for a detected frequently asked question."""
    question: str
    occurrences: int
    suggested_answer: Optional[str]
    similar_existing: Optional[UUID]  # ID of similar existing example answer


class ToneOfVoiceUpdate(BaseModel):
    """Schema for updating tone of voice."""
    description: str = Field(..., min_length=10, max_length=2000)


class BulkExampleAnswerImport(BaseModel):
    """Schema for bulk importing example answers."""
    items: List[ExampleAnswerCreate]


class BulkImportResponse(BaseModel):
    """Response for bulk import."""
    imported: int
    skipped: int
    errors: List[Dict[str, str]]


from typing import Dict
