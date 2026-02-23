"""Create crm_integrations table

Revision ID: 028_crm_integrations
Revises: 027_date_no_confirm
Create Date: 2026-02-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "028_crm_integrations"
down_revision = "027_date_no_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_integrations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("access_token_encrypted", sa.Text, nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime, nullable=True),
        sa.Column("hubspot_portal_id", sa.String(50), nullable=True),
        sa.Column("sync_contacts_on_call", sa.Boolean, default=True),
        sa.Column("write_call_notes", sa.Boolean, default=True),
        sa.Column("auto_create_contacts", sa.Boolean, default=False),
        sa.Column("last_sync_at", sa.DateTime, nullable=True),
        sa.Column("sync_error", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_crm_integrations_company_id", "crm_integrations", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_crm_integrations_company_id")
    op.drop_table("crm_integrations")
