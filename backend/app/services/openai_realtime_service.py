"""
klantenservice.ai - System Prompt Builder

Builds the system instructions for AI voice agents. Used by the ElevenLabs
Conversational AI integration (via register-call overrides).

All prompt sections are loaded from the database (SystemPrompt model) and
interpolated with runtime variables. Admins can edit every part of the AI's
personality, tone, and behavior via the admin panel.
"""
import logging
from typing import List, Optional

from app.core.config import get_settings
from app.models.ai_worker import AIWorker, AddressForm
from app.models.system_prompt import SystemPrompt

settings = get_settings()
logger = logging.getLogger(__name__)


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
    Build system instructions for the OpenAI Realtime session.

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

    # ── Example Q&A ───────────────────────────────────────────
    # NOTE: Example answers are NOT included in the system prompt to keep it
    # short and reduce latency.  The AI retrieves them via the search_knowledge
    # tool at runtime when a relevant question is asked.
    example_section = ""

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

    # ── Opening ───────────────────────────────────────────────
    if formatted_disclosure:
        greeting = f'Begin ALTIJD met: "{formatted_disclosure}"'
    else:
        greeting = f'Begin ALTIJD met: "{time_greeting}, met {worker.name} van {company_name}, waarmee kan ik u helpen?"'

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

    # Fallback to defaults if DB is empty or unavailable
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
    # BUILD PROMPT — group by category
    # ═══════════════════════════════════════════════════════════

    sections = []

    # Group: Personality (personality category)
    personality_parts = []
    for p in prompt_contents:
        if p["category"] == "personality":
            try:
                content = p["content"].format(**template_vars)
            except KeyError:
                content = p["content"]
            personality_parts.append(f"## {p['name']}\n{content}")

    if personality_parts:
        sections.append("# Personality and Tone\n\n" + "\n\n".join(personality_parts))

    # Group: Steps (steps category)
    steps_parts = []
    for p in prompt_contents:
        if p["category"] == "steps":
            try:
                content = p["content"].format(**template_vars)
            except KeyError:
                content = p["content"]
            steps_parts.append(f"## {p['name']}\n{content}")

    if steps_parts:
        sections.append("# Steps\n\n" + "\n\n".join(steps_parts))

    # Group: Safety & Compliance (safety, privacy, compliance categories)
    safety_parts = []
    for p in prompt_contents:
        if p["category"] in ("safety", "privacy", "compliance"):
            try:
                content = p["content"].format(**template_vars)
            except KeyError:
                content = p["content"]
            safety_parts.append(f"## {p['name']}\n{content}")

    if safety_parts:
        sections.append("# Safety & Compliance\n\n" + "\n\n".join(safety_parts))

    # ── Dynamic Context (not from system prompts) ─────────────
    context_parts = []

    if behavior_rules:
        context_parts.append(f"## Bedrijfsregels\n{chr(10).join(behavior_rules)}")
    if permissions:
        context_parts.append(f"## Bevoegdheden\n{chr(10).join(permissions)}")

    context_parts.append(
        "## Tools\n"
        "Gebruik search_knowledge voor inhoudelijke vragen over het bedrijf "
        "(prijzen, diensten, openingstijden, locatie, etc.). "
        "Als de tool niet beschikbaar is, zeg dat je het even niet kunt "
        "opzoeken en vraag of de beller later kan terugbellen. Nooit gokken."
    )

    if context_parts:
        sections.append("# Context\n\n" + "\n\n".join(context_parts))

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
