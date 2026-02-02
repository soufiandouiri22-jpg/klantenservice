"""
klantenservice.ai - Website Knowledge (RAG) Models
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.core.database import Base


class IndexStatus(str, Enum):
    pending = "pending"       # Not yet indexed
    indexing = "indexing"     # Currently being indexed
    completed = "completed"   # Successfully indexed
    failed = "failed"         # Indexing failed
    outdated = "outdated"     # Needs re-indexing


class WebsiteKnowledge(Base):
    """
    Website Knowledge model - represents a website that has been indexed.
    The AI uses this knowledge base to answer questions about the business.
    """
    __tablename__ = "website_knowledge"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    
    # Website details
    base_url = Column(String(500), nullable=False)
    sitemap_url = Column(String(500), nullable=True)
    
    # Crawl settings
    crawl_settings = Column(JSON, default=lambda: {
        "max_pages": 100,
        "max_depth": 3,
        "respect_robots_txt": True,
        "follow_external_links": False,
        "allowed_paths": [],  # Empty = all paths
        "blocked_paths": ["/admin", "/login", "/wp-admin"],
        "user_agent": "klantenservice-ai-bot/1.0",
    })
    
    # Index status
    status = Column(SQLEnum(IndexStatus, values_callable=lambda x: [e.value for e in x]), default=IndexStatus.pending)
    pages_indexed = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    failed_urls = Column(JSON, default=list)
    
    # Auto-update settings
    auto_update_enabled = Column(Boolean, default=True)
    update_frequency_hours = Column(Integer, default=24)  # Check for updates every 24 hours
    webhook_secret = Column(String(64), nullable=True)  # For webhook-triggered updates
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_indexed_at = Column(DateTime, nullable=True)
    next_index_at = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    company = relationship("Company", back_populates="website_knowledge")
    chunks = relationship("KnowledgeChunk", back_populates="website", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<WebsiteKnowledge {self.base_url}>"


class KnowledgeChunk(Base):
    """
    Knowledge Chunk model - represents a chunk of indexed content.
    Chunks are used for RAG (Retrieval Augmented Generation).
    """
    __tablename__ = "knowledge_chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    website_id = Column(UUID(as_uuid=True), ForeignKey("website_knowledge.id"), nullable=False)
    
    # Source page
    source_url = Column(String(500), nullable=False)
    page_title = Column(String(500), nullable=True)
    
    # Content
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)  # For detecting changes
    
    # Chunk metadata
    chunk_metadata = Column(JSON, default=dict)  # e.g., {"section": "FAQ", "category": "Prijzen"}
    
    # Vector embedding (stored directly in PostgreSQL with pgvector)
    embedding = Column(Vector(384), nullable=True)  # 384 dimensions for all-MiniLM-L6-v2
    
    # Legacy field for ChromaDB reference (deprecated, kept for migration)
    vector_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    website = relationship("WebsiteKnowledge", back_populates="chunks")
    
    def __repr__(self):
        return f"<KnowledgeChunk {self.source_url[:50]}...>"
