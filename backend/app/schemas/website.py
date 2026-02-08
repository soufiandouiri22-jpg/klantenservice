"""
klantenservice.ai - Website Knowledge Schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, HttpUrl
from uuid import UUID

from app.models.website_knowledge import IndexStatus


class CrawlSettings(BaseModel):
    """Website crawl settings."""
    max_pages: int = Field(default=100, ge=1, le=500)
    max_depth: int = Field(default=3, ge=1, le=5)
    respect_robots_txt: bool = True
    follow_external_links: bool = False
    allowed_paths: List[str] = []
    blocked_paths: List[str] = ["/admin", "/login", "/wp-admin"]


class WebsiteKnowledgeBase(BaseModel):
    base_url: HttpUrl


class WebsiteKnowledgeCreate(WebsiteKnowledgeBase):
    """Schema for creating website knowledge."""
    ai_worker_id: Optional[UUID] = None
    sitemap_url: Optional[HttpUrl] = None
    crawl_settings: Optional[CrawlSettings] = None


class WebsiteKnowledgeUpdate(BaseModel):
    """Schema for updating website knowledge."""
    sitemap_url: Optional[HttpUrl] = None
    crawl_settings: Optional[CrawlSettings] = None
    auto_update_enabled: Optional[bool] = None
    update_frequency_hours: Optional[int] = Field(None, ge=1, le=168)  # 1 hour to 1 week
    is_active: Optional[bool] = None


class WebsiteKnowledgeResponse(BaseModel):
    """Schema for website knowledge response."""
    id: UUID
    company_id: UUID
    ai_worker_id: Optional[UUID] = None
    base_url: str
    sitemap_url: Optional[str]
    crawl_settings: Dict[str, Any]
    status: IndexStatus
    pages_indexed: int
    chunks_created: int
    last_error: Optional[str]
    auto_update_enabled: bool
    update_frequency_hours: int
    last_indexed_at: Optional[datetime]
    next_index_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class KnowledgeChunkResponse(BaseModel):
    """Schema for knowledge chunk response."""
    id: UUID
    source_url: str
    page_title: Optional[str]
    content: str
    chunk_metadata: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


class TestQuestionRequest(BaseModel):
    """Request to test a question against the knowledge base."""
    question: str = Field(..., min_length=3, max_length=500)


class TestQuestionResponse(BaseModel):
    """Response for test question."""
    question: str
    answer: str
    sources: List[Dict[str, Any]]  # Source URLs and snippets
    confidence: float


class IndexTriggerResponse(BaseModel):
    """Response when triggering re-indexing."""
    message: str
    status: IndexStatus
    estimated_time_minutes: Optional[int]


class WebhookSetupResponse(BaseModel):
    """Response for webhook setup."""
    webhook_url: str
    webhook_secret: str
