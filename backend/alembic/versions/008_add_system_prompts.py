"""Add system_prompts table and is_superadmin to users

Revision ID: 008_add_system_prompts
Revises: 007_seed_training_rules
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = '008_add_system_prompts'
down_revision = '007_seed_training_rules'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_superadmin column to users table
    op.add_column('users', sa.Column('is_superadmin', sa.Boolean(), nullable=True, default=False))
    
    # Set default value for existing users
    op.execute("UPDATE users SET is_superadmin = false WHERE is_superadmin IS NULL")
    
    # Make column not nullable
    op.alter_column('users', 'is_superadmin', nullable=False, server_default='false')
    
    # Create system_prompts table
    op.create_table(
        'system_prompts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=False, server_default='general'),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )
    
    # Create index on key for faster lookups
    op.create_index('ix_system_prompts_key', 'system_prompts', ['key'])
    op.create_index('ix_system_prompts_category', 'system_prompts', ['category'])


def downgrade():
    op.drop_index('ix_system_prompts_category', 'system_prompts')
    op.drop_index('ix_system_prompts_key', 'system_prompts')
    op.drop_table('system_prompts')
    op.drop_column('users', 'is_superadmin')
