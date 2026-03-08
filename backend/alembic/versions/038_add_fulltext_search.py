"""Add full-text search (tsvector) for hybrid BM25+vector search

Revision ID: 038
Revises: 037
Create Date: 2026-03-08

"""
from alembic import op

revision = "038_hybrid_search"
down_revision = "037_smart_intake_prompt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add generated tsvector column for full-text search (Dutch + English content)
    op.execute("""
        ALTER TABLE knowledge_chunks
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED
    """)
    op.execute("""
        CREATE INDEX idx_knowledge_chunks_content_tsv
        ON knowledge_chunks USING GIN(content_tsv)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_knowledge_chunks_content_tsv")
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS content_tsv")
