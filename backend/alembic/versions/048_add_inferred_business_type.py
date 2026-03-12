"""Add inferred business type columns to companies

Revision ID: 048
Revises: 047
"""
from alembic import op
import sqlalchemy as sa

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("inferred_business_type", sa.String(50), nullable=True))
    op.add_column("companies", sa.Column("inferred_business_confidence", sa.Float, nullable=True))
    op.add_column("companies", sa.Column("inferred_topics", sa.JSON, nullable=True))
    op.add_column("companies", sa.Column("business_type_override", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "business_type_override")
    op.drop_column("companies", "inferred_topics")
    op.drop_column("companies", "inferred_business_confidence")
    op.drop_column("companies", "inferred_business_type")
