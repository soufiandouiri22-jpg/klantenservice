"""
Create notifications table for in-app notifications.

Revision ID: 020_create_notifications_table
Revises: 019_add_pending_email
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "020_create_notifications_table"
down_revision = "019_add_pending_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "detected_question",
                "call_error",
                "note_action",
                "website_indexed",
                "website_failed",
                "appointment_new",
                "appointment_cancelled",
                name="notificationtype",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("is_read", sa.Boolean, default=False),
        sa.Column("read_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    # Index for fast lookups by company + read status
    op.create_index("ix_notifications_company_unread", "notifications", ["company_id", "is_read"])


def downgrade() -> None:
    op.drop_index("ix_notifications_company_unread")
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS notificationtype")
