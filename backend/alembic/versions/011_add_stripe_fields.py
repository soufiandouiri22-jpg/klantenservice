"""Add Stripe fields to companies

Revision ID: 011_add_stripe_fields
Revises: 010_set_superadmin
Create Date: 2026-02-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_add_stripe_fields'
down_revision = '010_set_superadmin'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add Stripe fields to companies table
    op.add_column('companies', sa.Column('stripe_customer_id', sa.String(255), nullable=True))
    op.add_column('companies', sa.Column('stripe_subscription_id', sa.String(255), nullable=True))
    
    # Create unique index on stripe_customer_id
    op.create_index('ix_companies_stripe_customer_id', 'companies', ['stripe_customer_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_companies_stripe_customer_id', table_name='companies')
    op.drop_column('companies', 'stripe_subscription_id')
    op.drop_column('companies', 'stripe_customer_id')
