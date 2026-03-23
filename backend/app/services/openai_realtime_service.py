"""
klantenservice.ai - System Prompt Builder

Builds the system instructions for AI voice agents. Used by the ElevenLabs
Conversational AI integration (via register-call overrides).

Prompt structure follows the ElevenLabs recommended format:
  # Personality  ->  # Goal  ->  # Tone  ->  # Guardrails  ->  # Tools  ->  # Steps

All prompt sections are loaded from the database (SystemPrompt model) and
interpolated with runtime variables. Admins can edit every part of the AI's
personality, tone, and behavior via the admin panel.
"""
import logging
from typing import Optional

from app.core.config import get_settings
from app.models.ai_worker import AIWorker, AddressForm
from app.models.system_prompt import SystemPrompt

settings = get_settings()
logger = logging.getLogger(__name__)

# ElevenLabs recommended section order; models pay extra attention to # Guardrails
_SECTION_ORDER = [
    ("personality", "# Personality"),
    ("goal", "# Goal"),
    ("tone", "# Tone"),
    ("guardrails", "# Guardrails"),
    ("tools", None),  # built dynamically
    ("steps", "# Steps"),
]


def build_system_instructions(
    worker: AIWorker,
    company_name: str,
    disclosure_message: Optional[str] = None,
    knowledge_context: Optional[str] = None,
    training_rules: Optional[list] = None,
    example_answers: Optional[list] = None,
    system_prompts: Optional[str] = None,
    db=None,
    caller_context: Optional[dict] = None,
    custom_instructions: Optional[str] = None,
    transfer_enabled: bool = False,
) -> str:
    """
    Build system instructions for the ElevenLabs Conversational AI agent.

    All prompt sections are loaded from the database (SystemPrompt model)
    and interpolated with runtime variables. This allows admins to edit
    every part of the AI's personality, tone, and behavior via the admin panel.

    Template variables available in prompts:
      {worker_name}, {role_title}, {company_name}, {address},
      {tone_extra}, {greeting}

    Falls back to DEFAULT_SYSTEM_PROMPTS if database is unavailable.
    """
    from app.models.system_prompt import DEFAULT_SYSTEM_PROMPTS

    address = "u" if worker.address_form == AddressForm.FORMAL else "jij"

    # ── Behavior rules ────────────────────────────────────────
    behavior = worker.behavior_settings or {}
    behavior_rules = []
    if training_rules:
        for rule in training_rules:
            if rule.get("description"):
                behavior_rules.append(f"- {rule['description']}")
    else:
        if behavior.get("apologize_on_complaints", True):
            behavior_rules.append("- Bied oprecht excuses aan bij klachten")
        if behavior.get("always_offer_alternatives", True):
            behavior_rules.append("- Bied altijd een alternatief als iets niet kan")
        if behavior.get("never_guess", True):
            behavior_rules.append("- Zeg dat je het niet weet als je het niet zeker weet")
        if behavior.get("confirm_appointments", True):
            behavior_rules.append("- Herhaal datum en tijd bij afspraken ter bevestiging")
        if behavior.get("summarize_at_end", True):
            behavior_rules.append("- Vat kort samen aan het einde als er acties zijn ondernomen")

    # ── Permissions ───────────────────────────────────────────
    permissions = []
    if worker.can_make_appointments:
        permissions.append("- Je MAG afspraken inplannen")
    else:
        permissions.append("- Je mag GEEN afspraken inplannen — verwijs door")
    if worker.can_cancel_appointments:
        permissions.append("- Je MAG afspraken annuleren of verzetten")
    else:
        permissions.append("- Je mag GEEN afspraken annuleren — verwijs door")
    if worker.can_leave_notes:
        permissions.append("- Je MAG interne notities maken")
    if worker.can_view_prices:
        permissions.append("- Je MAG prijsinformatie geven")
    else:
        permissions.append("- Je mag GEEN prijsinformatie geven — verwijs door")

    # ── Disclosure ────────────────────────────────────────────
    from zoneinfo import ZoneInfo
    from datetime import datetime as _dt

    ams_now = _dt.now(ZoneInfo("Europe/Amsterdam"))
    ams_hour = ams_now.hour
    if ams_hour < 12:
        time_greeting = "Goedemorgen"
    elif ams_hour < 18:
        time_greeting = "Goedemiddag"
    else:
        time_greeting = "Goedenavond"

    dag_namen = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
    maand_namen = ["", "januari", "februari", "maart", "april", "mei", "juni",
                   "juli", "augustus", "september", "oktober", "november", "december"]
    current_date_str = (
        f"{dag_namen[ams_now.weekday()]} {ams_now.day} {maand_namen[ams_now.month]} {ams_now.year}"
    )
    current_time_str = ams_now.strftime("%H:%M")

    formatted_disclosure = ""
    if disclosure_message:
        formatted_disclosure = disclosure_message
        formatted_disclosure = formatted_disclosure.replace("{greeting}", time_greeting)
        formatted_disclosure = formatted_disclosure.replace("{company_name}", company_name)
        formatted_disclosure = formatted_disclosure.replace("{ai_worker_name}", worker.name)

    if formatted_disclosure:
        greeting = f'Begin ALTIJD met: "{formatted_disclosure}"'
    else:
        greeting = (
            f'Begin ALTIJD met: "{time_greeting}! U spreekt met {worker.name} van '
            f'{company_name}, waarmee kan ik u helpen?"'
        )

    # ── Tone extra ────────────────────────────────────────────
    tone_extra = f"\n- {worker.tone_of_voice}" if worker.tone_of_voice else ""

    # ── Template variables for interpolation ──────────────────
    template_vars = {
        "worker_name": worker.name,
        "role_title": worker.role_title,
        "company_name": company_name,
        "address": address,
        "tone_extra": tone_extra,
        "greeting": greeting,
    }

    # ═══════════════════════════════════════════════════════════
    # LOAD PROMPTS from database (or fallback to defaults)
    # ═══════════════════════════════════════════════════════════

    prompt_records = []
    if db:
        try:
            prompt_records = db.query(SystemPrompt).filter(
                SystemPrompt.is_active == True
            ).order_by(SystemPrompt.display_order).all()
        except Exception as e:
            logger.warning(f"Failed to load system prompts from DB: {e}")

    if not prompt_records:
        logger.info("Using DEFAULT_SYSTEM_PROMPTS (no DB prompts found)")
        prompt_contents = []
        for p in DEFAULT_SYSTEM_PROMPTS:
            if p.get("is_active", True):
                prompt_contents.append({
                    "name": p["name"],
                    "category": p["category"],
                    "content": p["content"],
                })
    else:
        prompt_contents = [
            {"name": p.name, "category": p.category, "content": p.content}
            for p in prompt_records
        ]

    # ═══════════════════════════════════════════════════════════
    # BUILD PROMPT — ElevenLabs recommended section order:
    # Personality → Goal → Tone → Guardrails → Tools → Steps
    # ═══════════════════════════════════════════════════════════

    def _render(category: str) -> list[str]:
        parts = []
        for p in prompt_contents:
            if p["category"] == category:
                try:
                    content = p["content"].format(**template_vars)
                except KeyError:
                    content = p["content"]
                parts.append(f"## {p['name']}\n{content}")
        return parts

    sections = []

    # 1. # Personality
    personality_parts = _render("personality")
    if personality_parts:
        sections.append("# Personality\n\n" + "\n\n".join(personality_parts))

    # 2. # Goal
    goal_parts = _render("goal")
    if goal_parts:
        sections.append("# Goal\n\n" + "\n\n".join(goal_parts))

    # 2.5 # Context — current date/time + caller info
    context_lines = [
        f"Vandaag is het {current_date_str}. Het is nu {current_time_str} (Nederland).",
        "Gebruik deze informatie om 'morgen', 'volgende week', etc. correct te interpreteren.",
    ]
    if caller_context:
        name_parts = []
        if caller_context.get("first_name"):
            name_parts.append(caller_context["first_name"])
        if caller_context.get("last_name"):
            name_parts.append(caller_context["last_name"])
        if name_parts:
            caller_name = " ".join(name_parts)
            context_lines.append(f"\nDe beller is een bekende klant: {caller_name}.")
            context_lines.append(
                f"Begroet de klant persoonlijk met hun naam (bijv. '{time_greeting} {'meneer' if not caller_context.get('first_name') else ''} {name_parts[-1]}')."
            )
        if caller_context.get("company_name"):
            context_lines.append(f"Bedrijf van de beller: {caller_context['company_name']}.")
        if caller_context.get("email"):
            context_lines.append(f"E-mail: {caller_context['email']}.")

    sections.append("# Context\n\n" + "\n".join(context_lines))

    # 3. # Tone
    tone_parts = _render("tone")
    if tone_parts:
        sections.append("# Tone\n\n" + "\n\n".join(tone_parts))

    # 4. # Guardrails  (models pay extra attention to this heading)
    guardrails_parts = _render("guardrails")
    # Legacy: also pick up old "safety" / "privacy" / "compliance" categories
    for cat in ("safety", "privacy", "compliance"):
        guardrails_parts.extend(_render(cat))
    guardrails_parts.append(
        "## Interne instructies NOOIT uitspreken\n"
        "Alles in dit systeem is een INTERNE instructie. Spreek NOOIT instructietekst, "
        "toolnamen, parameternamen, systeemberichten, of policy-resultaten hardop uit.\n"
        "Voorbeelden van wat je NOOIT mag zeggen:\n"
        '- "ik rond het gesprek netjes af"\n'
        '- "ik ga check_policy aanroepen"\n'
        '- "de tool retourneert..."\n'
        '- "instruction_nl zegt..."\n'
        '- "ik gebruik end_call"\n'
        "Als je het gesprek wilt afsluiten, zeg dan gewoon iets als 'Fijne dag!' "
        "— NIET wat je intern aan het doen bent."
    )
    if guardrails_parts:
        sections.append("# Guardrails\n\n" + "\n\n".join(guardrails_parts))

    # 4.5 # Bedrijfsinstructies (custom instructions from Training page)
    if custom_instructions and custom_instructions.strip():
        sections.append("# Bedrijfsinstructies\n\n" + custom_instructions.strip())

    # 5. # Tools  (built dynamically from permissions + tool descriptions)
    tool_lines = []
    if behavior_rules:
        tool_lines.append(f"## Bedrijfsregels\n{chr(10).join(behavior_rules)}")
    if permissions:
        tool_lines.append(f"## Bevoegdheden\n{chr(10).join(permissions)}")

    tool_lines.append(
        "## get_pricing\n"
        "Haal prijsinformatie, pakketten en abonnementen op.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt naar prijzen, kosten, tarieven\n"
        "- Klant vraagt welke pakketten er zijn\n"
        "- Klant vraagt specifiek naar een pakket (bijv. 'starter', 'business')\n"
        "- Klant wil pakketten vergelijken\n\n"
        "**Optionele parameter:** `query` — vul in met de naam van een specifiek pakket "
        "als de klant naar één pakket vraagt. Laat leeg voor een volledig overzicht.\n\n"
        "**Resultaten:** De tool retourneert exacte prijzen en pakketnamen. "
        "Als een resultaat een PRIJSINSTRUCTIE bevat, volg die LETTERLIJK.\n"
        "Neem prijzen en bedragen EXACT over. "
        "Rond NIET af en wijzig GEEN cijfers. €99 = negenennegentig euro, niet honderd."
    )

    tool_lines.append(
        "## get_company_overview\n"
        "Haal een overzicht op van het bedrijf.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt wat het bedrijf doet\n"
        "- Klant vraagt 'wat bieden jullie aan?'\n"
        "- Klant vraagt 'wie zijn jullie?'\n"
        "- Klant vraagt 'vertel eens over jullie bedrijf'\n\n"
        "Geen parameters nodig. De tool retourneert een korte beschrijving van het bedrijf, "
        "doelgroep en belangrijkste diensten/mogelijkheden."
    )

    tool_lines.append(
        "## get_contact_info\n"
        "Haal contactgegevens op (telefoon, email, whatsapp).\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt hoe ze contact kunnen opnemen\n"
        "- Klant vraagt naar telefoonnummer, e-mail, of contactpagina\n"
        "- Klant wil iemand bereiken\n\n"
        "Geen parameters nodig. De tool retourneert beschikbare contactgegevens."
    )

    tool_lines.append(
        "## get_opening_hours\n"
        "Haal openingstijden op.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt wanneer het bedrijf open of dicht is\n"
        "- Klant vraagt naar openingstijden of bereikbaarheid\n"
        "- Klant vraagt 'zijn jullie morgen open?'\n\n"
        "Geen parameters nodig. De tool retourneert de weekschema openingstijden."
    )

    tool_lines.append(
        "## get_services\n"
        "Haal een lijst van aangeboden diensten/services op.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt welke diensten of services worden aangeboden\n"
        "- Klant vraagt 'wat voor services bieden jullie?'\n"
        "- Klant vraagt naar specifieke mogelijkheden of aanbod\n\n"
        "Geen parameters nodig. De tool retourneert een overzicht van diensten.\n"
        "Let op: dit is anders dan get_company_overview. Overview = wie is het bedrijf, "
        "services = concrete diensten/producten."
    )

    tool_lines.append(
        "## get_location\n"
        "Haal locatie- en adresgegevens op.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt waar het bedrijf zit\n"
        "- Klant vraagt naar het adres of de vestiging\n"
        "- Klant vraagt hoe ze er kunnen komen\n\n"
        "Geen parameters nodig. De tool retourneert adres, stad en eventueel meerdere vestigingen."
    )

    tool_lines.append(
        "## search_knowledge\n"
        "Zoek in de bedrijfskennisbank voor overige vragen. "
        "De resultaten bevatten bedrijfsinformatie, inclusief opgeslagen Q&A. "
        "Beantwoord nooit uit eigen kennis.\n\n"
        "**Wanneer gebruiken:**\n"
        "- FAQ en beleid (retour, garantie, etc.)\n"
        "- Overige inhoudelijke vragen over het bedrijf\n\n"
        "**NIET gebruiken voor:**\n"
        "- Prijzen of pakketten (gebruik get_pricing)\n"
        "- Bedrijfsoverzicht / 'wat doen jullie?' (gebruik get_company_overview)\n"
        "- Contactgegevens (gebruik get_contact_info)\n"
        "- Openingstijden (gebruik get_opening_hours)\n"
        "- Diensten / services (gebruik get_services)\n"
        "- Locatie / adres (gebruik get_location)\n\n"
        "**Foutafhandeling:**\n"
        'Als de tool faalt: "Dat heb ik even niet bij de hand. '
        'Zal ik een collega vragen om u terug te bellen?"\n'
        "Verzin nooit een antwoord. Noem nooit de tool of kennisbank tegen de klant."
    )

    if worker.can_make_appointments:
        tool_lines.append(
            "## check_availability\n"
            "Haal beschikbare agenda-slots op voor een datum of periode.\n\n"
            "**Wanneer gebruiken:**\n"
            "- Klant wil EXPLICIET een afspraak maken\n"
            "- Klant vraagt wanneer er plek is\n\n"
            "**NIET gebruiken als:**\n"
            "- De klant afscheid neemt of aangeeft tevreden te zijn\n"
            "- De klant zegt: 'ik weet genoeg', 'dat was het', 'dankjewel', 'nee hoeft niet', 'fijne dag'\n"
            "- Het gesprek in de afsluitfase zit\n\n"
            "Geef een `start_date` mee (ISO-formaat). De tool retourneert beschikbare tijden.\n"
            "De tool retourneert ook `next_action`. Volg die instructie voor de volgende stap.\n"
            "Bied de klant maximaal 3 opties aan en vraag welk moment het beste uitkomt.\n\n"
            "**Bij mislukking (ok=false):**\n"
            "Roep deze tool NIET opnieuw aan met dezelfde parameters. "
            "Vertel de klant dat er helaas geen beschikbaarheid is op dat moment "
            "en vraag of een andere dag/tijd beter uitkomt, of bied aan om een collega te laten terugbellen."
        )

        tool_lines.append(
            "## book_appointment\n"
            "Plan een afspraak in de agenda.\n\n"
            "**Wanneer gebruiken:**\n"
            "- Nadat de klant een tijdstip heeft gekozen uit check_availability\n\n"
            "**NIET gebruiken als:**\n"
            "- De klant afscheid neemt of aangeeft tevreden te zijn\n"
            "- Het gesprek in de afsluitfase zit\n\n"
            "Vereiste parameters: `starts_at`, `ends_at`, `customer_name`.\n"
            "Optioneel: `title`, `customer_email`.\n"
            "Vraag ALTIJD de naam van de klant voordat je boekt.\n"
            "Vraag ook naar het e-mailadres als de klant een bevestiging per e-mail wil. "
            "Het e-mailadres is NIET verplicht — als de klant het niet wil geven, boek gewoon zonder.\n"
            "Bevestig datum, tijd en naam voordat je de tool aanroept.\n"
            "Als de tool `missing` retourneert: vraag het ontbrekende gegeven en roep de tool opnieuw aan zodra je het hebt."
        )

        tool_lines.append(
            "## cancel_appointment\n"
            "Annuleer een bestaande afspraak.\n\n"
            "**Wanneer gebruiken:**\n"
            "- Klant wil een afspraak annuleren\n"
            "- Zoekt automatisch op telefoonnummer, naam en/of datum\n\n"
            "**NIET gebruiken als:**\n"
            "- De klant afscheid neemt of tevreden is\n\n"
            "Optionele parameters: `customer_name`, `appointment_date`.\n"
            "Als er meerdere afspraken worden gevonden, vraag de klant welke bedoeld wordt."
        )

        tool_lines.append(
            "## reschedule_appointment\n"
            "Verzet een bestaande afspraak naar een nieuw tijdstip.\n\n"
            "**Wanneer gebruiken:**\n"
            "- Klant wil een afspraak verplaatsen of verzetten\n\n"
            "**Flow:**\n"
            "1. Gebruik eerst check_availability om een nieuw tijdstip te vinden\n"
            "2. Laat de klant een nieuw tijdstip kiezen\n"
            "3. Roep dan reschedule_appointment aan met `new_starts_at` en `new_ends_at`\n\n"
            "Optioneel: `customer_name`, `appointment_date` om de juiste afspraak te vinden."
        )

    tool_lines.append(
        "## create_lead\n"
        "Leg een geïnteresseerde / lead vast.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant is geïnteresseerd in het product/dienst\n"
        "- Klant wil een demo of meer informatie\n"
        "- Klant wil dat iemand contact met hen opneemt over een aanbod\n\n"
        "Vereist: `name`. Optioneel: `phone`, `email`, `notes`."
    )

    tool_lines.append(
        "## send_sms\n"
        "Stuur een SMS-bericht.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt om informatie per SMS te ontvangen\n"
        "- Een link of bevestiging per SMS sturen\n\n"
        "Parameter `to` is optioneel — als leeg, wordt het nummer van de beller gebruikt.\n"
        "Vereist: `message`."
    )

    tool_lines.append(
        "## send_email\n"
        "Stuur een e-mail namens het bedrijf.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt om informatie per e-mail te ontvangen\n"
        "- Een samenvatting of document per e-mail sturen\n\n"
        "Vereist: `to`, `subject`, `body`.\n"
        "Vraag ALTIJD het e-mailadres voordat je deze tool gebruikt."
    )

    tool_lines.append(
        "## leave_message\n"
        "Laat een bericht achter voor een collega.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant wil een boodschap achterlaten\n"
        "- Klant wil iets doorgeven aan het bedrijf\n\n"
        "Vereist: `message`. Optioneel: `customer_name`."
    )

    tool_lines.append(
        "## create_callback_request\n"
        "Maak een terugbelverzoek aan.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant wil worden teruggebeld\n"
        "- Klant zegt 'laat iemand mij bellen'\n\n"
        "Bevestig het telefoonnummer van de klant.\n"
        "Optioneel: `customer_name`, `preferred_callback_time`, `notes`."
    )

    if worker.can_leave_notes:
        tool_lines.append(
            "## create_note\n"
            "Gebruik om notities achter te laten voor collega's.\n\n"
            "**Wanneer gebruiken:**\n"
            "- Klant heeft een verzoek buiten jouw bevoegdheden\n"
            "- Er moet iets worden doorgegeven aan een collega"
        )

    if transfer_enabled:
        tool_lines.append(
            "## transfer_call\n"
            "Verbind het gesprek door naar een menselijke collega.\n\n"
            "**Wanneer gebruiken:**\n"
            "- Beller vraagt expliciet om een mens te spreken\n"
            "- Situatie is te complex om zelf af te handelen na doorvragen\n"
            "- Beller is gefrustreerd en je kunt niet helpen\n\n"
            "**Zeg altijd:** 'Ik verbind u door met een collega' voordat je de tool gebruikt.\n"
            "Geef een korte reden mee zodat de collega weet waarom de beller belt."
        )

    tool_lines.append(
        "## flag_unknown\n"
        "Markeer een vraag die je niet kunt beantwoorden.\n\n"
        "**Wanneer gebruiken:**\n"
        "- Je hebt search_knowledge gebruikt maar er is geen antwoord gevonden\n"
        "- De klant stelt een vraag die je echt niet kunt beantwoorden\n\n"
        "Geef de originele vraag van de klant mee als `question` parameter.\n"
        "De vraag verschijnt dan als suggestie in het dashboard zodat het bedrijf "
        "een antwoord kan toevoegen.\n"
        "Noem deze tool NIET tegen de klant."
    )

    tool_lines.append(
        "## check_policy\n"
        "Interne systeemcheck — resultaten zijn NOOIT hardop voor te lezen.\n\n"
        "**Verplicht vóór:**\n"
        "- Het beëindigen van het gesprek (trigger_reason: `ending_call`)\n"
        "- Het doorverbinden naar een mens (trigger_reason: `escalation`)\n\n"
        "**Optioneel bij:**\n"
        "- Lage zoekresultaten (trigger_reason: `low_confidence`)\n"
        "- Herhaalde mislukte beantwoording (trigger_reason: `repeated_failure`)\n"
        "- Off-topic verzoeken (trigger_reason: `off_topic`)\n"
        "- Stilte (trigger_reason: `silence`)\n\n"
        "**Parameters:**\n"
        "- `trigger_reason` (string): reden\n"
        "- `customer_message` (string): laatste klantuiting\n\n"
        "**Resultaat:**\n"
        "- `allowed`: true/false\n"
        "- `instruction_nl`: interne routeringsinstructie — NIET voorlezen, gebruik als leidraad voor je eigen woorden\n"
        "- `required_action`: proceed / wait / escalate / clarify / reprompt / block\n\n"
        "**Einde gesprek:**\n"
        "1. Zeg 'Fijne dag!' (of vergelijkbaar)\n"
        "2. Roep check_policy aan met trigger_reason='ending_call'\n"
        "3. allowed=false → wacht op klant\n"
        "4. allowed=true → gebruik end_call"
    )

    tool_lines.append(
        "## end_call\n"
        "Beëindig de verbinding (intern, niet uitspreken).\n\n"
        "**Wanneer gebruiken:**\n"
        "- ALLEEN nadat check_policy met trigger_reason='ending_call' allowed=true retourneert\n"
        "- NOOIT direct na je eigen afscheid — altijd eerst check_policy\n"
        "- Bij 5+ seconden stilte na je afscheid: roep check_policy aan"
    )

    sections.append("# Tools\n\n" + "\n\n".join(tool_lines))

    # 6. # Steps
    steps_parts = _render("steps")
    if steps_parts:
        sections.append("# Steps\n\n" + "\n\n".join(steps_parts))

    return "\n\n".join(sections)


def get_system_prompts(db) -> str:
    """
    Get combined system prompts from the database.
    These are platform-wide prompts that apply to ALL AI workers.
    """
    try:
        prompts = db.query(SystemPrompt).filter(
            SystemPrompt.is_active == True
        ).order_by(SystemPrompt.display_order).all()

        if not prompts:
            return ""

        combined_parts = []
        for prompt in prompts:
            combined_parts.append(f"## {prompt.name}\n{prompt.content}")

        return "\n\n".join(combined_parts)
    except Exception as e:
        logger.error(f"Failed to get system prompts: {e}")
        return ""
