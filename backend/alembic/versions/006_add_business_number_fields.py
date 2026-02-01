"""Add business_number and setup fields to phone_numbers

Revision ID: 006_add_business_number_fields
Revises: 005_add_ai_worker_to_phone_number
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_business_number'
down_revision = '005_ai_worker_phone'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to phone_numbers table (if they don't exist)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('phone_numbers')]
    
    if 'business_number' not in columns:
        op.add_column('phone_numbers', sa.Column('business_number', sa.String(20), nullable=True))
    if 'provider' not in columns:
        op.add_column('phone_numbers', sa.Column('provider', sa.String(50), nullable=True))
    if 'setup_completed' not in columns:
        op.add_column('phone_numbers', sa.Column('setup_completed', sa.Boolean(), nullable=True, server_default='false'))
    if 'forwarding_verified' not in columns:
        op.add_column('phone_numbers', sa.Column('forwarding_verified', sa.Boolean(), nullable=True, server_default='false'))
    
    # Create index for business_number (if not exists)
    indexes = [idx['name'] for idx in inspector.get_indexes('phone_numbers')]
    if 'ix_phone_numbers_business_number' not in indexes:
        op.create_index(op.f('ix_phone_numbers_business_number'), 'phone_numbers', ['business_number'], unique=False)


def downgrade():
    # Remove index
    op.drop_index(op.f('ix_phone_numbers_business_number'), table_name='phone_numbers')
    
    # Remove columns
    op.drop_column('phone_numbers', 'forwarding_verified')
    op.drop_column('phone_numbers', 'setup_completed')
    op.drop_column('phone_numbers', 'provider')
    op.drop_column('phone_numbers', 'business_number')
