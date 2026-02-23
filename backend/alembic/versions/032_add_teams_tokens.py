"""add teams token columns to calendar_integrations

Revision ID: 032
Revises: 031
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = "032_teams_tokens"
down_revision = "031_zoom_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("calendar_integrations", sa.Column("teams_access_token_encrypted", sa.Text(), nullable=True))
    op.add_column("calendar_integrations", sa.Column("teams_refresh_token_encrypted", sa.Text(), nullable=True))
    op.add_column("calendar_integrations", sa.Column("teams_token_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("calendar_integrations", "teams_token_expires_at")
    op.drop_column("calendar_integrations", "teams_refresh_token_encrypted")
    op.drop_column("calendar_integrations", "teams_access_token_encrypted")
