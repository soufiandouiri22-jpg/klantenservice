"""Add invite fields to users table

Revision ID: 002_add_invite
Revises: 001_add_oauth
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers
revision = '002_add_invite'
down_revision = '001_add_oauth'
branch_labels = None
depends_on = None


def upgrade():
    # Add invite system columns
    op.add_column('users', sa.Column(
        'invite_token', sa.String(255), nullable=True, unique=True, index=True
    ))
    op.add_column('users', sa.Column(
        'invite_token_expires_at', sa.DateTime(), nullable=True
    ))
    op.add_column('users', sa.Column(
        'invited_by_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True
    ))
    op.add_column('users', sa.Column(
        'invited_at', sa.DateTime(), nullable=True
    ))


def downgrade():
    op.drop_column('users', 'invited_at')
    op.drop_column('users', 'invited_by_id')
    op.drop_column('users', 'invite_token_expires_at')
    op.drop_column('users', 'invite_token')
