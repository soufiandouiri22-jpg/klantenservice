"""Add reliability & guardrail columns to voice_sessions and policy_decisions

Revision ID: 045
Revises: 044
"""
from alembic import op
import sqlalchemy as sa

revision = "045"
down_revision = "044_voice_policy"
branch_labels = None
depends_on = None


def upgrade():
    # voice_sessions — new counters
    op.add_column("voice_sessions", sa.Column("frustration_count", sa.Integer(), server_default="0"))
    op.add_column("voice_sessions", sa.Column("off_topic_block_count", sa.Integer(), server_default="0"))
    op.add_column("voice_sessions", sa.Column("output_guardrail_block_count", sa.Integer(), server_default="0"))
    op.add_column("voice_sessions", sa.Column("language_violation_count", sa.Integer(), server_default="0"))
    op.add_column("voice_sessions", sa.Column("retrieval_skip_count", sa.Integer(), server_default="0"))
    op.add_column("voice_sessions", sa.Column("last_retrieval_score", sa.Float(), nullable=True))

    # policy_decisions — retrieval & guardrail metadata
    op.add_column("policy_decisions", sa.Column("retrieval_confidence", sa.Float(), nullable=True))
    op.add_column("policy_decisions", sa.Column("retrieval_used", sa.Boolean(), nullable=True))
    op.add_column("policy_decisions", sa.Column("guardrail_passed", sa.Boolean(), nullable=True))
    op.add_column("policy_decisions", sa.Column("guardrail_violations", sa.Text(), nullable=True))
    op.add_column("policy_decisions", sa.Column("guardrail_safe_text", sa.Text(), nullable=True))
    op.add_column("policy_decisions", sa.Column("guardrail_original_text", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("policy_decisions", "guardrail_original_text")
    op.drop_column("policy_decisions", "guardrail_safe_text")
    op.drop_column("policy_decisions", "guardrail_violations")
    op.drop_column("policy_decisions", "guardrail_passed")
    op.drop_column("policy_decisions", "retrieval_used")
    op.drop_column("policy_decisions", "retrieval_confidence")
    op.drop_column("voice_sessions", "last_retrieval_score")
    op.drop_column("voice_sessions", "retrieval_skip_count")
    op.drop_column("voice_sessions", "language_violation_count")
    op.drop_column("voice_sessions", "output_guardrail_block_count")
    op.drop_column("voice_sessions", "off_topic_block_count")
    op.drop_column("voice_sessions", "frustration_count")
