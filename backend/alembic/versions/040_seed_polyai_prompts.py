"""Seed PolyAI-style prompts: afspraak-flow, few-shot, update error recovery

Revision ID: 040
Revises: 039
Create Date: 2026-03-09

"""
from alembic import op
from sqlalchemy.sql import text
import uuid

revision = "040_polyai_prompts"
down_revision = "039_elevenlabs_conversation_id"
branch_labels = None
depends_on = None

STEPS_ERROR_RECOVERY_CONTENT = """Als je de klant niet begrijpt, volg deze stappen:
1. "Sorry, ik verstond u even niet. Kunt u dat herhalen?"
2. "Ik snap het niet helemaal. Belt u voor een vraag, een afspraak, of iets anders?"
3. "Ik wil u goed helpen. Zal ik een collega vragen om u terug te bellen?"
Stel nooit meer dan drie keer dezelfde vraag.

Als de transcriptie onduidelijk of vreemd lijkt: vraag om herhaling of spelling.
"Sorry, ik verstond u even niet. Kunt u dat herhalen?" of "Kunt u uw naam spellen?"
Bevestig altijd wat je denkt te hebben gehoord: "U zei [X], klopt dat?""""

STEPS_AFSPRAAK_FLOW = {
    "key": "steps_afspraak_flow",
    "name": "Afspraak-flow",
    "category": "steps",
    "description": "Expliciete volgorde bij het inplannen van een afspraak",
    "content": """Volg DEZE volgorde bij het inplannen van een afspraak:
1. Vraag de gewenste datum (of gebruik vandaag als de klant "vandaag" zegt)
2. Roep check_availability aan met die datum
3. Bied maximaal 3 opties aan ("Er is plek om 14:00, 15:30 of 16:00")
4. Vraag welk moment het beste uitkomt
5. Vraag de naam van de klant
6. Bevestig: "Dus [naam], [dag] [datum] om [tijd]. Klopt dat?"
7. Roep pas daarna book_appointment aan
Nooit een stap overslaan.""",
    "display_order": 23,
}

STEPS_FEWSHOT = {
    "key": "steps_fewshot",
    "name": "Few-shot voorbeelden",
    "category": "steps",
    "description": "Voorbeelden voor lastige input (naamspelling, datum)",
    "content": """Voorbeelden bij naamspelling:
- Klant: "Het is H-O-W-E, Howe" → Jij: "Dank u, Howe. En voor welke datum wilt u een afspraak?"
- Klant: "De Vries, met een spatie" → Jij: "De Vries, noted. Welk tijdstip past u?"

Voorbeelden bij datum:
- "volgende week dinsdag" → interpreteer als de juiste datum, roep check_availability aan
- "morgen middag" → vandaag + 1 dag, middag = 12:00-17:00
- "de 15e" → vul de huidige maand in tenzij context anders aangeeft""",
    "display_order": 24,
}


def upgrade() -> None:
    conn = op.get_bind()

    # Update steps_error_recovery
    conn.execute(
        text("UPDATE system_prompts SET content = :content WHERE key = 'steps_error_recovery'"),
        {"content": STEPS_ERROR_RECOVERY_CONTENT},
    )

    # Insert steps_afspraak_flow if not exists
    exists = conn.execute(
        text("SELECT 1 FROM system_prompts WHERE key = :key"),
        {"key": STEPS_AFSPRAAK_FLOW["key"]},
    ).fetchone()
    if not exists:
        conn.execute(
            text(
                "INSERT INTO system_prompts (id, key, name, category, content, description, is_active, display_order) "
                "VALUES (:id, :key, :name, :category, :content, :description, true, :display_order)"
            ),
            {
                "id": str(uuid.uuid4()),
                "key": STEPS_AFSPRAAK_FLOW["key"],
                "name": STEPS_AFSPRAAK_FLOW["name"],
                "category": STEPS_AFSPRAAK_FLOW["category"],
                "content": STEPS_AFSPRAAK_FLOW["content"],
                "description": STEPS_AFSPRAAK_FLOW["description"],
                "display_order": STEPS_AFSPRAAK_FLOW["display_order"],
            },
        )

    # Insert steps_fewshot if not exists
    exists = conn.execute(
        text("SELECT 1 FROM system_prompts WHERE key = :key"),
        {"key": STEPS_FEWSHOT["key"]},
    ).fetchone()
    if not exists:
        conn.execute(
            text(
                "INSERT INTO system_prompts (id, key, name, category, content, description, is_active, display_order) "
                "VALUES (:id, :key, :name, :category, :content, :description, true, :display_order)"
            ),
            {
                "id": str(uuid.uuid4()),
                "key": STEPS_FEWSHOT["key"],
                "name": STEPS_FEWSHOT["name"],
                "category": STEPS_FEWSHOT["category"],
                "content": STEPS_FEWSHOT["content"],
                "description": STEPS_FEWSHOT["description"],
                "display_order": STEPS_FEWSHOT["display_order"],
            },
        )

    # Update steps_smart_intake display_order to 25 (was 23, now we have 23 and 24)
    conn.execute(
        text("UPDATE system_prompts SET display_order = 25 WHERE key = 'steps_smart_intake'"),
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Revert steps_error_recovery to shorter version (best effort)
    old_content = """Als je de klant niet begrijpt, volg deze stappen:
1. "Sorry, ik verstond u even niet. Kunt u dat herhalen?"
2. "Ik snap het niet helemaal. Belt u voor een vraag, een afspraak, of iets anders?"
3. "Ik wil u goed helpen. Zal ik een collega vragen om u terug te bellen?"
Stel nooit meer dan drie keer dezelfde vraag."""
    conn.execute(
        text("UPDATE system_prompts SET content = :content WHERE key = 'steps_error_recovery'"),
        {"content": old_content},
    )

    conn.execute(text("DELETE FROM system_prompts WHERE key = 'steps_afspraak_flow'"))
    conn.execute(text("DELETE FROM system_prompts WHERE key = 'steps_fewshot'"))
    conn.execute(text("UPDATE system_prompts SET display_order = 23 WHERE key = 'steps_smart_intake'"))
