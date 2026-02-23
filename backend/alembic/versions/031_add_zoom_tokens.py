"""add zoom token columns to calendar_integrations

Revision ID: 031
Revises: 030
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = "031_zoom_tokens"
down_revision = "030_meeting_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("calendar_integrations", sa.Column("zoom_access_token_encrypted", sa.Text(), nullable=True))
    op.add_column("calendar_integrations", sa.Column("zoom_refresh_token_encrypted", sa.Text(), nullable=True))
    op.add_column("calendar_integrations", sa.Column("zoom_token_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("calendar_integrations", "zoom_token_expires_at")
    op.drop_column("calendar_integrations", "zoom_refresh_token_encrypted")
    op.drop_column("calendar_integrations", "zoom_access_token_encrypted")
