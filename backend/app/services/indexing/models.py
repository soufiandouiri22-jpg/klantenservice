"""
klantenservice.ai - Indexing & Retrieval Database Models

New tables for the rebuilt indexing pipeline.
Prefix: idx_ for indexing, rtv_ for retrieval.
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, Text, Float,
    ForeignKey, Enum as SQLEnum, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SiteStatus(str, Enum):
    pending = "pending"
    crawling = "crawling"
    processing = "processing"
    ready = "ready"
    failed = "failed"
    outdated = "outdated"


class CrawlJobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class PageType(str, Enum):
    home = "home"
    pricing = "pricing"
    faq = "faq"
    contact = "contact"
    about = "about"
    service = "service"
    product = "product"
    policy = "policy"
    blog = "blog"
    location = "location"
    unknown = "unknown"


class ChunkType(str, Enum):
    faq = "faq"
    pricing = "pricing"
    contact = "contact"
    location = "location"
    product = "product"
    service = "service"
    policy = "policy"
    blog = "blog"
    general = "general"


# ---------------------------------------------------------------------------
# idx_sites – replaces website_knowledge
# ---------------------------------------------------------------------------

class IdxSite(Base):
    __tablename__ = "idx_sites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    ai_worker_id = Column(UUID(as_uuid=True), ForeignKey("ai_workers.id"), nullable=True)
    base_url = Column(Text, nullable=False)
    sitemap_url = Column(Text, nullable=True)
    crawl_config = Column(JSON, default=lambda: {
        "max_pages": 100,
        "max_depth": 3,
        "blocked_paths": ["/admin", "/login", "/wp-admin"],
        "provider": "http",
    })
    status = Column(
        SQLEnum(SiteStatus, values_callable=lambda x: [e.value for e in x]),
        default=SiteStatus.pending, nullable=False,
    )
    stats = Column(JSON, default=dict)
    last_crawled_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = relationship("Company", backref="idx_sites")
    ai_worker = relationship("AIWorker", backref="idx_sites")
    crawl_jobs = relationship("IdxCrawlJob", back_populates="site", cascade="all, delete-orphan")
    pages = relationship("IdxPage", back_populates="site", cascade="all, delete-orphan")
    chunks = relationship("IdxChunk", back_populates="site", cascade="all, delete-orphan")
    errors = relationship("IdxError", back_populates="site", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<IdxSite {self.base_url}>"


# ---------------------------------------------------------------------------
# idx_crawl_jobs – tracks each crawl run
# ---------------------------------------------------------------------------

class IdxCrawlJob(Base):
    __tablename__ = "idx_crawl_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    status = Column(
        SQLEnum(CrawlJobStatus, values_callable=lambda x: [e.value for e in x]),
        default=CrawlJobStatus.queued, nullable=False,
    )
    provider = Column(String(50), default="http")
    config = Column(JSON, default=dict)
    stats = Column(JSON, default=lambda: {
        "urls_discovered": 0,
        "pages_fetched": 0,
        "pages_failed": 0,
        "pages_skipped": 0,
    })
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    site = relationship("IdxSite", back_populates="crawl_jobs")
    pages = relationship("IdxPage", back_populates="crawl_job", cascade="all, delete-orphan")
    errors = relationship("IdxError", back_populates="crawl_job")

    def __repr__(self):
        return f"<IdxCrawlJob {self.id} status={self.status}>"


# ---------------------------------------------------------------------------
# idx_pages – individual crawled pages with rich metadata
# ---------------------------------------------------------------------------

class IdxPage(Base):
    __tablename__ = "idx_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey("idx_crawl_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)

    url = Column(Text, nullable=False)
    normalized_url = Column(Text, nullable=False, index=True)
    final_url = Column(Text, nullable=True)
    title = Column(Text, nullable=True)
    meta_description = Column(Text, nullable=True)
    h1 = Column(Text, nullable=True)
    raw_html = Column(Text, nullable=True)
    cleaned_content = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    content_type = Column(String(100), nullable=True)
    language = Column(String(20), nullable=True)
    page_type = Column(
        SQLEnum(PageType, values_callable=lambda x: [e.value for e in x]),
        default=PageType.unknown, nullable=False,
    )
    content_hash = Column(String(64), nullable=True)
    discovered_from_url = Column(Text, nullable=True)
    crawled_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("IdxSite", back_populates="pages")
    crawl_job = relationship("IdxCrawlJob", back_populates="pages")
    chunks = relationship("IdxChunk", back_populates="page", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<IdxPage {self.url[:60]}>"


# ---------------------------------------------------------------------------
# idx_chunks – semantic chunks with embeddings and rich metadata
# ---------------------------------------------------------------------------

class IdxChunk(Base):
    __tablename__ = "idx_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id = Column(UUID(as_uuid=True), ForeignKey("idx_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)

    url = Column(Text, nullable=True)
    page_title = Column(Text, nullable=True)
    page_type = Column(String(30), nullable=True)
    chunk_type = Column(
        SQLEnum(ChunkType, values_callable=lambda x: [e.value for e in x]),
        default=ChunkType.general, nullable=False,
    )
    section_path = Column(Text, nullable=True)
    heading_hierarchy = Column(JSON, default=list)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)
    position_on_page = Column(Integer, default=0)
    content_hash = Column(String(64), nullable=False)

    # Embedding (OpenAI text-embedding-3-small = 1536 dims)
    embedding = Column(Vector(1536), nullable=True)
    embedding_model = Column(String(50), nullable=True)
    embedding_version = Column(String(20), nullable=True)

    # Flexible extra metadata (faq_question, price, phone, email, ...)
    extra_meta = Column("metadata", JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    page = relationship("IdxPage", back_populates="chunks")
    site = relationship("IdxSite", back_populates="chunks")

    def __repr__(self):
        return f"<IdxChunk {self.chunk_type} pos={self.position_on_page}>"


# ---------------------------------------------------------------------------
# idx_errors – error log per phase
# ---------------------------------------------------------------------------

class IdxError(Base):
    __tablename__ = "idx_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id = Column(UUID(as_uuid=True), ForeignKey("idx_sites.id", ondelete="CASCADE"), nullable=False, index=True)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey("idx_crawl_jobs.id", ondelete="SET NULL"), nullable=True)
    phase = Column(String(30), nullable=False)  # crawl, clean, chunk, embed
    url = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    site = relationship("IdxSite", back_populates="errors")
    crawl_job = relationship("IdxCrawlJob", back_populates="errors")

    def __repr__(self):
        return f"<IdxError {self.phase}: {self.error_type}>"


# ---------------------------------------------------------------------------
# rtv_events – retrieval debug log (one per search query)
# ---------------------------------------------------------------------------

class RtvEvent(Base):
    __tablename__ = "rtv_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    query_classification = Column(String(30), nullable=True)
    retrieval_strategy = Column(JSON, default=dict)
    filters_applied = Column(JSON, default=dict)
    candidates_found = Column(Integer, default=0)
    reranked = Column(Boolean, default=False)
    top_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    chunks_returned = Column(Integer, default=0)
    context_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    results = relationship("RtvResult", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RtvEvent q='{self.query[:40]}' conf={self.confidence}>"


# ---------------------------------------------------------------------------
# rtv_results – individual retrieved chunks per event
# ---------------------------------------------------------------------------

class RtvResult(Base):
    __tablename__ = "rtv_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("rtv_events.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("idx_chunks.id", ondelete="SET NULL"), nullable=True)
    rank = Column(Integer, nullable=False)
    vector_score = Column(Float, nullable=True)
    rerank_score = Column(Float, nullable=True)
    metadata_boost = Column(Float, default=0.0)
    final_score = Column(Float, nullable=True)
    included_in_context = Column(Boolean, default=False)

    # Relationships
    event = relationship("RtvEvent", back_populates="results")

    def __repr__(self):
        return f"<RtvResult rank={self.rank} score={self.final_score}>"
