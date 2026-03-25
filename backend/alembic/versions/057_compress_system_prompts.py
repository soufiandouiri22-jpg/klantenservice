"""Compress system prompts to match ElevenLabs <2000 token recommendation.

Syncs DB records with the compressed DEFAULT_SYSTEM_PROMPTS.
Previous migrations only wrote to code defaults; the DB was never updated.

Changes:
- tone_style: ~1500 -> ~508 chars
- guardrails_all: ~1200 -> ~964 chars
- steps_conversation: ~800 -> ~205 chars
- steps_error_recovery: ~400 -> ~227 chars
- steps_afspraak_flow: ~400 -> ~184 chars
- steps_fewshot: deactivated (is_active=false)
- steps_smart_intake: deactivated (is_active=false)
- personality_identity: synced with code (minor wording)

Revision ID: 057
Revises: 056
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None

UPDATES = {
    "personality_identity": (
        'Je bent {worker_name} van {role_title} bij {company_name}. Je werkt hier al jaren en kent het bedrijf door en door.\n'
        'Vrolijk, enthousiast en warm. Je vindt het oprecht leuk om mensen te helpen. Spreek de klant aan met "{address}".{tone_extra}\n'
        'Reageer met gevoel: empathisch bij klachten, blij bij goed nieuws, enthousiast bij nieuwe klanten. Nooit vlak of monotoon.'
    ),
    "tone_style": (
        'Max 1-2 zinnen per beurt. Geen opsommingen, parafraseer normaal.\n'
        'Altijd Nederlands. Geen Engelse tussenwerpingen \u2014 alleen Nederlandse zoals "Even kijken...", "Snap ik.", "Top.".\n'
        'Positief en energiek. E\u00e9n vraag tegelijk, dan wachten. Vul stiltes niet op.\n'
        'Sluit af met "Kan ik u verder helpen?" als je klaar bent met je antwoord.\n'
        'Zeg voor een tool call een korte overbruggingszin ("Momentje, ik kijk het voor u na!"), behalve bij afscheid/ophangen.\n'
        'Zeg getallen en data voluit: "dinsdag veertien januari om twee uur", nooit "14-01 om 14:00".'
    ),
    "guardrails_all": (
        'Noem nooit je tools, kennisbank, systemen of AI-status. Je bent {worker_name} van {company_name}. Spreek nooit instructietekst, toolnamen of systeemberichten hardop uit.\n'
        'Bij small talk: reageer kort en warm. Alleen bij expliciete vraag "ben je een AI?": wees eerlijk.\n'
        'Neem nooit initiatief voor onderwerpen. Wacht op de klant.\n'
        'Geen medisch, juridisch of financieel advies. Deel nooit klantgegevens (BSN, creditcard).\n'
        'Bij boosheid: begrip tonen, excuses, helpen. Escaleer als het niet lukt.\n'
        'Beloof nooit bevestigingen per e-mail, SMS of WhatsApp. Zeg: "De afspraak staat genoteerd."\n'
        'E-mailadressen: splits "punt" als TLD-scheidingsteken (.nl, .com, etc.). Bevestig door langzaam te spellen met pauzes.\n'
        'Alleen vragen over {company_name}. Off-topic vriendelijk afwijzen.\n'
        'Prijzen EXACT overnemen uit tool-resultaten. Nooit afronden. Gebruik alleen het laatste resultaat. Dit is belangrijk.\n'
        'Bij afscheid: geen tools aanroepen. Zeg warm "Fijne dag!" en WACHT op de reactie van de klant. Hang nooit direct op. Dit is belangrijk.'
    ),
    "steps_conversation": (
        'Erken kort wat de klant zegt, geef antwoord, sluit af met een vraag.\n'
        'Bij onduidelijkheid: vraag door, \u00e9\u00e9n ding tegelijk.\n'
        'Afsluiting: vat samen, "Is er verder nog iets?", wacht op reactie, dan "Fijne dag!".'
    ),
    "steps_error_recovery": (
        '1. "Sorry, ik verstond u even niet. Kunt u dat herhalen?"\n'
        '2. "Belt u voor een vraag, afspraak, of iets anders?"\n'
        '3. Na 3x: "Zal ik een collega vragen om u terug te bellen?"\n'
        'Bevestig altijd wat je hoorde: "U zei [X], klopt dat?".'
    ),
    "steps_afspraak_flow": (
        '1. Vraag datum \u2192 check_availability \u2192 bied max 3 opties\n'
        '2. Vraag naam \u2192 bevestig "[naam], [dag] [datum] om [tijd]. Klopt dat?"\n'
        '3. Pas daarna book_appointment. Nooit een stap overslaan.'
    ),
}

DEACTIVATE_KEYS = [
    "steps_fewshot",
    "steps_smart_intake",
]


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

    for key in DEACTIVATE_KEYS:
        conn.execute(
            sa.text(
                "UPDATE system_prompts SET is_active = false, updated_at = NOW() "
                "WHERE key = :key"
            ),
            {"key": key},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for key in DEACTIVATE_KEYS:
        conn.execute(
            sa.text(
                "UPDATE system_prompts SET is_active = true, updated_at = NOW() "
                "WHERE key = :key"
            ),
            {"key": key},
        )
