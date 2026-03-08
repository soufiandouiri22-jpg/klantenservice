"""Add elevenlabs_conversation_id for demo call recordings

Revision ID: 039
Revises: 038
Create Date: 2026-03-09

"""
from alembic import op

revision = "039_elevenlabs_conversation_id"
down_revision = "038_hybrid_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE call_logs
        ADD COLUMN elevenlabs_conversation_id VARCHAR(100) NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE call_logs DROP COLUMN IF EXISTS elevenlabs_conversation_id")
