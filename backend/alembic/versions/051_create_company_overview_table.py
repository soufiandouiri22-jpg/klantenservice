"""create company overview table

Revision ID: 051
Revises: 050
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_company_overviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", UUID(as_uuid=True), sa.ForeignKey("idx_sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("target_audience", sa.Text, nullable=True),
        sa.Column("capabilities", sa.JSON, nullable=True),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_overview_company", "business_company_overviews", ["company_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_overview_company")
    op.drop_table("business_company_overviews")
