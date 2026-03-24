"""Add Salesdock CRM fields (api_key_encrypted, account_domain) and extend provider enum

Revision ID: 055
Revises: 054
"""
from alembic import op
import sqlalchemy as sa

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crm_integrations",
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
    )
    op.add_column(
        "crm_integrations",
        sa.Column("account_domain", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crm_integrations", "account_domain")
    op.drop_column("crm_integrations", "api_key_encrypted")
