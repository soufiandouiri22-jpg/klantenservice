"""Fix abandoned call durations and add usage alert fields to companies

Revision ID: 042_usage_alerts
Revises: 041_indexing_pipeline
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "042_usage_alerts"
down_revision = "041_indexing_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add usage alert tracking columns to companies
    op.add_column("companies", sa.Column("usage_warning_sent_at", sa.DateTime(), nullable=True))
    op.add_column("companies", sa.Column("usage_exceeded_sent_at", sa.DateTime(), nullable=True))

    # Reset inflated duration_seconds on all ABANDONED calls to 0
    op.execute("""
        UPDATE call_logs
        SET duration_seconds = 0
        WHERE status = 'abandoned'
          AND duration_seconds > 0
    """)


def downgrade() -> None:
    op.drop_column("companies", "usage_exceeded_sent_at")
    op.drop_column("companies", "usage_warning_sent_at")
