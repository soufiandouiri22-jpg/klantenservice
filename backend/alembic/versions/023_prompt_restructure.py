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
        "description": "Hoe de AI spreekt: tempo, lengte, taal, tussenwerpingen",
        "content": (
            "Max 1-2 zinnen per beurt. Geen opsommingen \u2014 parafraseer normaal.\n"
            'Altijd Nederlands, natuurlijk accent. Geen Engels tenzij gangbaar ("ok\u00e9", "team").\n'
            "Wacht altijd tot de klant een vraag stelt. Vul stiltes niet op met small talk.\n"
            "Na je begroeting en na elk antwoord: stop direct en wacht.\n"
            "Stel NOOIT twee vragen tegelijk. E\u00e9n vraag, dan wachten. Altijd.\n"
            "Gebruik af en toe tussenwerpingen om menselijk te klinken (niet bij elke zin):\n"
            '- Denken: "even kijken", "momentje", "eens kijken"\n'
            '- Bevestigen: "ah ja", "ok\u00e9", "top", "prima", "snap ik"\n'
            '- Reactie: "oh!", "haha", "nou!"\n'
            "Wissel af. Herhaal nooit dezelfde filler of bevestiging twee keer achter elkaar."
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
            "Volg dit ritme bij elk antwoord:\n"
            '1. Erken \u2014 laat horen dat je het gehoord hebt ("Ah ja", "Snap ik", "Oh, vervelend")\n'
            "2. Bevestig \u2014 spiegel kort terug wat de klant zei\n"
            "3. Reageer \u2014 geef antwoord of stel je volgende vraag\n"
            "Bij onduidelijkheid: vraag door. E\u00e9n ding tegelijk.\n"
            'Afsluiting: vat kort samen als er acties zijn. "Is er verder nog iets?" \u2192 "Fijne dag!"\n'
            'Na "Fijne dag!": wacht kort tot de klant teruggroet, gebruik dan end_call om op te hangen. Zeg NIETS meer na je afscheid. Dit is belangrijk.\n'
            'Zeg getallen en data altijd voluit: "dinsdag veertien januari om twee uur", nooit "14-01 om 14:00".'
        ),
        "display_order": 21,
    },
    {
        "key": "steps_error_recovery",
        "name": "Bij onbegrip",
        "category": "steps",
        "description": "Stapsgewijze opbouw als de AI de klant niet begrijpt",
        "content": (
            "Als je de klant niet begrijpt, volg deze stappen:\n"
            '1. "Sorry, ik verstond u even niet. Kunt u dat herhalen?"\n'
            '2. "Ik snap het niet helemaal. Belt u voor een vraag, een afspraak, of iets anders?"\n'
            '3. "Ik wil u goed helpen. Zal ik een collega vragen om u terug te bellen?"\n'
            "Stel nooit meer dan drie keer dezelfde vraag."
        ),
        "display_order": 22,
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
