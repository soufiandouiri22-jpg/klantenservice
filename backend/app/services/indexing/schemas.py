"""
Pydantic schemas for the indexing pipeline API.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, HttpUrl


# ---------------------------------------------------------------------------
# Site schemas
# ---------------------------------------------------------------------------

class CrawlConfig(BaseModel):
    max_pages: int = 100
    max_depth: int = 3
    blocked_paths: List[str] = ["/admin", "/login", "/wp-admin"]
    provider: str = "http"


class SiteCreate(BaseModel):
    base_url: HttpUrl
    ai_worker_id: Optional[UUID] = None
    sitemap_url: Optional[HttpUrl] = None
    crawl_config: Optional[CrawlConfig] = None


class SiteUpdate(BaseModel):
    base_url: Optional[HttpUrl] = None
    ai_worker_id: Optional[UUID] = None
    sitemap_url: Optional[HttpUrl] = None
    crawl_config: Optional[CrawlConfig] = None
    is_active: Optional[bool] = None


class SiteResponse(BaseModel):
    id: UUID
    company_id: UUID
    ai_worker_id: Optional[UUID] = None
    base_url: str
    sitemap_url: Optional[str] = None
    crawl_config: Dict[str, Any] = {}
    status: str
    stats: Dict[str, Any] = {}
    last_crawled_at: Optional[datetime] = None
    last_error: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Crawl job schemas
# ---------------------------------------------------------------------------

class CrawlJobResponse(BaseModel):
    id: UUID
    site_id: UUID
    status: str
    provider: str
    stats: Dict[str, Any] = {}
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Page schemas
# ---------------------------------------------------------------------------

class PageResponse(BaseModel):
    id: UUID
    url: str
    title: Optional[str] = None
    page_type: str
    status_code: Optional[int] = None
    language: Optional[str] = None
    content_hash: Optional[str] = None
    crawled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Chunk schemas
# ---------------------------------------------------------------------------

class ChunkResponse(BaseModel):
    id: UUID
    url: Optional[str] = None
    page_title: Optional[str] = None
    page_type: Optional[str] = None
    chunk_type: str
    section_path: Optional[str] = None
    content: str
    token_count: Optional[int] = None
    position_on_page: int = 0
    metadata: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Test / search schemas
# ---------------------------------------------------------------------------

class TestQuestionRequest(BaseModel):
    question: str


class TestQuestionResponse(BaseModel):
    question: str
    answer: str
    sources: List[Dict[str, Any]] = []
    confidence: float = 0.0


class IndexTriggerResponse(BaseModel):
    message: str
    status: str
    estimated_time_minutes: int = 5
