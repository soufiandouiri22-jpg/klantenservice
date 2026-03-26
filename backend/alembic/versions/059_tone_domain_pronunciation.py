"""Add TLD pronunciation hint to tone_style (voice / .ai etc.).

Revision ID: 059
Revises: 058
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None

NEW = (
    'Max 1-2 zinnen per beurt. Geen opsommingen, parafraseer in gewone zinnen.\n'
    'Altijd Nederlands. Natuurlijke tussenwerpingen: "Even kijken...", "Snap ik.", "Top.".\n'
    'Warm en gemoedelijk, niet overdreven enthousiast.\n'
    'Stel NOOIT meer dan \u00e9\u00e9n vraag per beurt. Geef antwoord, stel \u00e9\u00e9n vervolgvraag, wacht. Dit is belangrijk.\n'
    'Zeg voor een tool call een korte overbruggingszin ("Momentje, ik kijk het even na!"), behalve bij afscheid.\n'
    'Zeg getallen en data voluit: "dinsdag veertien januari om twee uur", nooit "14-01 om 14:00".\n'
    'Spreek TLD\'s in domeinnamen uit als "punt ai", "punt nl", "punt com" \u2014 niet als losse letters.'
)

OLD = (
    'Max 1-2 zinnen per beurt. Geen opsommingen, parafraseer in gewone zinnen.\n'
    'Altijd Nederlands. Natuurlijke tussenwerpingen: "Even kijken...", "Snap ik.", "Top.".\n'
    'Warm en gemoedelijk, niet overdreven enthousiast.\n'
    'Stel NOOIT meer dan \u00e9\u00e9n vraag per beurt. Geef antwoord, stel \u00e9\u00e9n vervolgvraag, wacht. Dit is belangrijk.\n'
    'Zeg voor een tool call een korte overbruggingszin ("Momentje, ik kijk het even na!"), behalve bij afscheid.\n'
    'Zeg getallen en data voluit: "dinsdag veertien januari om twee uur", nooit "14-01 om 14:00".'
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE system_prompts SET content = :content, updated_at = NOW() "
            "WHERE key = 'tone_style'"
        ),
        {"content": NEW},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE system_prompts SET content = :content, updated_at = NOW() "
            "WHERE key = 'tone_style'"
        ),
        {"content": OLD},
    )
