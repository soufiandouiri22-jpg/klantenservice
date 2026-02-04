"""Admin dashboard models

Revision ID: 013_admin_dashboard_models
Revises: 012_add_stripe_fields
Create Date: 2026-02-04

New tables:
- global_configs: Platform-wide settings
- usage_logs: API usage tracking
- latency_logs: Performance metrics
- context_logs: Orchestrator debugging

Company updates:
- is_kill_switched: Emergency stop for calls
- feature_flags: Per-company feature toggles
- admin_overrides: Hidden admin settings
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '013_admin_dashboard_models'
down_revision = '012_add_stripe_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create global_configs table
    op.create_table(
        'global_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', postgresql.JSON(), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_global_configs_key'), 'global_configs', ['key'], unique=True)
    op.create_index(op.f('ix_global_configs_category'), 'global_configs', ['category'], unique=False)
    
    # Create usage_logs table
    op.create_table(
        'usage_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('call_log_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('turn_id', sa.Integer(), nullable=True),
        sa.Column('stt_seconds', sa.Float(), nullable=True, default=0),
        sa.Column('stt_model', sa.String(50), nullable=True, default='whisper-1'),
        sa.Column('llm_input_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('llm_output_tokens', sa.Integer(), nullable=True, default=0),
        sa.Column('llm_model', sa.String(50), nullable=True),
        sa.Column('stt_cost_cents', sa.Integer(), nullable=True, default=0),
        sa.Column('llm_cost_cents', sa.Integer(), nullable=True, default=0),
        sa.Column('total_cost_cents', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['call_log_id'], ['call_logs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_logs_company_id'), 'usage_logs', ['company_id'], unique=False)
    op.create_index(op.f('ix_usage_logs_call_log_id'), 'usage_logs', ['call_log_id'], unique=False)
    op.create_index(op.f('ix_usage_logs_created_at'), 'usage_logs', ['created_at'], unique=False)
    
    # Create latency_logs table
    op.create_table(
        'latency_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('call_log_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=False),
        sa.Column('stt_latency_ms', sa.Integer(), nullable=True),
        sa.Column('orchestrator_latency_ms', sa.Integer(), nullable=True),
        sa.Column('pod_latency_ms', sa.Integer(), nullable=True),
        sa.Column('tts_latency_ms', sa.Integer(), nullable=True),
        sa.Column('total_latency_ms', sa.Integer(), nullable=True),
        sa.Column('queue_wait_ms', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['call_log_id'], ['call_logs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_latency_logs_call_log_id'), 'latency_logs', ['call_log_id'], unique=False)
    op.create_index(op.f('ix_latency_logs_created_at'), 'latency_logs', ['created_at'], unique=False)
    
    # Create context_logs table
    op.create_table(
        'context_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('call_log_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('turn_id', sa.Integer(), nullable=False),
        sa.Column('user_transcript', sa.Text(), nullable=True),
        sa.Column('assistant_transcript', sa.Text(), nullable=True),
        sa.Column('detected_intent', sa.String(100), nullable=True),
        sa.Column('intent_confidence', sa.Integer(), nullable=True),
        sa.Column('tool_calls', postgresql.JSON(), nullable=True),
        sa.Column('facts', sa.Text(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(50), nullable=True),
        sa.Column('was_escalated', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['call_log_id'], ['call_logs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_context_logs_call_log_id'), 'context_logs', ['call_log_id'], unique=False)
    op.create_index(op.f('ix_context_logs_created_at'), 'context_logs', ['created_at'], unique=False)
    
    # Add new columns to companies table
    op.add_column('companies', sa.Column('is_kill_switched', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('companies', sa.Column('feature_flags', postgresql.JSON(), nullable=True, server_default='{}'))
    op.add_column('companies', sa.Column('admin_overrides', postgresql.JSON(), nullable=True, server_default='{}'))


def downgrade() -> None:
    # Remove columns from companies table
    op.drop_column('companies', 'admin_overrides')
    op.drop_column('companies', 'feature_flags')
    op.drop_column('companies', 'is_kill_switched')
    
    # Drop tables
    op.drop_index(op.f('ix_context_logs_created_at'), table_name='context_logs')
    op.drop_index(op.f('ix_context_logs_call_log_id'), table_name='context_logs')
    op.drop_table('context_logs')
    
    op.drop_index(op.f('ix_latency_logs_created_at'), table_name='latency_logs')
    op.drop_index(op.f('ix_latency_logs_call_log_id'), table_name='latency_logs')
    op.drop_table('latency_logs')
    
    op.drop_index(op.f('ix_usage_logs_created_at'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_call_log_id'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_company_id'), table_name='usage_logs')
    op.drop_table('usage_logs')
    
    op.drop_index(op.f('ix_global_configs_category'), table_name='global_configs')
    op.drop_index(op.f('ix_global_configs_key'), table_name='global_configs')
    op.drop_table('global_configs')
