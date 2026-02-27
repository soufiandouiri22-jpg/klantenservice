"""add sms confirmation fields to phone_numbers

Revision ID: 035
Revises: 034
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "phone_numbers",
        sa.Column("sms_confirmation_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "phone_numbers",
        sa.Column(
            "sms_confirmation_template",
            sa.String(500),
            server_default="Uw afspraak bij {bedrijfsnaam} is bevestigd op {datum} om {tijd}. Tot dan!",
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("phone_numbers", "sms_confirmation_template")
    op.drop_column("phone_numbers", "sms_confirmation_enabled")
