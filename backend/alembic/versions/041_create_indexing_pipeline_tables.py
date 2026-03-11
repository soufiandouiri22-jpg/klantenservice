"""Create new indexing pipeline tables (idx_*, rtv_*)

Revision ID: 041_indexing_pipeline
Revises: 040_polyai_prompts
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "041_indexing_pipeline"
down_revision = "040_polyai_prompts"
branch_labels = None
depends_on = None


def upgrade():
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- idx_sites ---
    op.create_table(
        "idx_sites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("ai_worker_id", UUID(as_uuid=True), sa.ForeignKey("ai_workers.id"), nullable=True),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("sitemap_url", sa.Text, nullable=True),
        sa.Column("crawl_config", sa.JSON, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("stats", sa.JSON, server_default="{}"),
        sa.Column("last_crawled_at", sa.DateTime, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_idx_sites_company_id", "idx_sites", ["company_id"])

    # --- idx_crawl_jobs ---
    op.create_table(
        "idx_crawl_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("idx_sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("provider", sa.String(50), server_default="http"),
        sa.Column("config", sa.JSON, server_default="{}"),
        sa.Column("stats", sa.JSON, server_default="{}"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_idx_crawl_jobs_site_id", "idx_crawl_jobs", ["site_id"])

    # --- idx_pages ---
    op.create_table(
        "idx_pages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("idx_sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crawl_job_id", UUID(as_uuid=True), sa.ForeignKey("idx_crawl_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("normalized_url", sa.Text, nullable=False),
        sa.Column("final_url", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("meta_description", sa.Text, nullable=True),
        sa.Column("h1", sa.Text, nullable=True),
        sa.Column("raw_html", sa.Text, nullable=True),
        sa.Column("cleaned_content", sa.Text, nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("content_type", sa.String(100), nullable=True),
        sa.Column("language", sa.String(20), nullable=True),
        sa.Column("page_type", sa.String(20), server_default="unknown", nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("discovered_from_url", sa.Text, nullable=True),
        sa.Column("crawled_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_idx_pages_site_id", "idx_pages", ["site_id"])
    op.create_index("ix_idx_pages_company_id", "idx_pages", ["company_id"])
    op.create_index("ix_idx_pages_normalized_url", "idx_pages", ["normalized_url"])

    # --- idx_chunks ---
    op.create_table(
        "idx_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("page_id", UUID(as_uuid=True), sa.ForeignKey("idx_pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("idx_sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("page_title", sa.Text, nullable=True),
        sa.Column("page_type", sa.String(30), nullable=True),
        sa.Column("chunk_type", sa.String(20), server_default="general", nullable=False),
        sa.Column("section_path", sa.Text, nullable=True),
        sa.Column("heading_hierarchy", sa.JSON, server_default="[]"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("position_on_page", sa.Integer, server_default="0"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(50), nullable=True),
        sa.Column("embedding_version", sa.String(20), nullable=True),
        sa.Column("metadata", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    # Add pgvector column separately (sa.Column doesn't handle custom types well in create_table)
    op.execute("ALTER TABLE idx_chunks ADD COLUMN embedding vector(1536)")

    op.create_index("ix_idx_chunks_company_id", "idx_chunks", ["company_id"])
    op.create_index("ix_idx_chunks_site_id", "idx_chunks", ["site_id"])
    op.create_index("ix_idx_chunks_page_id", "idx_chunks", ["page_id"])
    op.create_index("ix_idx_chunks_chunk_type", "idx_chunks", ["chunk_type"])
    op.create_index("ix_idx_chunks_company_type", "idx_chunks", ["company_id", "chunk_type"])

    # HNSW index for vector similarity search
    op.execute("""
        CREATE INDEX ix_idx_chunks_embedding
        ON idx_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Full-text search column + GIN index
    op.execute("""
        ALTER TABLE idx_chunks
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED
    """)
    op.execute("CREATE INDEX ix_idx_chunks_content_tsv ON idx_chunks USING gin(content_tsv)")

    # --- idx_errors ---
    op.create_table(
        "idx_errors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("idx_sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("crawl_job_id", UUID(as_uuid=True), sa.ForeignKey("idx_crawl_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("phase", sa.String(30), nullable=False),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_idx_errors_site_id", "idx_errors", ["site_id"])

    # --- rtv_events ---
    op.create_table(
        "rtv_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("query_classification", sa.String(30), nullable=True),
        sa.Column("retrieval_strategy", sa.JSON, server_default="{}"),
        sa.Column("filters_applied", sa.JSON, server_default="{}"),
        sa.Column("candidates_found", sa.Integer, server_default="0"),
        sa.Column("reranked", sa.Boolean, server_default="false"),
        sa.Column("top_score", sa.Float, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("chunks_returned", sa.Integer, server_default="0"),
        sa.Column("context_tokens", sa.Integer, server_default="0"),
        sa.Column("latency_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_rtv_events_company_id", "rtv_events", ["company_id"])
    op.create_index("ix_rtv_events_created_at", "rtv_events", ["created_at"])

    # --- rtv_results ---
    op.create_table(
        "rtv_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", UUID(as_uuid=True), sa.ForeignKey("rtv_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("idx_chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("vector_score", sa.Float, nullable=True),
        sa.Column("rerank_score", sa.Float, nullable=True),
        sa.Column("metadata_boost", sa.Float, server_default="0"),
        sa.Column("final_score", sa.Float, nullable=True),
        sa.Column("included_in_context", sa.Boolean, server_default="false"),
    )
    op.create_index("ix_rtv_results_event_id", "rtv_results", ["event_id"])


def downgrade():
    op.drop_table("rtv_results")
    op.drop_table("rtv_events")
    op.drop_table("idx_errors")
    op.drop_table("idx_chunks")
    op.drop_table("idx_pages")
    op.drop_table("idx_crawl_jobs")
    op.drop_table("idx_sites")
