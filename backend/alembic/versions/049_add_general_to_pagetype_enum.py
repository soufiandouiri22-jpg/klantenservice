"""Add 'general' to pagetype enum

Revision ID: 049
Revises: 048
"""
from alembic import op

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE pagetype ADD VALUE IF NOT EXISTS 'general'")


def downgrade() -> None:
    pass
