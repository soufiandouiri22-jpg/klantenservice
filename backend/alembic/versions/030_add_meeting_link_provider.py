"""Add meeting_link_provider to calendar_integrations

Revision ID: 030_meeting_link
Revises: 029_add_pkce_verifier
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = "030_meeting_link"
down_revision = "029_add_pkce_verifier"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calendar_integrations",
        sa.Column("meeting_link_provider", sa.String(20), server_default="none"),
    )


def downgrade() -> None:
    op.drop_column("calendar_integrations", "meeting_link_provider")
