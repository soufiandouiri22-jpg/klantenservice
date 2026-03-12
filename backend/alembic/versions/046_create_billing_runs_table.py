"""Create billing_runs table for idempotent overage billing

Revision ID: 046
Revises: 045
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("stripe_invoice_id", sa.String(255), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("period_start", sa.DateTime, nullable=False),
        sa.Column("period_end", sa.DateTime, nullable=False),
        sa.Column("minutes_included", sa.Integer, nullable=False, server_default="0"),
        sa.Column("minutes_used", sa.Float, nullable=False, server_default="0"),
        sa.Column("overage_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overage_amount_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stripe_invoice_item_id", sa.String(255), nullable=True),
        sa.Column("stripe_idempotency_key", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="calculated"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("stripe_invoice_id", name="uq_billing_runs_stripe_invoice"),
    )


def downgrade() -> None:
    op.drop_table("billing_runs")
