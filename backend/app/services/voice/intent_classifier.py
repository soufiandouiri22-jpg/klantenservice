"""
Intent classifier — deterministic, regex-first classification of caller
utterances for the voice pipeline.

Runs on every server tool call to classify the latest customer message.
Designed for Dutch; patterns cover common phrasings and variations.

Off-topic detection runs BEFORE the generic question catch-all so that
"Kun je een pizza bestellen?" is classified as off_topic, not question.
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


# ── Off-topic keyword pattern (broad coverage) ────────────────────
# This must be checked BEFORE the generic question catch-all.

_OFF_TOPIC_RE = re.compile(
    r"\b("
    # Food / restaurants
    r"pizza|hamburger|sushi|friet|patat|bezorg\w*\s+eten|uber\s*eats|thuisbezorgd|"
    r"recept\w*|kook\w*|bak\w*\s+(?:taart|cake|brood)|"
    # Weather
    r"weer\s+(?:vandaag|morgen|overmorgen|deze\s+week)|weerbericht|weersvoorspelling|"
    r"weer\s+voor\s+(?:morgen|overmorgen|vandaag)|"
    r"regent\s+het|zon\w*\s+schijn|temperatuur\s+(?:vandaag|morgen|buiten)|"
    # Sports
    r"voetbal\w*|ajax|feyenoord|psv|eredivisie|champions\s*league|"
    r"formule\s*1|f1|olympi\w*|wedstrijd\w*\s+(?:vandaag|morgen)|"
    # Entertainment / media
    r"spotify|netflix|disney\s*plus|youtube|tiktok|instagram|"
    r"film\w*\s+(?:kijken|aanraden|tip)|serie\w*\s+(?:kijken|aanraden|tip)|"
    r"grap\w*|mop\w*|vertel\s+(?:een|me)\s+(?:grap|mop|verhaal)|"
    r"zing\s+(?:een|voor\s+me)|"
    # General knowledge / trivia
    r"hoofdstad\s+van|president\s+van|wie\s+(?:is|was)\s+de\s+(?:president|koning|premier)|"
    r"hoeveel\s+inwoners|wanneer\s+is\s+(?:kerst|pasen|koningsdag)|"
    r"wat\s+is\s+de\s+(?:hoofdstad|bevolking|oppervlakte)|"
    # School / homework
    r"huiswerk\w*|wiskunde|som\w*\s+(?:maken|oplossen|uitrekenen)|"
    r"werkstuk|spreekbeurt|examen\w*\s+(?:tip|hulp|oefenen)|"
    r"bereken\s+(?:de|het)|uitleg\w*\s+(?:over|van)\s+(?:wiskunde|natuurkunde|scheikunde)|"
    # Finance / crypto (unrelated to company)
    r"bitcoin|crypto\w*|beurs|aandel\w*|belegg\w*|"
    r"koers\s+van|wat\s+kost\s+(?:een\s+)?bitcoin|"
    # Travel (unrelated to company)
    r"vlieg\w*\s+naar|vlucht\s+(?:naar|boeken)|hotel\s+(?:in|boeken)|"
    r"vakantie\s+(?:naar|boeken|tip)|"
    # Other clearly off-topic
    r"wie\s+wint\s+(?:het|de)|"
    r"lotto\w*|loterij|postcode\s*loterij|"
    r"vertaal\s+(?:dit|het|naar)|"
    r"schrijf\s+(?:een\s+)?(?:gedicht|lied|brief\s+naar|email\s+naar)|"
    r"doe\s+(?:een\s+)?(?:spelletje|quiz|raadsel)"
    r")\b",
    re.I,
)

# Structural off-topic: "Kun je X voor me Y?" where X is non-business
_OFF_TOPIC_ACTION_RE = re.compile(
    r"\b(?:kun\s+je|kan\s+je|wil\s+je|zou\s+je|kunt\s+u|kunt\s+je)\s+"
    r"(?:een\s+|me\s+|mij\s+|voor\s+(?:me|mij)\s+)?"
    r"(?:pizza|eten|taxi|hotel|vlucht|vliegticket|"
    r"huiswerk|som|grap|mop|lied|gedicht|verhaal|"
    r"(?:het\s+)?weer|weerbericht|recept|"
    r"spelletje|quiz|raadsel|"
    r"vertaling|vertalen|"
    r"film|serie)\b",
    re.I,
)

# ── Main rules (ordered by priority; first match wins) ────────────

_RULES: list[tuple[re.Pattern, CallerIntent, float]] = [
    # Silence / empty
    (re.compile(r"^\s*$"), CallerIntent.SILENCE, 0.99),

    # Goodbye — must come before greeting (overlapping words)
    (re.compile(
        r"\b(doei|tot\s*ziens|tot\s*snel|tot\s*de\s+volgende|"
        r"fijne\s+dag|fijne\s+avond|prettige\s+dag|prettige\s+avond|"
        r"goedenacht|lekker\s+weekend|"
        r"bye|goodbye|tot\s+later)\b|"
        r"^\s*da+g!?\s*$",
        re.I,
    ), CallerIntent.GOODBYE, 0.95),

    # Anger / frustration — strong signals
    (re.compile(
        r"\b(boos|kwaad|woedend|onacceptabel|belachelijk|schande|schandalig|"
        r"klacht\s*indienen|klacht|aanklacht|advocaat|rechter|juridisch|"
        r"fuck|shit|godverdomme|kut|kanker|tyfus|tering|"
        r"rotzooi|waardeloos|verschrikkelijk|vreselijk|"
        r"nooit\s+meer|oplichter\w*|oplichting|zwendel|bedrog|"
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
        r"agenda|beschikbaar\w*|wanneer\s+kan|vrij\w*\s+slot)\b",
        re.I,
    ), CallerIntent.APPOINTMENT, 0.80),

    # ── OFF-TOPIC (before generic question!) ──────────────────────
    # Keyword-based off-topic detection
    (_OFF_TOPIC_RE, CallerIntent.OFF_TOPIC, 0.90),
    # Structural pattern: "Kun je [non-business-thing] voor me?"
    (_OFF_TOPIC_ACTION_RE, CallerIntent.OFF_TOPIC, 0.88),

    # General question (broad catch-all — LAST specific intent)
    (re.compile(
        r"\b(wat|wie|waar|wanneer|waarom|hoe|welke?|hoeveel|"
        r"kunt?\s+(?:u|je)|kun\s+je|weet\s+(?:u|je)|"
        r"is\s+(?:het|er|dat)|heeft?\s+(?:u|jullie)|"
        r"kan\s+(?:ik|dat)|mag\s+(?:ik|dat))\b",
        re.I,
    ), CallerIntent.QUESTION, 0.60),
]


def classify_intent(utterance: str) -> Tuple[CallerIntent, float]:
    """
    Classify a caller utterance into an intent with confidence score.

    Returns (CallerIntent, confidence) where confidence is 0.0-1.0.
    Deterministic, regex-based. First match wins (rules ordered by priority).
    Off-topic detection runs before the generic question catch-all.
    """
    if not utterance or not utterance.strip():
        return CallerIntent.SILENCE, 0.99

    text = utterance.strip()

    cache_key = text.lower()[:200]
    if cache_key in _cache:
        return CallerIntent(_cache[cache_key][0]), _cache[cache_key][1]

    for pattern, intent, confidence in _RULES:
        if pattern.search(text):
            _cache[cache_key] = (intent.value, confidence)
            return intent, confidence

    # Fallback
    if len(text.split()) <= 2:
        _cache[cache_key] = (CallerIntent.UNCLEAR.value, 0.40)
        return CallerIntent.UNCLEAR, 0.40

    _cache[cache_key] = (CallerIntent.QUESTION.value, 0.40)
    return CallerIntent.QUESTION, 0.40


def is_off_topic(utterance: str) -> bool:
    """
    Secondary scope check — can be called even if classify_intent
    returned something other than OFF_TOPIC.

    Returns True if the utterance contains clear off-topic signals,
    regardless of what other patterns may have also matched.
    """
    if not utterance or not utterance.strip():
        return False
    text = utterance.strip()
    return bool(_OFF_TOPIC_RE.search(text) or _OFF_TOPIC_ACTION_RE.search(text))
