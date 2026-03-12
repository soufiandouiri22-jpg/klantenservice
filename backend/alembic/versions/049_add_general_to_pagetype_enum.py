"""Add 'general' to pagetype enum (no-op: column is VARCHAR, not a DB enum)

Revision ID: 049
Revises: 048
"""

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
