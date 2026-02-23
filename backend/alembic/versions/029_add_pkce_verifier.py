"""Add pkce_code_verifier column to crm_integrations

Revision ID: 029_add_pkce_verifier
Revises: 028_crm_integrations
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = "029_add_pkce_verifier"
down_revision = "028_crm_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crm_integrations",
        sa.Column("pkce_code_verifier", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crm_integrations", "pkce_code_verifier")
