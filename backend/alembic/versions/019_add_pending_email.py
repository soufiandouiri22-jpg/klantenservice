"""
Add pending_email column to users table for email change verification.

Revision ID: 019_add_pending_email
Revises: 018_seed_prompt_sections
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "019_add_pending_email"
down_revision = "018_seed_prompt_sections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_email", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "pending_email")
