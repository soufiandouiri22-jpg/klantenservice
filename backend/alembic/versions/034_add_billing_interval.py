"""add billing_interval column to companies

Revision ID: 034_billing_interval
Revises: 033_gmeet_tokens
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

revision = "034_billing_interval"
down_revision = "033_gmeet_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    billing_interval_enum = sa.Enum("monthly", "yearly", name="billinginterval")
    billing_interval_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "companies",
        sa.Column(
            "billing_interval",
            billing_interval_enum,
            nullable=False,
            server_default="monthly",
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "billing_interval")
    sa.Enum(name="billinginterval").drop(op.get_bind(), checkfirst=True)
