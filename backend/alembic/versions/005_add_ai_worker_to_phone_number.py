"""Add ai_worker_id to phone_numbers table

Revision ID: 005
Revises: 004_fix_website_knowledge
Create Date: 2026-01-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_ai_worker_phone'
down_revision = '004_fix_website'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add ai_worker_id column to phone_numbers table
    op.add_column(
        'phone_numbers',
        sa.Column('ai_worker_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_phone_numbers_ai_worker_id',
        'phone_numbers',
        'ai_workers',
        ['ai_worker_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint('fk_phone_numbers_ai_worker_id', 'phone_numbers', type_='foreignkey')
    
    # Remove column
    op.drop_column('phone_numbers', 'ai_worker_id')
