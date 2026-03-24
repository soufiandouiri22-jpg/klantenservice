"""Add api_context_id column for Saleslane JWT auth

Revision ID: 056
Revises: 055
"""
from alembic import op
import sqlalchemy as sa

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crm_integrations",
        sa.Column("api_context_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crm_integrations", "api_context_id")
