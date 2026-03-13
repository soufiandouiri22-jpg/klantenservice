"""Create call evaluations table

Revision ID: 054
Revises: 053
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_evaluations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("call_log_id", UUID(as_uuid=True), sa.ForeignKey("call_logs.id"), nullable=False, unique=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("hallucination_detected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("wrong_tool_detected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("customer_helped", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("needs_review", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("issues", JSON(), server_default="[]"),
        sa.Column("tool_usage", JSON(), server_default="[]"),
        sa.Column("langsmith_run_id", sa.String(100), nullable=True),
        sa.Column("evaluator_model", sa.String(50), server_default="gpt-4o-mini"),
        sa.Column("evaluated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_call_evaluations_company_id", "call_evaluations", ["company_id"])
    op.create_index("ix_call_evaluations_evaluated_at", "call_evaluations", ["evaluated_at"])
    op.create_index("ix_call_evaluations_needs_review", "call_evaluations", ["needs_review"])


def downgrade() -> None:
    op.drop_index("ix_call_evaluations_needs_review")
    op.drop_index("ix_call_evaluations_evaluated_at")
    op.drop_index("ix_call_evaluations_company_id")
    op.drop_table("call_evaluations")
