"""Add registration consent fields to companies

Revision ID: 014_register_consents
Revises: 013_admin_dashboard_models
Create Date: 2026-02-06

- terms_accepted_at: when the user agreed to terms & privacy at signup
- marketing_consent: opt-in for email marketing
"""
from alembic import op
import sqlalchemy as sa


revision = '014_register_consents'
down_revision = '013_admin_dashboard_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('terms_accepted_at', sa.DateTime(), nullable=True))
    op.add_column('companies', sa.Column('marketing_consent', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('companies', 'marketing_consent')
    op.drop_column('companies', 'terms_accepted_at')
