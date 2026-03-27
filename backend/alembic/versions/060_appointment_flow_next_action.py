"""Align steps_afspraak_flow with dynamic check_availability next_action.

Revision ID: 060
Revises: 059
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None

KEY = "steps_afspraak_flow"

NEW = (
    "1. check_availability: `start_date` met tijd meegeven als de klant die al noemde (bijv. maandag 10:00).\n"
    "2. Volg `next_action` uit het tool-resultaat: bij bevestigen geen extra tijdopties; bij kiezen max 3 uit `slots`.\n"
    "3. Naam \u2192 korte bevestiging \u2192 book_appointment."
)

OLD = (
    "1. Vraag datum \u2192 check_availability \u2192 bied max 3 opties\n"
    "2. Vraag naam \u2192 bevestig \"[naam], [dag] [datum] om [tijd]. Klopt dat?\"\n"
    "3. Pas daarna book_appointment. Nooit een stap overslaan."
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE system_prompts SET content = :content, updated_at = NOW() "
            "WHERE key = :key"
        ),
        {"key": KEY, "content": NEW},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE system_prompts SET content = :content, updated_at = NOW() "
            "WHERE key = :key"
        ),
        {"key": KEY, "content": OLD},
    )
