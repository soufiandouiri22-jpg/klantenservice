"""add standalone google meet token columns to calendar_integrations

Revision ID: 033_gmeet_tokens
Revises: 032_teams_tokens
Create Date: 2026-02-23
"""
from alembic import op
import sqlalchemy as sa

revision = "033_gmeet_tokens"
down_revision = "032_teams_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("calendar_integrations", sa.Column("gmeet_access_token_encrypted", sa.Text(), nullable=True))
    op.add_column("calendar_integrations", sa.Column("gmeet_refresh_token_encrypted", sa.Text(), nullable=True))
    op.add_column("calendar_integrations", sa.Column("gmeet_token_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("calendar_integrations", "gmeet_token_expires_at")
    op.drop_column("calendar_integrations", "gmeet_refresh_token_encrypted")
    op.drop_column("calendar_integrations", "gmeet_access_token_encrypted")
