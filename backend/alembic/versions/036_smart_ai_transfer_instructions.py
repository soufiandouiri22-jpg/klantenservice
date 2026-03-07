"""add transfer, custom_instructions, sms_callback fields

Revision ID: 036
Revises: 035
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "036_transfer_instructions"
down_revision = "035_sms_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phone number: transfer settings
    op.add_column(
        "phone_numbers",
        sa.Column("transfer_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "phone_numbers",
        sa.Column("transfer_number", sa.String(20), nullable=True),
    )
    # Phone number: SMS callback template
    op.add_column(
        "phone_numbers",
        sa.Column(
            "sms_callback_template",
            sa.String(500),
            server_default="Uw verzoek is genoteerd bij {bedrijfsnaam}. U wordt zo snel mogelijk teruggebeld.",
            nullable=True,
        ),
    )
    # Company: custom AI instructions
    op.add_column(
        "companies",
        sa.Column("custom_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "custom_instructions")
    op.drop_column("phone_numbers", "sms_callback_template")
    op.drop_column("phone_numbers", "transfer_number")
    op.drop_column("phone_numbers", "transfer_enabled")
