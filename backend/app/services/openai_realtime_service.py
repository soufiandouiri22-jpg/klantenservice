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

    ams_hour = _dt.now(ZoneInfo("Europe/Amsterdam")).hour
    if ams_hour < 12:
        time_greeting = "Goedemorgen"
    elif ams_hour < 18:
        time_greeting = "Goedemiddag"
    else:
        time_greeting = "Goedenavond"

    formatted_disclosure = ""
    if disclosure_message:
        try:
            formatted_disclosure = disclosure_message.format(
                greeting=time_greeting,
                company_name=company_name,
                ai_worker_name=worker.name,
            )
        except KeyError:
            formatted_disclosure = disclosure_message.format(
                company_name=company_name,
                ai_worker_name=worker.name,
            )

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

    # 3. # Tone
    tone_parts = _render("tone")
    if tone_parts:
        sections.append("# Tone\n\n" + "\n\n".join(tone_parts))

    # 4. # Guardrails  (models pay extra attention to this heading)
    guardrails_parts = _render("guardrails")
    # Legacy: also pick up old "safety" / "privacy" / "compliance" categories
    for cat in ("safety", "privacy", "compliance"):
        guardrails_parts.extend(_render(cat))
    if guardrails_parts:
        sections.append("# Guardrails\n\n" + "\n\n".join(guardrails_parts))

    # 5. # Tools  (built dynamically from permissions + tool descriptions)
    tool_lines = []
    if behavior_rules:
        tool_lines.append(f"## Bedrijfsregels\n{chr(10).join(behavior_rules)}")
    if permissions:
        tool_lines.append(f"## Bevoegdheden\n{chr(10).join(permissions)}")

    tool_lines.append(
        "## search_knowledge\n"
        "Gebruik voor inhoudelijke vragen over het bedrijf "
        "(prijzen, diensten, openingstijden, locatie, etc.).\n\n"
        "**Wanneer gebruiken:**\n"
        "- Klant vraagt over prijzen, diensten, openingstijden\n"
        "- Klant stelt een vraag die je niet direct kunt beantwoorden\n\n"
        "**Foutafhandeling:**\n"
        'Als de tool faalt: "Dat heb ik even niet bij de hand. '
        'Zal ik een collega vragen om u terug te bellen?"\n'
        "Verzin nooit een antwoord. Noem nooit de tool of kennisbank tegen de klant."
    )

    if worker.can_leave_notes:
        tool_lines.append(
            "## create_note\n"
            "Gebruik om notities achter te laten voor collega's.\n\n"
            "**Wanneer gebruiken:**\n"
            "- Klant heeft een verzoek buiten jouw bevoegdheden\n"
            "- Er moet iets worden doorgegeven aan een collega"
        )

    tool_lines.append(
        "## end_call\n"
        "Gebruik om het gesprek netjes te beëindigen.\n\n"
        "**Wanneer gebruiken:**\n"
        "- ALLEEN nadat de klant heeft teruggegroet na jouw afscheid (bijv. klant zegt \"Dag!\", \"Doei\", \"Bedankt\", \"Goedenavond\")\n"
        "- Zodra de klant teruggroet: zeg NIETS meer, gebruik DIRECT end_call. Niet nog een keer groeten.\n"
        "- NOOIT direct na jouw eigen afscheid — altijd wachten op de klant\n"
        "- Bij 5+ seconden stilte na je afscheid mag je end_call gebruiken"
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
