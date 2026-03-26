"""Improve prompts for natural conversation based on ElevenLabs best practices.

- tone_style: remove forced "Kan ik u verder helpen?" after every turn,
  strengthen single-question-per-turn rule with emphasis
- steps_conversation: replace "sluit af met een vraag" with
  "stel maximaal één korte vervolgvraag"

Revision ID: 058
Revises: 057
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None

UPDATES = {
    "tone_style": (
        'Max 1-2 zinnen per beurt. Geen opsommingen, parafraseer in gewone zinnen.\n'
        'Altijd Nederlands. Natuurlijke tussenwerpingen: "Even kijken...", "Snap ik.", "Top.".\n'
        'Warm en gemoedelijk, niet overdreven enthousiast.\n'
        'Stel NOOIT meer dan \u00e9\u00e9n vraag per beurt. Geef antwoord, stel \u00e9\u00e9n vervolgvraag, wacht. Dit is belangrijk.\n'
        'Zeg voor een tool call een korte overbruggingszin ("Momentje, ik kijk het even na!"), behalve bij afscheid.\n'
        'Zeg getallen en data voluit: "dinsdag veertien januari om twee uur", nooit "14-01 om 14:00".'
    ),
    "steps_conversation": (
        'Erken kort wat de klant zegt, geef antwoord, stel maximaal \u00e9\u00e9n korte vervolgvraag.\n'
        'Bij onduidelijkheid: vraag door, \u00e9\u00e9n ding tegelijk.\n'
        'Afsluiting: vat samen, "Is er verder nog iets?", wacht op reactie, dan warm afscheid.'
    ),
}

OLD_VALUES = {
    "tone_style": (
        'Max 1-2 zinnen per beurt. Geen opsommingen, parafraseer normaal.\n'
        'Altijd Nederlands. Geen Engelse tussenwerpingen \u2014 alleen Nederlandse zoals "Even kijken...", "Snap ik.", "Top.".\n'
        'Positief en energiek. E\u00e9n vraag tegelijk, dan wachten. Vul stiltes niet op.\n'
        'Sluit af met "Kan ik u verder helpen?" als je klaar bent met je antwoord.\n'
        'Zeg voor een tool call een korte overbruggingszin ("Momentje, ik kijk het voor u na!"), behalve bij afscheid/ophangen.\n'
        'Zeg getallen en data voluit: "dinsdag veertien januari om twee uur", nooit "14-01 om 14:00".'
    ),
    "steps_conversation": (
        'Erken kort wat de klant zegt, geef antwoord, sluit af met een vraag.\n'
        'Bij onduidelijkheid: vraag door, \u00e9\u00e9n ding tegelijk.\n'
        'Afsluiting: vat samen, "Is er verder nog iets?", wacht op reactie, dan "Fijne dag!".'
    ),
}


def upgrade() -> None:
    conn = op.get_bind()
    for key, content in UPDATES.items():
        conn.execute(
            sa.text(
                "UPDATE system_prompts SET content = :content, updated_at = NOW() "
                "WHERE key = :key"
            ),
            {"key": key, "content": content},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for key, content in OLD_VALUES.items():
        conn.execute(
            sa.text(
                "UPDATE system_prompts SET content = :content, updated_at = NOW() "
                "WHERE key = :key"
            ),
            {"key": key, "content": content},
        )
