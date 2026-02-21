"""Hang up silently after caller says goodbye - no double greeting

Revision ID: 026_silent_hangup
Revises: 025_fix_smalltalk_hangup
Create Date: 2026-02-22
"""
from alembic import op
import sqlalchemy as sa

revision = "026_silent_hangup"
down_revision = "025_fix_smalltalk_hangup"
branch_labels = None
depends_on = None

UPDATES = {
    "steps_conversation": (
        'Volg dit ritme bij elk antwoord:\n'
        '1. Erken \u2014 laat horen dat je het gehoord hebt ("Ah ja", "Snap ik", "Oh, vervelend")\n'
        '2. Bevestig \u2014 spiegel kort terug wat de klant zei\n'
        '3. Reageer \u2014 geef antwoord \u00e9n sluit altijd af met een vraag om het gesprek gaande te houden\n'
        'Bij onduidelijkheid: vraag door. E\u00e9n ding tegelijk.\n'
        'Stop NOOIT na alleen een antwoord. Eindig altijd met een vraag of check-in.\n'
        'Afsluiting: vat kort samen als er acties zijn. "Is er verder nog iets?" \u2192 "Fijne dag!"\n'
        'Na je afscheid ("Fijne dag!", "Prettige avond!" etc.): WACHT ALTIJD tot de klant teruggroet ("Dag!", "Doei", "Bedankt", etc.). '
        'Zodra de klant teruggroet: zeg NIETS meer en gebruik direct end_call. Niet nog een keer "Fijne dag" of "Dag" zeggen. Gewoon ophangen. Dit is heel belangrijk.\n'
        'Als de klant zegt dat ze geen hulp nodig hebben: vraag vriendelijk "Ok\u00e9! Mocht u toch nog iets nodig hebben, bel gerust. Fijne dag!" en WACHT dan op hun reactie. Hang NOOIT direct op.\n'
        'Zeg getallen en data altijd voluit: "dinsdag veertien januari om twee uur", nooit "14-01 om 14:00".'
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
    pass
