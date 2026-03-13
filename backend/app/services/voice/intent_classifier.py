"""
Intent classifier — deterministic, regex-first classification of caller
utterances for the voice pipeline.

Runs on every server tool call to classify the latest customer message.
Designed for Dutch; patterns cover common phrasings and variations.

Off-topic detection runs BEFORE the generic question catch-all so that
"Kun je een pizza bestellen?" is classified as off_topic, not question.
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

_cache: dict[str, Tuple[str, float]] = {}


# ═══════════════════════════════════════════════════════════════════
#  Company scope — used by company-aware off-topic / scope checking
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CompanyScope:
    """Lightweight scope descriptor passed through the voice pipeline."""
    business_type: Optional[str] = None
    topics: list[str] = field(default_factory=list)


class CallerIntent(str, Enum):
    GREETING = "greeting"
    GOODBYE = "goodbye"
    QUESTION = "question"
    PRICING = "pricing"
    APPOINTMENT = "appointment"
    COMPLAINT = "complaint"
    ANGER = "anger"
    FRUSTRATION = "frustration"
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
    r"vakantie\s*(?:naar|boeken|tip\w*)|vakantietip\w*|"
    # Cinema / entertainment / media
    r"bioscoop\w*|bioscoopfilm\w*|"
    r"nieuws\s+(?:vandaag|morgen)|het\s+nieuws|"
    r"\btv\b|televisie|op\s+tv|"
    r"taart\w*|"
    r"taxi\w*|"
    # Health / fitness (unrelated to company)
    r"calorie[ën\w]*|"
    # Postal / address lookup
    r"postcode\s+van|wat\s+is\s+de\s+postcode|postcode\s+\d|"
    # Math requests
    r"(?:hoeveel\s+is\s+)?\d+\s+(?:maal|keer|plus|min|gedeeld\s+door)\s+\d+|"
    r"(?:maal|keer|plus|min|gedeeld\s+door)\s+\d+|"
    # Other clearly off-topic
    r"wie\s+wint\s+(?:het|de)|"
    r"lotto\w*|loterij|postcode\s*loterij|"
    r"vertaal\s+(?:dit|het|naar)|"
    r"schrijf\s+(?:een\s+)?(?:gedicht|lied|brief|email|"
    r"verhaal|essay|artikel|samenvatting|tekst)|"
    r"doe\s+(?:een\s+)?(?:spelletje|quiz|raadsel)"
    r")\b",
    re.I,
)

# Structural off-topic: "Kun je X voor me Y?" where X is non-business
_OFF_TOPIC_ACTION_RE = re.compile(
    r"\b(?:kun\s+je|kan\s+je|wil\s+je|zou\s+je|kunt\s+u|kunt\s+je|bestel)\s+"
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

    # Goodbye / conversation closing — must come before greeting (overlapping words)
    (re.compile(
        r"\b(doei|tot\s*ziens|tot\s*snel|tot\s*de\s+volgende|"
        r"fijne\s+dag|fijne\s+avond|prettige\s+dag|prettige\s+avond|"
        r"goedenacht|lekker\s+weekend|"
        r"bye|goodbye|tot\s+later)\b|"
        # Satisfied / done / closing signals
        r"\b(ik\s+weet\s+genoeg|dat\s+was\s+het|dat\s+is\s+alles|"
        r"ik\s+heb\s+genoeg\s+info\w*|geen\s+vragen\s+meer|"
        r"verder\s+geen\s+vragen|nee\s+hoor\s*,?\s*hoeft\s+niet|"
        r"hoeft\s+(?:niet\s+meer|verder\s+niet)|"
        r"nee\s+(?:dank\s*(?:je|u)|bedankt)\s*,?\s*(?:dat\s+was\s+het|ik\s+weet\s+genoeg)?|"
        r"dat\s+is\s+(?:voldoende|genoeg)|ik\s+ben\s+(?:klaar|geholpen)|"
        r"u\s+heeft\s+mij\s+geholpen|je\s+hebt\s+me\s+geholpen|"
        r"top\s+(?:dank\w+|bedankt)|(?:oke|oké)\s+(?:dank\w+|bedankt)|"
        r"that'?s\s+(?:all|enough|it)|(?:no\s+)?thanks?\s*,?\s*(?:that'?s\s+(?:all|enough|it)|i'?m\s+good)|"
        r"i\s+(?:have\s+)?(?:enough|all\s+(?:the\s+)?info)|(?:nothing|no)\s+(?:else|more))\b|"
        r"^\s*da+g!?\s*$",
        re.I,
    ), CallerIntent.GOODBYE, 0.95),

    # Anger / frustration — strong signals
    (re.compile(
        r"\b(boos|kwaad|woedend|razend|furieus|"
        r"onacceptabel|belachelijk|schande|schandalig|"
        r"klacht\s*indienen|klacht|aanklacht|advocaat|rechter|juridisch|"
        r"fuck|shit|godverdomme|kut|kanker|tyfus|tering|"
        r"rotzooi|waardeloos|verschrikkelijk\w*|vreselijk\w*|"
        r"nooit\s+meer|oplichter\w*|oplichting|zwendel|bedrog\w*|"
        r"geld\s+terug|"
        r"dit\s+kan\s+(?:niet|echt\s+niet)|dit\s+pik\s+ik\s+niet|ik\s+ben\s+het\s+zat|"
        # Stronger emotional / insult patterns
        r"verpest\w*|verniel\w*|vernaggel\w*|"
        r"pruts\w*|klungel\w*|"
        r"slechtste\w*|ergste\w*|"
        r"schaam\s+(?:je|u|jullie)|"
        r"klaar\s+(?:er\s*)?mee|helemaal\s+klaar\s+(?:er\s*)?mee|"
        r"hier\s+(?:echt\s+)?boos\s+(?:om|over)|"
        r"echt\s+(?:heel\s+)?slecht|"
        r"ongelofelijk\s+slecht|"
        r"beschadig\w+)\b",
        re.I,
    ), CallerIntent.ANGER, 0.90),

    # Frustration — repeated-failure signals (softer than anger)
    (re.compile(
        r"\b("
        r"(?:dat\s+)?bedoel\s+ik\s+niet|dat\s+is\s+niet\s+wat\s+ik\s+(?:vroeg|bedoel|zei)|"
        r"je\s+begrijpt\s+(?:me|mij)\s+niet|u\s+begrijpt\s+(?:me|mij)\s+niet|"
        r"nog\s+steeds\s+niet|dat\s+heb\s+ik\s+al\s+(?:gezegd|gevraagd|uitgelegd)|"
        r"ik\s+heb\s+(?:dit|dat)\s+al\s+(?:gezegd|gevraagd|uitgelegd)|"
        r"luister\s+(?:je|u)\s+(?:wel|eigenlijk)|"
        r"dat\s+zei\s+ik\s+(?:al|net|toch)|"
        r"nee\s+(?:dat\s+)?(?:bedoel|klopt|snap)\s+ik\s+niet|"
        r"ik\s+(?:snap|begrijp)\s+(?:er|het)\s+(?:niks|niets|geen)\s+(?:van|meer)|"
        r"ik\s+(?:snap|begrijp)\s+(?:het\s+)?niet|"
        r"(?:je|u)\s+snapt?\s+er\s+(?:niks|niets)\s+van|"
        r"dat\s+(?:klopt|helpt)\s+(?:niet|helemaal\s+niet)|"
        r"nee\s+dat\s+klopt\s+(?:niet|helemaal\s+niet)|"
        r"we\s+draaien\s+in\s+(?:rondjes|cirkels|kringetjes)"
        r")\b",
        re.I,
    ), CallerIntent.FRUSTRATION, 0.88),

    # Complaint — softer frustration / implicit dissatisfaction
    (re.compile(
        r"\b(niet\s+tevreden|ontevreden|teleurgesteld|tegenvalt|"
        r"valt\s+(?:me|mij)\s+tegen|"
        r"probleem|fout\w*|verkeerd\w*|kapot|stuk|defect|beschadigd|"
        r"te\s+lang\s+wacht|al\s+\d+\s+keer\s+gebeld|steeds\s+weer|"
        r"niet\s+opgelost|gaat\s+fout|werkt\s+niet|lukt\s+niet|"
        r"foutmelding|error|storing|"
        # Implicit dissatisfaction: result/service quality
        r"niet\s+(?:goed|wat\s+ik|zoals)\b|"
        r"helemaal\s+(?:niet\s+goed|anders|verkeerd|mis)|"
        r"(?:nog\s+steeds|steeds\s+nog)\s+(?:niet|kapot|stuk|pijn|last)|"
        r"(?:veel|erg|heel)\s+(?:te\s+)?lang\s+(?:gewacht|wachten|moeten\s+wacht|geduurd|duurde)|"
        r"(?:lang|uren?)\s+moeten\s+wachten|"
        r"moest\w*\s+(?:\w+\s+)*wachten|"
        r"duurde\s+(?:veel\s+)?te\s+lang|"
        r"(?:er\s*(?:al\s+)?)?uit\s*gevallen|"
        # Negative outcome / unmet expectations
        r"niet\s+wat\s+(?:ik|we|wij)\s+(?:verwacht|gevraagd|besteld|afgesproken|wilde)|"
        r"anders\s+dan\s+(?:afgesproken|verwacht|beloofd)|"
        r"(?:klopt|klopte)\s+niet|"
        r"(?:hoger|meer|duurder)\s+dan\s+(?:de\s+)?(?:offerte|afgesproken|verwacht)|"
        # Physical problems after service
        r"(?:nog\s+steeds\s+)?(?:pijn|last|bloedt?|bloeding)\s+(?:na|sinds|van)|"
        r"(?:pijn|last)\s+(?:na|sinds)\s+(?:de|het|mijn)\b|"
        # General "not right" patterns
        r"(?:zit|staat|is)\s+(?:helemaal\s+)?niet\s+goed|"
        r"kan\s+(?:er\s+)?niet\s+(?:mee\s+)?(?:leven|door)|"
        r"niet\s+(?:gelukt|gefixt|gemaakt|gerepareerd|hersteld)|"
        r"(?:is|was|waren)\s+(?:helemaal\s+)?(?:mis|fout)\b|"
        r"(?:was|waren|is)\s+(?:erg|heel|echt|ontzettend|veel|super|best\s+wel)?\s*(?:koud|vies|vuil|slecht|smerig|rauw|oud|bedorven|lauw|onvriendelijk|lawaaierig|traag|(?:(?:veel\s+)?te\s+)?klein|(?:(?:veel\s+)?te\s+)?duur|(?:(?:veel\s+)?te\s+)?lang|pijnlijk)\b|"
        r"crasht|inloggen\s+lukt\s+niet|kan\s+niet\s+inloggen|"
        r"data\s+(?:is\s+)?(?:weg|verdwenen|kwijt)|"
        r"(?:dubbel|foutief)\s+gefactureerd|"
        # Foreign objects / unexpected damage
        r"er\s+z(?:at|it)\s+(?:een\s+)?(?:haar|vlek|scheur|deuk|gat|barst)|"
        r"(?:een\s+)?kras\s+(?:op|in|aan)|"
        # Expectation mismatch / duration complaint
        r"in\s+plaats\s+van|"
        r"(?:nog\s+steeds|steeds\s+nog)\s+(?:hetzelfde|dezelfde)|"
        # Broad "not what I expected" phrasing
        r"helemaal\s+niet\s+wat|"
        r"(?:kale|lege)\s+plek)\b",
        re.I,
    ), CallerIntent.COMPLAINT, 0.85),

    # Transfer to human
    (re.compile(
        r"\b(echte?\s+persoon|echte?\s+mens|echte?\s+medewerker|"
        r"iemand\s+anders|collega|leidinggevende|manager|supervisor|chef|"
        r"directeur|directie|management|"
        r"doorverbind\w*|verbind\s+(?:me|mij)\s+(?:met|door)|doorverbonden\s+worden|"
        r"menselijk\w*|een\s+mens|"
        r"geen\s+computer|geen\s+robot|geen\s+machine|"
        r"niet\s+(?:meer\s+)?met\s+een\s+(?:machine|computer|robot)\s+praten|"
        r"niet\s+meer\s+met\s+(?:jou|u|je)\s+(?:praten|spreken)|"
        r"geef\s+(?:me|mij)\s+(?:een\s+)?(?:medewerker|mens|persoon)|"
        r"(?:een|de)\s+medewerker\s+(?:krijgen|spreken|bellen)|"
        r"ik\s+wil\s+(?:een\s+)?(?:mens|iemand)\s+spreken|"
        r"ik\s+wil\s+iemand\s+spreken|"
        r"(?:kan\s+ik|mag\s+ik|ik\s+wil)\s+(?:de|een)\s+\w+\s+(?:\w+\s+)?(?:spreken|bellen|aan\s+de\s+lijn)|"
        r"iemand\s+van\s+(?:jullie|het|de)\s+\w+\s+spreken|"
        r"iemand\s+van\s+(?:jullie|het\s+team|het\s+bedrijf))\b",
        re.I,
    ), CallerIntent.TRANSFER_REQUEST, 0.92),

    # Greeting
    (re.compile(
        r"^(hallo|hoi|hey|goedemorgen|goedemiddag|goedenavond|"
        r"goedendag|ja\s+hallo|he+y)\b",
        re.I,
    ), CallerIntent.GREETING, 0.90),

    # Short scheduling follow-ups (must come before generic confirmation)
    (re.compile(
        r"^(?:(?:ja|nee|toch|eigenlijk|oh|nou|wacht|maar|ok[eé]?|dan)\s+){0,2}"
        r"(?:(?:liever|doe\s+(?:maar)?)\s+)?"
        r"(?:morgen|vandaag|overmorgen|"
        r"(?:aanstaande\s+|volgende\s+(?:week\s+)?)?(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag))"
        r"(?:\s+(?:om|rond)\s+(?:half\s+)?(?:\d{1,2}|een|twee|drie|vier|vijf|zes|zeven|acht|negen|tien|elf|twaalf)"
        r"(?:[.:]\d{2})?(?:\s+uur)?)?[.!]?\s*$",
        re.I,
    ), CallerIntent.APPOINTMENT, 0.82),

    # Short time-only follow-ups ("om drie uur", "rond half 4", "ja om twee uur graag")
    (re.compile(
        r"^(?:ja\s+)?(?:om|rond)\s+(?:half\s+)?(?:\d{1,2}|een|twee|drie|vier|vijf|zes|zeven|acht|negen|tien|elf|twaalf)"
        r"(?:[.:]\d{2})?\s*(?:uur)?\s*(?:graag|alsjeblieft|aub)?\s*[.!]?\s*$",
        re.I,
    ), CallerIntent.APPOINTMENT, 0.80),

    # Confirmation (including scheduling confirmations)
    (re.compile(
        r"^(ja\s*(?:graag|zeker|dat\s+klopt|precies|inderdaad|goed|prima|top|"
        r"die\s+(?:tijd|datum|dag)\s+is\s+goed|"
        r"doe\s+maar|is\s+goed|akkoord|ok[eé]?|klopt)?[.!]?\s*$)",
        re.I,
    ), CallerIntent.CONFIRMATION, 0.85),

    # Denial
    (re.compile(
        r"^(nee\s*(?:dank\s*(?:je|u)|bedankt|hoeft\s+niet|"
        r"laat\s+maar|niet\s+nodig)?[.!]?\s*$|"
        r"laat\s+(?:maar|zitten)[.!]?\s*$)",
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
        r"\b(prij[sz]\w*|kost\w*|tariev\w*|tarief\w*|\w*pakket\w*|"
        r"abonnement\w*|€|euro|betaa?l\w*|goedkoo?p\w*|budget\w*|"
        r"belminut\w*|per\s+maand|per\s+jaar|"
        r"\w*korting\w*|opzeg\w*|gratis|proefperiode|"
        r"offerte\w*|staffel\w*|"
        r"upgrade\w*|downgrade\w*|"
        r"verschil\s+tussen|"
        r"welk\s+pakket|duurste|goedkoopste|"
        r"factuur\w*|facturen|rekening)\b",
        re.I,
    ), CallerIntent.PRICING, 0.80),

    # Appointment
    (re.compile(
        r"\b(afspraak\w*|inplann\w*|boek\w*|reserv\w*|"
        r"agenda|beschikba\w+|wanneer\s+kan|vrij\w*\s+(?:slot|plek\w*|plekje\w*)|"
        r"plek\w*\s+(?:vrij|beschikbaar|over)|vrije\s+plek\w*|plek(?:je|ken|jes|je)?(?=\s*[\?\.!]|\s|$)|"
        r"terecht|"
        r"langskomen|langs\s+komen|"
        r"ruimte|"
        r"ergens\s+deze\s+week|"
        r"zo\s+snel\s+mogelijk|"
        r"verzetten|verplaats\w*|omboek\w*|"
        r"annule\w+|afzeg\w*|"
        r"(?:kan|kom|het\s+komt|lukt|red)\s+(?:helaas\s+)?(?:niet\s+meer|toch\s+niet)|"
        r"(?:niet\s+meer|toch\s+niet)\s+(?:komen|lukken)|"
        r"(?:het\s+)?komt?\s+(?:toch\s+)?niet\s+uit|"
        r"(?:een\s+)?ander(?:e\s+)?(?:dag|moment|tijd|datum|keer)|"
        r"(?:kan\s+het|kunnen\s+we)\s+(?:ook\s+)?(?:later|eerder|morgen|een\s+dag)|"
        r"(?:ik\s+)?red\s+het\s+niet|"
        r"(?:morgen|vandaag|vrijdag|maandag|dinsdag|woensdag|donderdag|zaterdag|zondag)"
        r"\s+(?:om|rond)\s+(?:\d|een|twee|drie|vier|vijf))\b",
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


def is_off_topic(
    utterance: str,
    company_scope: Optional[CompanyScope] = None,
) -> bool:
    """
    Secondary scope check — can be called even if classify_intent
    returned something other than OFF_TOPIC.

    Returns True if the utterance contains clear off-topic signals,
    regardless of what other patterns may have also matched.

    If company_scope is provided, domain-relevant terms are exempted
    from the global off-topic regex (e.g. "pizza" for a pizza restaurant).
    """
    if not utterance or not utterance.strip():
        return False
    text = utterance.strip()

    match = _OFF_TOPIC_RE.search(text)
    if match and company_scope and company_scope.business_type:
        matched_term = match.group(0).lower().strip()
        exemptions = _get_exemptions(company_scope.business_type)
        if any(ex in matched_term for ex in exemptions):
            match = None

    if match:
        return True

    action_match = _OFF_TOPIC_ACTION_RE.search(text)
    if action_match and company_scope and company_scope.business_type:
        matched_text = action_match.group(0).lower().strip()
        exemptions = _get_exemptions(company_scope.business_type)
        if any(ex in matched_text for ex in exemptions):
            action_match = None

    return bool(action_match)


def _get_exemptions(business_type: str) -> set[str]:
    """Get the off-topic exemption terms for a business type."""
    from app.services.domain_inference import PROFILES
    profile = PROFILES.get(business_type)
    return profile.off_topic_exemptions if profile else set()


def check_company_scope(
    utterance: str,
    company_scope: CompanyScope,
) -> str:
    """
    Check whether an utterance is in scope for a given company.

    Returns:
        "on_topic"  — utterance matches this company's domain
        "off_topic" — utterance matches a DIFFERENT domain only
        "neutral"   — no domain-specific terms detected
    """
    if not utterance or not utterance.strip():
        return "neutral"
    if not company_scope or not company_scope.business_type:
        return "neutral"

    from app.services.domain_inference import PROFILES

    text = utterance.strip()
    matched_domains: set[str] = set()

    for btype, profile in PROFILES.items():
        if btype == "general":
            continue
        if profile.scope_re.search(text):
            matched_domains.add(btype)

    if not matched_domains:
        return "neutral"

    if company_scope.business_type in matched_domains:
        return "on_topic"

    return "off_topic"


# ═══════════════════════════════════════════════════════════════════
#  LAYER 2+3: Context-aware + semantic classification
# ═══════════════════════════════════════════════════════════════════
#
#  Three-layer system:
#    1. Rule-based regex (fast, deterministic) — classify_intent()
#    2. Semantic scoring (keyword proximity per intent)
#    3. Context resolution (conversation flow awareness)
#
#  High-confidence regex results are returned immediately.
#  Low-confidence results are refined by semantic + context layers.

@dataclass
class ConversationContext:
    """Minimal conversation state for context-aware classification."""
    prev_intent: Optional[CallerIntent] = None
    prev_utterance: str = ""
    phase: str = "greeting"
    flow_type: Optional[str] = None   # "booking", "pricing", "transfer"
    turn_count: int = 0

    def in_booking_flow(self) -> bool:
        return (self.flow_type == "booking"
                or self.prev_intent == CallerIntent.APPOINTMENT)

    def in_transfer_flow(self) -> bool:
        return (self.flow_type == "transfer"
                or self.prev_intent == CallerIntent.TRANSFER_REQUEST)


class BookingSignal(str, Enum):
    TIME_PREFERENCE = "time_preference"
    DATE_PREFERENCE = "date_preference"
    FLEXIBLE_SCHEDULING = "flexible_scheduling"
    CONFIRMATION = "confirmation"
    RESCHEDULE = "reschedule"
    CANCELLATION = "cancellation"


# ── Semantic signal patterns per intent ──────────────────────────
# Each is (compiled regex, weight). Weights are summed per intent;
# raw totals are compared — only the winning score is capped on output.

_APPOINTMENT_SEMANTIC: list[tuple[re.Pattern, float]] = [
    # Time-of-day
    (re.compile(r'\b(?:de\s+)?(?:middag|ochtend|avond)\b', re.I), 0.5),
    (re.compile(r'\boverdag\b', re.I), 0.5),
    (re.compile(r"'s\s+(?:morgens|middags|avonds|ochtends)", re.I), 0.6),
    # Scheduling verbs
    (re.compile(r'\bplan\w*\s+(?:me|mij|ons)\b', re.I), 0.7),
    (re.compile(r'\b(?:uitkomt|schikt|past)\b', re.I), 0.4),
    (re.compile(r'\bkomen\b', re.I), 0.2),
    # Contextual scheduling phrases
    (re.compile(r'\b(?:rond|ergens|iets)\s+(?:de\s+)?(?:middag|ochtend|avond|week)\b', re.I), 0.7),
    (re.compile(r'\bhet\s+liefst\b', re.I), 0.4),
    (re.compile(r'\bbij\s+voorkeur\b', re.I), 0.4),
    (re.compile(r'\bmaakt\s+(?:me\s+|mij\s+)?niet\s+uit\b', re.I), 0.5),
    (re.compile(r'\bals\s+het\s+kan\b', re.I), 0.4),
    (re.compile(r'\b(?:vandaag|morgen)\s+nog\b', re.I), 0.4),
    (re.compile(r'\bbinnenkort\b', re.I), 0.3),
    # Compound words containing scheduling nouns (afspraa?k handles Dutch aa→a inflection)
    (re.compile(r'\b\w*afspraa?k\w*\b', re.I), 0.8),
    (re.compile(r'\bbehandeling\w*\b', re.I), 0.5),
    # Date references
    (re.compile(r'\b(?:volgende|aanstaande|komende|deze)\s+week(?:\s+\w+dag)?\b', re.I), 0.6),
    (re.compile(r'\b(?:maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)\b', re.I), 0.3),
    # Time references
    (re.compile(r'\bom\s+\d{1,2}\b', re.I), 0.5),
    (re.compile(r'\b\d{1,2}\s+uur\b', re.I), 0.5),
    (re.compile(r'\bom\s+(?:een|twee|drie|vier|vijf|zes|zeven|acht|negen|tien|elf|twaalf)\b', re.I), 0.5),
    # Scheduling constraints
    (re.compile(r'\b(?:daarna|erna)\s+graag\b', re.I), 0.5),
    (re.compile(r'\btot\s+\d', re.I), 0.3),
    (re.compile(r'\bvrij\w*\s+moment\b', re.I), 0.6),
]

_TRANSFER_SEMANTIC: list[tuple[re.Pattern, float]] = [
    (re.compile(r'\bliever\s+(?:met\s+)?(?:iemand|een\s+mens)', re.I), 0.8),
    (re.compile(r'\bpraat\s+liever\b', re.I), 0.7),
    (re.compile(r'\b(?:echte?)\s+medewerker\w*', re.I), 0.7),
    (re.compile(r'\biemand\s+(?:van\s+(?:het\s+)?team|anders)\b', re.I), 0.8),
    (re.compile(r'\bniet\s+meer\s+met\s+(?:jou|u|je)\b', re.I), 0.7),
    (re.compile(r'\bsenior\s+medewerker', re.I), 0.7),
    (re.compile(r'\bmedewerker\w*\b', re.I), 0.3),
    (re.compile(r'\biemand\s+spreken\b', re.I), 0.6),
    (re.compile(r'\biemand\s+(?:bellen|bereiken)\b', re.I), 0.5),
]

_CONFIRMATION_SEMANTIC: list[tuple[re.Pattern, float]] = [
    (re.compile(r'\bdat\s+is\s+(?:prima|goed|ok[eé]?|mooi|fijn)\b', re.I), 0.8),
    (re.compile(r'\bklopt\s+(?:helemaal|precies|zeker)\b', re.I), 0.8),
    (re.compile(r'\bprima\s+zo\b', re.I), 0.7),
    (re.compile(r'\bgoed\s+zo\b', re.I), 0.6),
    (re.compile(r'\b(?:prima|top|perfect|super|mooi)\b', re.I), 0.4),
    (re.compile(r'\bnu\s+snap\s+ik\s+(?:het|t)\b', re.I), 0.6),
    (re.compile(r'\bok[eé]?\s*[,.]?\s+(?:nu|dan|goed|snap)\b', re.I), 0.5),
]

_DENIAL_SEMANTIC: list[tuple[re.Pattern, float]] = [
    (re.compile(
        r'\b(?:die|dat|deze)\s+(?:tijd|dag|datum)\s+'
        r'(?:past|kan|schikt|lukt)\s+niet\b', re.I), 0.8),
    (re.compile(r'\bliever\s+niet\b', re.I), 0.7),
    (re.compile(r'\btoch\s+(?:niet|maar\s+niet)\b', re.I), 0.6),
    (re.compile(r'\bhoef\s+(?:ik\s+)?(?:niet|geen)\b', re.I), 0.5),
    (re.compile(r'\bhoeft?\s+niet\s+meer\b', re.I), 0.7),
    # Cancellation (negation + appointment nouns) — high-weight denial
    (re.compile(
        r'\b(?:hoef|wil)\s+(?:geen|niet)\s+(?:meer\s+)?'
        r'(?:\w*afspraak|behandeling|reservering)', re.I), 1.0),
    (re.compile(r'\blaat\s+maar.*(?:afspraak|behandeling|boek)', re.I), 0.9),
]

_SEMANTIC_PATTERNS: dict[CallerIntent, list[tuple[re.Pattern, float]]] = {
    CallerIntent.APPOINTMENT: _APPOINTMENT_SEMANTIC,
    CallerIntent.TRANSFER_REQUEST: _TRANSFER_SEMANTIC,
    CallerIntent.CONFIRMATION: _CONFIRMATION_SEMANTIC,
    CallerIntent.DENIAL: _DENIAL_SEMANTIC,
}

_CONTEXT_FLOW_BOOST = 0.30
_CONTEXT_RELATED_BOOST = 0.15
_OVERRIDE_MARGIN = 0.10


def _score_semantic(text: str) -> dict[CallerIntent, float]:
    """Score utterance against weighted signal patterns for each intent.
    Returns raw (uncapped) scores for internal comparison."""
    scores: dict[CallerIntent, float] = {}
    for intent, patterns in _SEMANTIC_PATTERNS.items():
        total = sum(w for p, w in patterns if p.search(text))
        if total > 0:
            scores[intent] = total
    return scores


def _resolve_with_context(
    text: str,
    base_intent: CallerIntent,
    base_confidence: float,
    context: ConversationContext,
) -> Tuple[CallerIntent, float]:
    """Apply semantic scoring + context flow awareness to refine
    a low-confidence rule-based classification."""
    # Very high confidence (greeting, anger, goodbye) → trust regex
    if base_confidence >= 0.85:
        return base_intent, base_confidence

    scores = _score_semantic(text)

    # Context boost: amplify existing semantic evidence, never create phantom scores
    if context.in_booking_flow():
        if CallerIntent.APPOINTMENT in scores:
            scores[CallerIntent.APPOINTMENT] += _CONTEXT_FLOW_BOOST
        if CallerIntent.CONFIRMATION in scores:
            scores[CallerIntent.CONFIRMATION] += _CONTEXT_RELATED_BOOST
        if CallerIntent.DENIAL in scores:
            scores[CallerIntent.DENIAL] += _CONTEXT_RELATED_BOOST

    if context.in_transfer_flow():
        if CallerIntent.TRANSFER_REQUEST in scores:
            scores[CallerIntent.TRANSFER_REQUEST] += _CONTEXT_FLOW_BOOST

    if not scores:
        return base_intent, base_confidence

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    # Use tighter margin when not in a known flow, looser when context is available
    margin = 0.05 if context.flow_type is not None else _OVERRIDE_MARGIN

    if best_score > base_confidence + margin:
        return best_intent, min(best_score, 0.85)

    # Competing signals exist but no clear winner → prefer safe clarification
    if (len(scores) >= 2
            and base_confidence <= 0.40
            and base_intent in (CallerIntent.QUESTION, CallerIntent.UNCLEAR)):
        return CallerIntent.UNCLEAR, base_confidence

    return base_intent, base_confidence


# ── Lightweight English fallback ─────────────────────────────────
# Narrow, safe mapping for high-frequency English customer phrases.
# Only checked when Dutch regex returns low-confidence (QUESTION/UNCLEAR).

_ENGLISH_FALLBACK: list[tuple[re.Pattern, CallerIntent, float]] = [
    # Booking / appointment
    (re.compile(
        r"\b(?:book|schedule|make)\s+(?:an?\s+)?(?:appointment|booking|session)\b", re.I,
    ), CallerIntent.APPOINTMENT, 0.80),
    (re.compile(r"\b(?:cancel|reschedule)\s+(?:my\s+)?(?:appointment|booking)\b", re.I),
     CallerIntent.APPOINTMENT, 0.80),
    (re.compile(r"\breschedule\b", re.I), CallerIntent.APPOINTMENT, 0.70),
    # Pricing / cost
    (re.compile(r"\bhow\s+much\s+(?:does|is|will)\b", re.I), CallerIntent.PRICING, 0.80),
    (re.compile(r"\b(?:price|cost|pricing|subscription|plan)s?\b", re.I),
     CallerIntent.PRICING, 0.70),
    # Transfer / human handoff
    (re.compile(r"\b(?:speak|talk)\s+to\s+(?:a\s+)?(?:human|person|agent|someone)\b", re.I),
     CallerIntent.TRANSFER_REQUEST, 0.85),
    (re.compile(r"\b(?:connect|transfer)\s+(?:me\s+)?(?:to\s+)?(?:an?\s+)?(?:human|person|agent|someone)\b", re.I),
     CallerIntent.TRANSFER_REQUEST, 0.85),
    (re.compile(r"\breal\s+person\b", re.I), CallerIntent.TRANSFER_REQUEST, 0.80),
    # Confusion / help
    (re.compile(r"\bcan\s+you\s+help\s+me\b", re.I), CallerIntent.QUESTION, 0.60),
    (re.compile(r"\bi\s+(?:need|want)\s+help\b", re.I), CallerIntent.QUESTION, 0.60),
    # Greeting
    (re.compile(r"^(?:hello|hi|hey|good\s+(?:morning|afternoon|evening))\b", re.I),
     CallerIntent.GREETING, 0.80),
    # Goodbye / closing
    (re.compile(
        r"\b(?:goodbye|bye|see\s+you|take\s+care|"
        r"that'?s\s+(?:all|enough|it)|i'?m\s+good|no\s+thanks|"
        r"(?:nothing|no)\s+(?:else|more)|i\s+have\s+enough)\b",
        re.I,
    ), CallerIntent.GOODBYE, 0.80),
]


def _try_english_fallback(text: str) -> Optional[Tuple[CallerIntent, float]]:
    """Check for high-frequency English phrases. Returns None if no match."""
    for pattern, intent, confidence in _ENGLISH_FALLBACK:
        if pattern.search(text):
            return intent, confidence
    return None


def classify_intent_with_context(
    utterance: str,
    context: Optional[ConversationContext] = None,
) -> Tuple[CallerIntent, float]:
    """Context-aware intent classification.

    Layer 1: deterministic regex (classify_intent)
    Layer 2: semantic signal scoring
    Layer 3: conversation context resolution
    Layer 4: lightweight English fallback

    Falls back to UNCLEAR for safe clarification when truly ambiguous.
    """
    base_intent, base_confidence = classify_intent(utterance)

    # English fallback: try when Dutch regex returns low-confidence
    if base_confidence <= 0.50 and base_intent in (CallerIntent.QUESTION, CallerIntent.UNCLEAR):
        en = _try_english_fallback(utterance.strip() if utterance else "")
        if en is not None:
            return en

    if context is None:
        # No context → still apply semantic scoring for strong signals
        if base_confidence < 0.85:
            scores = _score_semantic(utterance.strip() if utterance else "")
            if scores:
                best = max(scores, key=scores.get)
                if scores[best] > base_confidence + _OVERRIDE_MARGIN:
                    return best, min(scores[best], 0.85)
        return base_intent, base_confidence

    return _resolve_with_context(
        utterance.strip() if utterance else "",
        base_intent, base_confidence, context,
    )


def detect_booking_signals(utterance: str) -> list[BookingSignal]:
    """Extract booking-related follow-up signals from an utterance."""
    if not utterance or not utterance.strip():
        return []
    text = utterance.strip()
    signals: list[BookingSignal] = []

    if re.search(
        r"\b(?:middag|ochtend|overdag|avond|uur)\b|"
        r"'s\s+(?:morgens|middags|avonds)|"
        r"\b(?:om|rond)\s+(?:\d|half|een|twee|drie|vier|vijf|zes|zeven|"
        r"acht|negen|tien|elf|twaalf)\b",
        text, re.I,
    ):
        signals.append(BookingSignal.TIME_PREFERENCE)

    if re.search(
        r"\b(?:morgen|vandaag|overmorgen|"
        r"maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag)\b|"
        r"\b(?:volgende|aanstaande|komende|deze)\s+week\b",
        text, re.I,
    ):
        signals.append(BookingSignal.DATE_PREFERENCE)

    if re.search(
        r"\b(?:maakt\s+niet\s+uit|wanneer\s+(?:het|maar|dan\s+ook)|"
        r"als\s+het\s+kan|het\s+liefst|bij\s+voorkeur|ergens|"
        r"binnenkort|zo\s+snel\s+mogelijk)\b",
        text, re.I,
    ):
        signals.append(BookingSignal.FLEXIBLE_SCHEDULING)

    if re.search(
        r"\b(?:ja\s+(?:graag|prima|goed|dat\s+klopt)|"
        r"dat\s+is\s+(?:prima|goed)|klopt)\b",
        text, re.I,
    ):
        signals.append(BookingSignal.CONFIRMATION)

    if re.search(
        r"\b(?:verzet\w*|verplaats\w*|omboek\w*|"
        r"ander\w*\s+(?:tijd|dag|datum))\b",
        text, re.I,
    ):
        signals.append(BookingSignal.RESCHEDULE)

    if re.search(
        r"\b(?:annule\w+|"
        r"(?:hoef|wil)\s+(?:geen|niet)\s+(?:meer\s+)?(?:\w*afspraak|behandeling)|"
        r"laat\s+maar)\b",
        text, re.I,
    ):
        signals.append(BookingSignal.CANCELLATION)

    return signals
