"""Add voice_sessions and policy_decisions tables + call_logs enrichment

Revision ID: 044_voice_policy
Revises: 043_scope_guardrail
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "044_voice_policy"
down_revision = "043_scope_guardrail"
branch_labels = None
depends_on = None


def upgrade():
    # voice_sessions: per-call conversation state
    op.create_table(
        "voice_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("call_log_id", UUID(as_uuid=True), sa.ForeignKey("call_logs.id"), unique=True),
        sa.Column("call_sid", sa.String(50), unique=True, index=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id")),

        sa.Column("phase", sa.String(30), server_default="greeting"),
        sa.Column("turn_count", sa.Integer, server_default="0"),

        sa.Column("last_customer_intent", sa.String(30), nullable=True),
        sa.Column("last_customer_utterance", sa.Text, nullable=True),

        sa.Column("goodbye_said_by_agent", sa.Boolean, server_default="false"),
        sa.Column("goodbye_said_by_customer", sa.Boolean, server_default="false"),
        sa.Column("escalation_requested", sa.Boolean, server_default="false"),
        sa.Column("transfer_executed", sa.Boolean, server_default="false"),

        sa.Column("low_confidence_count", sa.Integer, server_default="0"),
        sa.Column("repeat_topic_count", sa.Integer, server_default="0"),
        sa.Column("retrieval_count", sa.Integer, server_default="0"),
        sa.Column("end_call_attempts", sa.Integer, server_default="0"),

        sa.Column("goodbye_handshake_ok", sa.Boolean, nullable=True),
        sa.Column("hangup_reason", sa.String(50), nullable=True),
        sa.Column("ended_by", sa.String(20), nullable=True),

        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # policy_decisions: every policy checkpoint logged
    op.create_table(
        "policy_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("voice_session_id", UUID(as_uuid=True), sa.ForeignKey("voice_sessions.id"), index=True),
        sa.Column("call_log_id", UUID(as_uuid=True), sa.ForeignKey("call_logs.id"), index=True),
        sa.Column("turn_number", sa.Integer),

        sa.Column("trigger_tool", sa.String(50)),
        sa.Column("trigger_reason", sa.String(50), nullable=True),

        sa.Column("phase_before", sa.String(30)),
        sa.Column("phase_after", sa.String(30)),
        sa.Column("detected_intent", sa.String(30), nullable=True),
        sa.Column("intent_confidence", sa.Float, nullable=True),

        sa.Column("policy_name", sa.String(50)),
        sa.Column("allowed", sa.Boolean),
        sa.Column("required_action", sa.String(50)),
        sa.Column("reason_code", sa.String(50)),
        sa.Column("instruction_nl", sa.Text, nullable=True),

        sa.Column("model_complied", sa.Boolean, nullable=True),
        sa.Column("violation", sa.Boolean, server_default="false"),
        sa.Column("violation_type", sa.String(50), nullable=True),

        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Enrich call_logs with hangup metadata
    op.add_column("call_logs", sa.Column("hangup_reason", sa.String(50), nullable=True))
    op.add_column("call_logs", sa.Column("goodbye_handshake_ok", sa.Boolean, nullable=True))
    op.add_column("call_logs", sa.Column("ended_by", sa.String(20), nullable=True))
    op.add_column("call_logs", sa.Column("policy_violations_count", sa.Integer, server_default="0"))


def downgrade():
    op.drop_column("call_logs", "policy_violations_count")
    op.drop_column("call_logs", "ended_by")
    op.drop_column("call_logs", "goodbye_handshake_ok")
    op.drop_column("call_logs", "hangup_reason")
    op.drop_table("policy_decisions")
    op.drop_table("voice_sessions")
