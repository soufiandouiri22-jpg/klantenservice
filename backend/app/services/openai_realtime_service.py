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
from app.models.business_facts import (
    CompanyOverview, PricingPlan, ContactInfo, OpeningHours,
    BusinessLocation, BusinessService,
)

settings = get_settings()
logger = logging.getLogger(__name__)

_WEEKDAY_NAMES = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]


def prefetch_company_context(db, company_id: str) -> str:
    """
    Pre-fetch static company data (overview, pricing, hours, contact, services,
    location) and return as a compact text block for injection into the prompt.
    Eliminates tool calls for common questions, saving ~800ms per avoided call.
    """
    parts = []

    overview = db.query(CompanyOverview).filter_by(company_id=company_id).first()
    if overview:
        lines = [f"Bedrijf: {overview.summary}"]
        if overview.capabilities and isinstance(overview.capabilities, list):
            lines.append("Mogelijkheden: " + ", ".join(overview.capabilities[:8]))
        if overview.target_audience:
            lines.append(f"Doelgroep: {overview.target_audience}")
        parts.append("\n".join(lines))

    plans = (
        db.query(PricingPlan)
        .filter_by(company_id=company_id)
        .order_by(PricingPlan.display_order)
        .all()
    )
    if plans:
        plan_lines = []
        for p in plans:
            if p.price_type == "fixed" and p.price is not None:
                price = f"\u20ac{int(p.price)}" if p.price == int(p.price) else f"\u20ac{p.price}"
                period = f"/{p.billing_period}" if p.billing_period else ""
                feat_str = ""
                if p.features and isinstance(p.features, list):
                    feat_str = " (" + ", ".join(p.features[:5]) + ")"
                plan_lines.append(f"{p.name}: {price}{period}{feat_str}")
            elif p.price_type == "free":
                plan_lines.append(f"{p.name}: Gratis")
            elif p.price_type == "contact_required":
                plan_lines.append(f"{p.name}: Prijs op aanvraag")
        parts.append("Pakketten:\n" + "\n".join(plan_lines))

    hours = (
        db.query(OpeningHours)
        .filter_by(company_id=company_id)
        .order_by(OpeningHours.weekday)
        .all()
    )
    if hours:
        hour_parts = []
        for h in hours:
            day = _WEEKDAY_NAMES[h.weekday] if 0 <= h.weekday <= 6 else f"Dag {h.weekday}"
            if h.closed:
                hour_parts.append(f"{day}: gesloten")
            elif h.open_time and h.close_time:
                hour_parts.append(f"{day}: {h.open_time.strftime('%H:%M')}-{h.close_time.strftime('%H:%M')}")
        parts.append("Openingstijden: " + " | ".join(hour_parts))

    contacts = db.query(ContactInfo).filter_by(company_id=company_id).all()
    if contacts:
        c_parts = []
        for c in contacts:
            if c.phone:
                c_parts.append(f"Tel: {c.phone}")
            if c.email:
                c_parts.append(f"E-mail: {c.email}")
        if c_parts:
            parts.append("Contact: " + ", ".join(c_parts))

    services = db.query(BusinessService).filter_by(company_id=company_id).all()
    if services:
        svc_names = [s.name for s in services[:10]]
        parts.append("Diensten: " + ", ".join(svc_names))

    locations = db.query(BusinessLocation).filter_by(company_id=company_id).all()
    if locations:
        loc_parts = []
        for loc in locations:
            loc_str = ", ".join(x for x in [loc.name, loc.address, loc.city] if x)
            if loc_str:
                loc_parts.append(loc_str)
        if loc_parts:
            parts.append("Locatie: " + " | ".join(loc_parts))

    result = "\n".join(parts)
    if result:
        logger.info("[prefetch] Loaded %d chars of company context for %s", len(result), company_id)
    return result


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
    company_context: Optional[str] = None,
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

    if company_context:
        context_lines.append(f"\n{company_context}")

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
    # "Interne instructies NOOIT uitspreken" is now part of guardrails_all
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
        "BELANGRIJK: Gebruik ALTIJD eerst de bedrijfsgegevens uit # Context. "
        "Roep onderstaande info-tools ALLEEN aan als de klant specifiek iets vraagt "
        "dat NIET in Context staat."
    )

    tool_lines.append(
        "## get_pricing\n"
        "Prijzen ophalen. Param: `query` (optioneel, pakketnaam).\n"
        "Volg PRIJSINSTRUCTIES letterlijk. Alleen als Context onvoldoende is."
    )

    tool_lines.append(
        "## get_company_overview\n"
        "Bedrijfsoverzicht. Alleen als Context onvoldoende is."
    )

    tool_lines.append(
        "## get_contact_info\n"
        "Contactgegevens. Alleen als Context onvoldoende is."
    )

    tool_lines.append(
        "## get_opening_hours\n"
        "Openingstijden. Alleen als Context onvoldoende is."
    )

    tool_lines.append(
        "## get_services\n"
        "Diensten. Alleen als Context onvoldoende is."
    )

    tool_lines.append(
        "## get_location\n"
        "Adres/vestigingen. Alleen als Context onvoldoende is."
    )

    tool_lines.append(
        "## search_knowledge\n"
        "Zoek in kennisbank voor FAQ, beleid en overige vragen. Beantwoord nooit uit eigen kennis.\n"
        "Niet voor info die al in Context staat.\n"
        "Param: `query`. Bij falen: bied terugbelverzoek aan."
    )

    if worker.can_make_appointments:
        tool_lines.append(
            "## check_availability\n"
            "Haal beschikbare agenda-slots op. Param: `start_date` (ISO).\n"
            "Bied max 3 opties aan. Volg `next_action` uit het resultaat.\n"
            "Bij ok=false: niet opnieuw met dezelfde params, vraag andere datum."
        )

        tool_lines.append(
            "## book_appointment\n"
            "Plan afspraak in. Params: `starts_at`, `ends_at`, `customer_name`. Optioneel: `title`, `customer_email`.\n"
            "Vraag altijd naam. Bevestig datum+tijd+naam voordat je boekt.\n"
            "E-mail is niet verplicht. Bij `missing`: vraag ontbrekend gegeven."
        )

        tool_lines.append(
            "## cancel_appointment\n"
            "Annuleer afspraak. Optioneel: `customer_name`, `appointment_date`.\n"
            "Bij meerdere matches: vraag welke bedoeld wordt."
        )

        tool_lines.append(
            "## reschedule_appointment\n"
            "Verzet afspraak. Gebruik eerst check_availability, laat klant kiezen, dan aanroepen.\n"
            "Params: `new_starts_at`, `new_ends_at`. Optioneel: `customer_name`, `appointment_date`."
        )

    tool_lines.append(
        "## create_lead\n"
        "Leg geïnteresseerde vast. Vereist: `name`. Optioneel: `phone`, `email`, `notes`."
    )

    tool_lines.append(
        "## send_sms\n"
        "Stuur SMS. Vereist: `message`. `to` optioneel (default: bellernummer)."
    )

    tool_lines.append(
        "## send_email\n"
        "Stuur e-mail. Vereist: `to` (e.g. 'john@company.com'), `subject`, `body`.\n"
        "Vraag altijd e-mailadres en bevestig door langzaam te spellen voordat je stuurt."
    )

    tool_lines.append(
        "## leave_message\n"
        "Laat bericht achter. Vereist: `message`. Optioneel: `customer_name`."
    )

    tool_lines.append(
        "## create_callback_request\n"
        "Maak terugbelverzoek. Bevestig telefoonnummer.\n"
        "Optioneel: `customer_name`, `preferred_callback_time`, `notes`."
    )

    if worker.can_leave_notes:
        tool_lines.append(
            "## create_note\n"
            "Notitie voor collega's. Bij verzoeken buiten jouw bevoegdheden."
        )

    if transfer_enabled:
        tool_lines.append(
            "## transfer_call\n"
            "Verbind door naar mens. Zeg 'Ik verbind u door' voordat je de tool gebruikt.\n"
            "Geef korte reden mee. Gebruik bij: expliciete vraag om mens, te complex, of gefrustreerde beller."
        )

    tool_lines.append(
        "## flag_unknown\n"
        "Markeer onbeantwoordbare vraag. Param: `question`. Noem deze tool niet tegen de klant."
    )

    # check_policy and end_call removed — end_call is a built-in ElevenLabs system tool,
    # check_policy was never registered in ElevenLabs. Afscheid rules are in guardrails.

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
