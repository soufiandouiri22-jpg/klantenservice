"""
Intent classifier — deterministic, regex-first classification of caller
utterances for the voice pipeline.

Runs on every server tool call to classify the latest customer message.
Designed for Dutch; patterns cover common phrasings and variations.
"""
import re
from enum import Enum
from typing import Tuple

_cache: dict[str, Tuple[str, float]] = {}


class CallerIntent(str, Enum):
    GREETING = "greeting"
    GOODBYE = "goodbye"
    QUESTION = "question"
    PRICING = "pricing"
    APPOINTMENT = "appointment"
    COMPLAINT = "complaint"
    ANGER = "anger"
    TRANSFER_REQUEST = "transfer_request"
    CONFIRMATION = "confirmation"
    DENIAL = "denial"
    GRATITUDE = "gratitude"
    UNCLEAR = "unclear"
    SILENCE = "silence"
    OFF_TOPIC = "off_topic"


_RULES: list[tuple[re.Pattern, CallerIntent, float]] = [
    # Silence / empty
    (re.compile(r"^\s*$"), CallerIntent.SILENCE, 0.99),

    # Goodbye — must come before greeting (overlapping words)
    (re.compile(
        r"\b(doei|tot\s*ziens|tot\s*snel|tot\s*de\s+volgende|"
        r"fijne\s+dag|fijne\s+avond|prettige\s+dag|prettige\s+avond|"
        r"goedenacht|lekker\s+weekend|"
        r"dag!?$|daag!?$|bye|goodbye|tot\s+later)\b",
        re.I,
    ), CallerIntent.GOODBYE, 0.95),

    # Anger / frustration — strong signals
    (re.compile(
        r"\b(boos|kwaad|woedend|onacceptabel|belachelijk|schande|schandalig|"
        r"klacht\s*indienen|klacht|aanklacht|advocaat|rechter|juridisch|"
        r"fuck|shit|godverdomme|kut|kanker|tyfus|tering|"
        r"rotzooi|waardeloos|verschrikkelijk|vreselijk|"
        r"nooit\s+meer|oplichter|oplichting|zwendel|bedrog|"
        r"dit\s+kan\s+niet|dit\s+pik\s+ik\s+niet|ik\s+ben\s+het\s+zat)\b",
        re.I,
    ), CallerIntent.ANGER, 0.90),

    # Complaint — softer frustration
    (re.compile(
        r"\b(niet\s+tevreden|ontevreden|teleurgesteld|tegenvalt|"
        r"probleem|fout|verkeerd|kapot|stuk|defect|beschadigd|"
        r"te\s+lang\s+wacht|al\s+\d+\s+keer\s+gebeld|steeds\s+weer|"
        r"niet\s+opgelost|gaat\s+fout|werkt\s+niet|lukt\s+niet)\b",
        re.I,
    ), CallerIntent.COMPLAINT, 0.85),

    # Transfer to human
    (re.compile(
        r"\b(echte?\s+persoon|echte?\s+mens|echte?\s+medewerker|"
        r"iemand\s+anders|collega|leidinggevende|manager|supervisor|chef|"
        r"doorverbind|verbind\s*door|menselijk|een\s+mens|"
        r"geen\s+computer|geen\s+robot|geen\s+machine|"
        r"ik\s+wil\s+iemand\s+spreken)\b",
        re.I,
    ), CallerIntent.TRANSFER_REQUEST, 0.92),

    # Greeting
    (re.compile(
        r"^(hallo|hoi|hey|goedemorgen|goedemiddag|goedenavond|"
        r"goedendag|ja\s+hallo|he+y)\b",
        re.I,
    ), CallerIntent.GREETING, 0.90),

    # Confirmation
    (re.compile(
        r"^(ja\s*(?:graag|zeker|dat\s+klopt|precies|inderdaad|goed|prima|top|"
        r"doe\s+maar|is\s+goed|akkoord|ok[eé]?)?[.!]?\s*$)",
        re.I,
    ), CallerIntent.CONFIRMATION, 0.85),

    # Denial
    (re.compile(
        r"^(nee\s*(?:dank\s*(?:je|u)|bedankt|hoeft\s+niet|"
        r"laat\s+maar|niet\s+nodig)?[.!]?\s*$)",
        re.I,
    ), CallerIntent.DENIAL, 0.85),

    # Gratitude
    (re.compile(
        r"\b(bedankt|dank\s*(?:je|u)\s*(?:wel)?|thanks|hartelijk\s+dank|"
        r"heel\s+erg\s+bedankt|super\s+bedankt|fijn|top)\b",
        re.I,
    ), CallerIntent.GRATITUDE, 0.80),

    # Pricing
    (re.compile(
        r"\b(prij[sz]\w*|kost\w*|tariev\w*|tarief\w*|pakket\w*|"
        r"abonnement\w*|€|euro|betaal\w*|goedkoop\w*|budget\w*|"
        r"belminut\w*|per\s+maand|per\s+jaar)\b",
        re.I,
    ), CallerIntent.PRICING, 0.80),

    # Appointment
    (re.compile(
        r"\b(afspraak\w*|inplann\w*|boek\w*|reserv\w*|"
        r"agenda|beschikbaar\w*|wanneer\s+kan|vrij\w*\s+slot|"
        r"morgen|overmorgen|volgende\s+week|deze\s+week)\b",
        re.I,
    ), CallerIntent.APPOINTMENT, 0.80),

    # General question (broad catch)
    (re.compile(
        r"\b(wat|wie|waar|wanneer|waarom|hoe|welke?|hoeveel|"
        r"kunt?\s+(?:u|je)|kun\s+je|weet\s+(?:u|je)|"
        r"is\s+(?:het|er|dat)|heeft?\s+(?:u|jullie)|"
        r"kan\s+(?:ik|dat)|mag\s+(?:ik|dat))\b",
        re.I,
    ), CallerIntent.QUESTION, 0.60),
]

# Off-topic signals (checked separately — only when no other intent matched)
_OFF_TOPIC_RE = re.compile(
    r"\b(pizza|weer\s+vandaag|voetbal|ajax|feyenoord|psv|"
    r"wie\s+is\s+de\s+president|recepten?|spotify|netflix|"
    r"grap|mop|vertel\s+een|zing\s+een|"
    r"bitcoin|crypto|beurs)\b",
    re.I,
)


def classify_intent(utterance: str) -> Tuple[CallerIntent, float]:
    """
    Classify a caller utterance into an intent with confidence score.

    Returns (CallerIntent, confidence) where confidence is 0.0-1.0.
    Deterministic, regex-based. First match wins (rules ordered by priority).
    """
    if not utterance or not utterance.strip():
        return CallerIntent.SILENCE, 0.99

    text = utterance.strip()

    # Check cache
    cache_key = text.lower()[:200]
    if cache_key in _cache:
        return CallerIntent(_cache[cache_key][0]), _cache[cache_key][1]

    for pattern, intent, confidence in _RULES:
        if pattern.search(text):
            _cache[cache_key] = (intent.value, confidence)
            return intent, confidence

    # Off-topic check
    if _OFF_TOPIC_RE.search(text):
        _cache[cache_key] = (CallerIntent.OFF_TOPIC.value, 0.75)
        return CallerIntent.OFF_TOPIC, 0.75

    # Fallback
    if len(text.split()) <= 2:
        _cache[cache_key] = (CallerIntent.UNCLEAR.value, 0.40)
        return CallerIntent.UNCLEAR, 0.40

    _cache[cache_key] = (CallerIntent.QUESTION.value, 0.40)
    return CallerIntent.QUESTION, 0.40
