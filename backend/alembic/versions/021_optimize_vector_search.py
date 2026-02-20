"""Optimize vector search: HNSW index + denormalized company_id on knowledge_chunks

Revision ID: 021_optimize_vector_search
Revises: 020_create_notifications_table
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "021_optimize_vector_search"
down_revision = "020_create_notifications_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add company_id directly on knowledge_chunks to avoid JOIN during search
    op.add_column(
        "knowledge_chunks",
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=True),
    )

    # Back-fill company_id from the parent website_knowledge row
    op.execute("""
        UPDATE knowledge_chunks kc
        SET company_id = wk.company_id
        FROM website_knowledge wk
        WHERE kc.website_id = wk.id
    """)

    # 2. Drop old IVFFlat index (slow for small datasets, requires training)
    op.execute("DROP INDEX IF EXISTS idx_knowledge_chunks_embedding")

    # 3. Create HNSW index (faster recall, no training needed)
    op.execute("""
        CREATE INDEX idx_knowledge_chunks_embedding
        ON knowledge_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # 4. B-tree index on company_id for fast pre-filtering
    op.create_index(
        "ix_knowledge_chunks_company_id",
        "knowledge_chunks",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_company_id")
    op.execute("DROP INDEX IF EXISTS idx_knowledge_chunks_embedding")

    # Recreate original IVFFlat index
    op.execute("""
        CREATE INDEX idx_knowledge_chunks_embedding
        ON knowledge_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    op.drop_column("knowledge_chunks", "company_id")
