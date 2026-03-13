"""Add email confirmation fields to phone_numbers

Revision ID: 052
Revises: 051
"""
from alembic import op
import sqlalchemy as sa

revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("phone_numbers", sa.Column("email_confirmation_enabled", sa.Boolean(), server_default="false"))
    op.add_column("phone_numbers", sa.Column("email_confirmation_template", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("phone_numbers", "email_confirmation_template")
    op.drop_column("phone_numbers", "email_confirmation_enabled")
