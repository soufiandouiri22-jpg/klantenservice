"""
Output Guardrails — validates AI output before it reaches speech.

Checks for:
- Language violations (non-Dutch output)
- Prompt leakage (system instructions bleeding into response)
- Tool leakage (tool names, function calls)
- JSON/code leakage (objects, arrays, markdown fences)
- HTML/script fragments
- Malformed/debug text

Returns a safe Dutch fallback if any check fails.
Every violation is logged structurally.
"""
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List

logger = logging.getLogger(__name__)


class ViolationType(str, Enum):
    PROMPT_LEAKAGE = "prompt_leakage"
    TOOL_LEAKAGE = "tool_leakage"
    JSON_LEAKAGE = "json_leakage"
    LANGUAGE_VIOLATION = "language_violation"
    MALFORMED_OUTPUT = "malformed_output"
    HTML_OR_SCRIPT = "html_or_script_leakage"


@dataclass
class GuardrailResult:
    passed: bool
    violations: List[ViolationType]
    original_text: str
    safe_text: str
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "violations": [v.value for v in self.violations],
            "safe_text": self.safe_text,
            "details": self.details,
        }


SAFE_FALLBACK_NL = (
    "Excuses, er ging iets mis. Kunt u uw vraag nog eens herhalen?"
)

# ── English filler phrases that must never reach TTS ─────────────
# Matched case-insensitively as standalone phrases (start of sentence
# or after punctuation). Replacements are neutral Dutch alternatives.
_ENGLISH_FILLER_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'(?<![a-zA-Z])I hear you\.?(?![a-zA-Z])', re.I), ''),
    (re.compile(r'(?<![a-zA-Z])I understand\.?(?![a-zA-Z])', re.I), ''),
    (re.compile(r'(?<![a-zA-Z])Got it\.?(?![a-zA-Z])', re.I), ''),
    (re.compile(r'(?<![a-zA-Z])Right\.?(?![a-zA-Z])', re.I), ''),
    (re.compile(r'(?<![a-zA-Z])Sure\.?(?![a-zA-Z])', re.I), ''),
    (re.compile(r'(?<![a-zA-Z])Absolutely\.?(?![a-zA-Z])', re.I), ''),
    (re.compile(r'(?<![a-zA-Z])Okay\.?(?![a-zA-Z])', re.I), ''),
]


def _strip_english_fillers(text: str) -> tuple[str, list[str]]:
    """Remove banned English filler phrases. Returns cleaned text and list of removed phrases."""
    removed: list[str] = []
    for pattern, replacement in _ENGLISH_FILLER_PATTERNS:
        match = pattern.search(text)
        if match:
            removed.append(match.group().strip())
            text = pattern.sub(replacement, text)
    text = re.sub(r'[ ]{2,}', ' ', text).strip()
    text = re.sub(r'^[,.\s]+', '', text).strip()
    return text, removed

SAFE_FALLBACK_LANGUAGE = (
    "Excuses, dat ging niet helemaal goed. "
    "Kunt u uw vraag nog één keer stellen?"
)


# ── Prompt leakage patterns ──────────────────────────────────────

_PROMPT_LEAKAGE_RE = re.compile(
    r"("
    r"system\s*prompt|system\s*instruction|"
    r"je\s+bent\s+een\s+AI|you\s+are\s+an?\s+AI|"
    r"as\s+an?\s+(?:AI|language\s+model|assistant)|"
    r"i\s+am\s+an?\s+(?:AI|language\s+model)|"
    r"my\s+(?:instructions|system\s+prompt|training)|"
    r"mijn\s+(?:instructies|systeem\s*prompt|training\s*data)|"
    r"#\s*(?:personality|goal|tone|guardrails|tools|steps)\b|"
    r"\bBELANGRIJKE?\s+REGELS\b|"
    r"\bROLE:\s|USER:\s|ASSISTANT:\s|SYSTEM:\s"
    r")",
    re.I,
)

# ── Tool leakage patterns ────────────────────────────────────────

_TOOL_LEAKAGE_RE = re.compile(
    r"("
    r"search_knowledge|check_availability|book_appointment|"
    r"create_note|flag_unknown|transfer_call|check_policy|"
    r"end_call|get_prices|"
    r"tool_call|function_call|tool_result|"
    r"kennisbank|knowledge\s*base|retrieval\s*pipeline|"
    r"tool\s+result|tool\s+response|"
    r"\btrigger_reason\b|\brequired_action\b|\breason_code\b"
    r")",
    re.I,
)

# ── JSON / code leakage ─────────────────────────────────────────

_JSON_LEAKAGE_RE = re.compile(
    r'(?:'
    r'\{["\']?\w+["\']?\s*:|'        # {"key": or {'key':
    r'\[\s*\{|'                       # [{ array of objects
    r'\[\s*"[^"]+"\s*,|'             # ["item1", ... raw JSON string arrays
    r'```|'                           # markdown code fence
    r'"ok"\s*:\s*(?:true|false)|'     # "ok": true
    r'"results"\s*:\s*\[|'            # "results": [
    r'"message"\s*:\s*"'              # "message": "
    r')',
    re.I,
)

# ── HTML / script fragments ──────────────────────────────────────

_HTML_LEAKAGE_RE = re.compile(
    r'(?:'
    r'<(?:script|style|div|span|html|body|head|p|a|img|iframe)\b|'
    r'</(?:script|style|div|span|html|body|head|p|a)\b|'
    r'<!\-\-|'
    r'javascript:|onclick=|onerror='
    r')',
    re.I,
)

# ── Malformed output patterns ────────────────────────────────────

_MALFORMED_RE = re.compile(
    r'(?:'
    r'^\s*(?:None|null|undefined|NaN|Error|Traceback)\s*$|'
    r'^\s*\{?\s*\}?\s*$|'            # empty braces or whitespace only
    r'(?:File|Line)\s+"\S+",\s+line\s+\d+|'  # Python tracebacks
    r'Traceback\s*\(most\s+recent'
    r')',
    re.I | re.M,
)

# ── Language detection (Dutch vs non-Dutch) ──────────────────────

# Common Dutch function words that appear in virtually any Dutch sentence
_DUTCH_MARKERS = re.compile(
    r'\b(?:'
    r'de|het|een|van|in|is|dat|die|op|aan|met|er|voor|niet|zijn|'
    r'ze|maar|dan|nog|als|ook|kan|wel|ik|je|u|we|ze|hij|zij|'
    r'dit|wat|bij|naar|uit|meer|al|zo|om|door|geen|waar|hoe|'
    r'goed|graag|bedankt|alstublieft|meneer|mevrouw|'
    r'ja|nee|hallo|dank|excuses|sorry'
    r')\b',
    re.I,
)

# Common English function words that should not dominate Dutch output
_ENGLISH_MARKERS = re.compile(
    r'\b(?:'
    r'the|is|are|was|were|have|has|had|will|would|could|should|'
    r'this|that|these|those|which|what|where|when|how|why|'
    r'with|from|into|about|after|before|between|through|'
    r'your|their|our|its|my|his|her|'
    r'here|there|now|then|also|just|only|very|much|'
    r'I\s+(?:am|can|will|would|have|don\'t|think|hear|understand)|'
    r'you\s+(?:are|can|will|have|need)|'
    r'please|thank|sorry|hello|goodbye|welcome|'
    r'unfortunately|however|therefore|moreover'
    r')\b',
    re.I,
)


def _check_language(text: str) -> Optional[ViolationType]:
    """
    Check if text is primarily Dutch. Returns LANGUAGE_VIOLATION if
    English content dominates, None if OK.
    """
    words = text.split()
    if len(words) < 3:
        return None

    dutch_count = len(_DUTCH_MARKERS.findall(text))
    english_count = len(_ENGLISH_MARKERS.findall(text))
    total_words = len(words)

    # If English markers outnumber Dutch markers significantly
    if english_count > dutch_count and english_count >= 3:
        english_ratio = english_count / total_words
        if english_ratio > 0.25:
            return ViolationType.LANGUAGE_VIOLATION

    # If no Dutch markers at all in a substantial response
    if dutch_count == 0 and total_words >= 5:
        return ViolationType.LANGUAGE_VIOLATION

    return None


# ── Main validation function ─────────────────────────────────────


def validate_output(text: str) -> GuardrailResult:
    """
    Validate AI output before it reaches speech synthesis.

    Returns GuardrailResult with passed=True if all checks pass,
    or passed=False with violations list and safe fallback text.
    """
    if not text or not text.strip():
        return GuardrailResult(
            passed=False,
            violations=[ViolationType.MALFORMED_OUTPUT],
            original_text=text or "",
            safe_text=SAFE_FALLBACK_NL,
            details="Empty or whitespace-only output",
        )

    original_text = text

    # Strip banned English filler phrases before all other checks
    text, removed_fillers = _strip_english_fillers(text)
    if removed_fillers:
        logger.info(
            "[output_guardrails] Stripped English fillers: %s from: %r",
            removed_fillers, original_text[:200],
        )

    if not text.strip():
        return GuardrailResult(
            passed=True,
            violations=[],
            original_text=original_text,
            safe_text="Even kijken...",
            details=f"stripped_fillers={removed_fillers}; remainder empty",
        )

    violations: List[ViolationType] = []
    details_parts: List[str] = []
    if removed_fillers:
        details_parts.append(f"stripped_fillers={removed_fillers}")

    # 1. Prompt leakage
    if _PROMPT_LEAKAGE_RE.search(text):
        violations.append(ViolationType.PROMPT_LEAKAGE)
        match = _PROMPT_LEAKAGE_RE.search(text)
        details_parts.append(f"prompt_leak: '{match.group()[:50]}'")

    # 2. Tool leakage
    if _TOOL_LEAKAGE_RE.search(text):
        violations.append(ViolationType.TOOL_LEAKAGE)
        match = _TOOL_LEAKAGE_RE.search(text)
        details_parts.append(f"tool_leak: '{match.group()[:50]}'")

    # 3. JSON/code leakage
    if _JSON_LEAKAGE_RE.search(text):
        violations.append(ViolationType.JSON_LEAKAGE)
        details_parts.append("json_or_code_fragment_detected")

    # 4. HTML/script
    if _HTML_LEAKAGE_RE.search(text):
        violations.append(ViolationType.HTML_OR_SCRIPT)
        details_parts.append("html_or_script_detected")

    # 5. Malformed
    if _MALFORMED_RE.search(text):
        violations.append(ViolationType.MALFORMED_OUTPUT)
        details_parts.append("malformed_output_detected")

    # 6. Language check
    lang_violation = _check_language(text)
    if lang_violation:
        violations.append(lang_violation)
        details_parts.append("non_dutch_output_detected")

    if violations:
        # Choose appropriate fallback
        safe_text = (
            SAFE_FALLBACK_LANGUAGE
            if ViolationType.LANGUAGE_VIOLATION in violations
            else SAFE_FALLBACK_NL
        )

        logger.warning(
            "[output_guardrails] BLOCKED: violations=%s text=%r",
            [v.value for v in violations],
            original_text[:200],
        )

        return GuardrailResult(
            passed=False,
            violations=violations,
            original_text=original_text[:2000],
            safe_text=safe_text,
            details="; ".join(details_parts),
        )

    return GuardrailResult(
        passed=True,
        violations=[],
        original_text=original_text,
        safe_text=text,
    )
