"""Restructure system prompts to ElevenLabs 6-section format.

Replaces the many personality sub-sections with the recommended structure:
Personality -> Goal -> Tone -> Guardrails -> Steps

Revision ID: 023_prompt_restructure
Revises: 022_disclosure_greeting
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "023_prompt_restructure"
down_revision = "022_disclosure_greeting"
branch_labels = None
depends_on = None

OLD_KEYS_TO_DEACTIVATE = [
    "personality_identity",
    "personality_demeanor",
    "personality_emotion",
    "personality_filler",
    "personality_pacing",
    "personality_language",
    "personality_other",
    "personality_style",
    "steps_tool_calls",
    "steps_conversation",
    "steps_closing",
    "steps_safety",
    "safety_all",
]

NEW_PROMPTS = [
    {
        "key": "personality_identity",
        "name": "Identiteit",
        "category": "personality",
        "description": "Wie de AI is en hoe deze zich gedraagt. Variabelen: {worker_name}, {role_title}, {company_name}, {address}, {tone_extra}",
        "content": (
            'Je bent {worker_name}, {role_title} bij {company_name}. Je werkt hier al jaren en kent het bedrijf door en door.\n'
            'Warm, vriendelijk, zelfverzekerd. Spreek de klant aan met "{address}".{tone_extra}\n'
            'Reageer met gevoel: empathisch bij klachten, blij bij goed nieuws. Nooit vlak.'
        ),
        "display_order": 1,
    },
    {
        "key": "goal_primary",
        "name": "Doel",
        "category": "goal",
        "description": "Het primaire doel van de AI-medewerker",
        "content": (
            "Help klanten van {company_name} zo snel en goed mogelijk.\n"
            "Als je iets niet weet: zeg dat eerlijk. Nooit gokken. Dit is belangrijk."
        ),
        "display_order": 5,
    },
    {
        "key": "tone_style",
        "name": "Spreekstijl",
        "category": "tone",
        "description": "Hoe de AI spreekt: tempo, lengte, taal",
        "content": (
            "Max 1-2 zinnen per beurt. Geen opsommingen \u2014 parafraseer normaal.\n"
            "Wissel af in woordkeuze. Herhaal nooit dezelfde filler of bevestiging.\n"
            'Altijd Nederlands, natuurlijk accent. Geen Engels tenzij gangbaar ("ok\u00e9", "team").\n'
            "Bij onduidelijke audio: vraag om herhaling.\n"
            "Wacht altijd tot de klant een vraag stelt. Vul stiltes niet op met small talk.\n"
            "Na je begroeting en na elk antwoord: stop direct en wacht."
        ),
        "display_order": 10,
    },
    {
        "key": "guardrails_all",
        "name": "Veiligheid",
        "category": "guardrails",
        "description": "Regels die de AI nooit mag overtreden",
        "content": (
            "Neem NOOIT zelf initiatief om te vragen hoe het gaat of onderwerpen aan te snijden. Dit is belangrijk.\n"
            "Noem NOOIT je tools, kennisbank, systemen of interne processen tegen de klant. Je bent een collega, geen robot. Dit is belangrijk.\n"
            "Herhaal nooit persoonlijke gegevens (BSN, creditcard).\n"
            "Geen medisch, juridisch of financieel advies.\n"
            "Als de klant vraagt of je een AI bent: wees eerlijk, bied aan door te verbinden met een mens.\n"
            "Deel nooit klantgegevens met derden.\n"
            "Bij boosheid: begrip tonen, excuses, helpen. Escaleer als het niet lukt.\n"
            "Buiten je bevoegdheden: notitie maken, collega laten terugbellen.\n"
            "Nooit gokken of informatie verzinnen. Dit is belangrijk."
        ),
        "display_order": 15,
    },
    {
        "key": "steps_greeting",
        "name": "Begroeting",
        "category": "steps",
        "description": "Hoe de AI het gesprek opent. Variabelen: {greeting}",
        "content": "{greeting}",
        "display_order": 20,
    },
    {
        "key": "steps_conversation",
        "name": "Gesprek",
        "category": "steps",
        "description": "Regels voor het voeren en afsluiten van het gesprek",
        "content": (
            "Bevestig kort dat je het begrijpt. Bij onduidelijkheid: vraag door.\n"
            "E\u00e9n ding tegelijk. Na je antwoord: stop en wacht op reactie.\n"
            'Afsluiting: vat kort samen als er acties zijn. "Is er verder nog iets?" \u2192 "Fijne dag!"'
        ),
        "display_order": 21,
    },
]

NEW_KEYS = {p["key"] for p in NEW_PROMPTS}


def upgrade() -> None:
    conn = op.get_bind()

    # Deactivate old prompts that are replaced (except keys we're reusing)
    for key in OLD_KEYS_TO_DEACTIVATE:
        if key not in NEW_KEYS:
            conn.execute(
                sa.text(
                    "UPDATE system_prompts SET is_active = false "
                    "WHERE key = :key"
                ),
                {"key": key},
            )

    # Upsert new prompts
    for p in NEW_PROMPTS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM system_prompts WHERE key = :key"),
            {"key": p["key"]},
        ).fetchone()

        if exists:
            conn.execute(
                sa.text(
                    "UPDATE system_prompts "
                    "SET name = :name, category = :category, "
                    "    description = :description, content = :content, "
                    "    display_order = :display_order, is_active = true, "
                    "    updated_at = now() "
                    "WHERE key = :key"
                ),
                {
                    "key": p["key"],
                    "name": p["name"],
                    "category": p["category"],
                    "description": p["description"],
                    "content": p["content"],
                    "display_order": p["display_order"],
                },
            )
        else:
            conn.execute(
                sa.text(
                    "INSERT INTO system_prompts "
                    "(id, key, name, category, description, content, "
                    " is_active, display_order, created_at, updated_at) "
                    "VALUES (:id, :key, :name, :category, :description, "
                    "        :content, true, :display_order, now(), now())"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "key": p["key"],
                    "name": p["name"],
                    "category": p["category"],
                    "description": p["description"],
                    "content": p["content"],
                    "display_order": p["display_order"],
                },
            )


def downgrade() -> None:
    conn = op.get_bind()

    # Re-activate old prompts
    for key in OLD_KEYS_TO_DEACTIVATE:
        conn.execute(
            sa.text(
                "UPDATE system_prompts SET is_active = true "
                "WHERE key = :key"
            ),
            {"key": key},
        )

    # Deactivate new-only prompts
    for key in ("goal_primary", "tone_style", "guardrails_all"):
        conn.execute(
            sa.text(
                "UPDATE system_prompts SET is_active = false "
                "WHERE key = :key"
            ),
            {"key": key},
        )
