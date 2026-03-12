"""
Domain inference — automatically determine a company's business type
from its name and indexed website content.

Used by the indexing pipeline after crawling and by the scope-aware
off-topic detection in the voice pipeline.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  BUSINESS TYPE PROFILES
# ═══════════════════════════════════════════════════════════════════
#
# Each profile defines:
#   name_hints      – substrings that strongly suggest this type when
#                     found in the company name
#   content_keywords – {keyword: weight} scored against indexed content
#   scope_keywords  – compiled regex patterns for runtime scope checking;
#                     if an utterance matches these, the domain is relevant
#   off_topic_exemptions – terms from the global off-topic regex that
#                     should be EXEMPTED for this business type
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BusinessProfile:
    name_hints: list[str]
    content_keywords: dict[str, int]
    scope_re: re.Pattern
    off_topic_exemptions: set[str] = field(default_factory=set)


PROFILES: dict[str, BusinessProfile] = {
    "hair_salon": BusinessProfile(
        name_hints=[
            "kapsalon", "kapper", "kapster", "barber", "hair",
            "salon", "coiffeur", "coiffure", "hairstudio", "knipstudio",
        ],
        content_keywords={
            "haar": 3, "knippen": 5, "coupe": 4, "kapsel": 3, "föhnen": 4,
            "verven": 4, "kleuren": 3, "highlights": 4, "extensions": 3,
            "baard": 3, "trimmen": 3, "wassen": 2, "stylen": 3,
            "kapper": 5, "kapster": 5, "knipbeurt": 5, "balayage": 4,
            "permanent": 3, "keratine": 3, "hairextension": 4,
        },
        scope_re=re.compile(
            r"\b(?:haar|knippen|coupe|kapsel|föhn\w*|verf\w*|kleur\w*|"
            r"highlight\w*|extension\w*|baard|trim\w*|styl\w*|"
            r"kapper|kapster|knipbeurt|balayage|permanent|"
            r"keratine|opscheer\w*|bijpunt\w*|lok\w*|scheef|"
            r"behandeling\w*)\b",
            re.I,
        ),
    ),
    "dentist": BusinessProfile(
        name_hints=[
            "tandarts", "dental", "dentist", "mondhygiën", "tandheelkund",
            "tandartsenpraktijk", "tandartspraktijk",
        ],
        content_keywords={
            "tand": 5, "kies": 4, "vulling": 5, "wortelkanaal": 5,
            "tandarts": 5, "gebit": 4, "mondhygiën": 5, "brug": 3,
            "kroon": 4, "implantaat": 5, "röntgen": 3, "tandvlees": 4,
            "beugel": 4, "extractie": 4, "verdoving": 3, "bleek": 3,
            "cariës": 4, "kaakchirurg": 4, "prothese": 4,
        },
        scope_re=re.compile(
            r"\b(?:tand\w*|kies|kiezen|vulling\w*|wortelkanaal\w*|"
            r"tandarts\w*|gebit\w*|mondhygiën\w*|brug|kroon|"
            r"implanta\w+|röntgen|tandvlees|beugel|extractie|"
            r"verdoving|bleek\w*|cariës|kaak\w*|prothese|"
            r"fluor\w*|gaatje\w*|sanering|behandeling\w*)\b",
            re.I,
        ),
    ),
    "car_garage": BusinessProfile(
        name_hints=[
            "garage", "autogarage", "autobedrijf", "autoservice",
            "carservice", "werkplaats", "autohersteller", "bandencentrale",
            "bandenwisselcentrum",
        ],
        content_keywords={
            "auto": 4, "motor": 3, "band": 3, "olie": 4, "remmen": 4,
            "APK": 5, "reparatie": 4, "onderhoud": 4, "airco": 4,
            "diagnose": 3, "schade": 3, "lakwerk": 4, "uitlaat": 4,
            "monteur": 5, "garage": 5, "distributieriem": 4,
            "koppeling": 4, "versnelling": 3, "carrosserie": 4,
            "wielbalans": 4, "oliewissel": 5, "koppakking": 4,
        },
        scope_re=re.compile(
            r"\b(?:auto\w*|motor\w*|band\w*|olie\w*|rem\w+|"
            r"APK|reparati\w*|onderhoud\w*|airco\w*|diagnos\w*|"
            r"schade\w*|lak\w*|uitlaa?t\w*|monteur\w*|garage\w*|"
            r"distributieriem|koppeling\w*|versnelling\w*|"
            r"carrosser\w*|wielbalans|oliewissel|koppakking|"
            r"dashboard\w*|start\s+niet|"
            r"aanslaan|lek\w*|bumper\w*|kras\w*)\b",
            re.I,
        ),
    ),
    "pizza_restaurant": BusinessProfile(
        name_hints=[
            "pizza", "pizzeria", "pizza's",
        ],
        content_keywords={
            "pizza": 6, "margherita": 5, "tonno": 4, "hawaii": 3,
            "calzone": 4, "pasta": 3, "menu": 3, "bezorg": 5,
            "bestel": 4, "afhaal": 4, "restaurant": 3, "oven": 3,
            "deeg": 3, "mozzarella": 4, "topping": 4,
        },
        scope_re=re.compile(
            r"\b(?:pizza\w*|margherita|tonno|hawai\w*|calzone|"
            r"pasta\w*|menu\w*|bezorg\w*|bestel\w*|afhaal\w*|"
            r"deeg|mozzarella|topping\w*|portie\w*|"
            r"eten\w*|maaltijd|gerecht\w*|bediening\w*|"
            r"reserv\w*|tafeltje\w*|wijn\w*|chef\w*|"
            r"driegangen\w*|restaurant\w*|keuken|"
            r"glutenvrij|allergi\w*|dieet\w*|vegan\w*|vegetar\w*)\b",
            re.I,
        ),
        off_topic_exemptions={
            "pizza", "bezorg", "bestellen", "bestel",
            "eten", "sushi", "recept",
        },
    ),
    "restaurant": BusinessProfile(
        name_hints=[
            "restaurant", "bistro", "brasserie", "eetcafé", "eetcafe",
            "trattoria", "grand café", "grand cafe", "lunchroom",
        ],
        content_keywords={
            "restaurant": 5, "reserv": 4, "tafeltje": 4, "menu": 4,
            "diner": 4, "lunch": 4, "wijn": 3, "dessert": 3,
            "voorgerecht": 4, "hoofdgerecht": 4, "chef": 3,
            "kok": 3, "bediening": 3, "portie": 3, "driegangen": 4,
            "kaart": 3, "terras": 3, "brunch": 3,
        },
        scope_re=re.compile(
            r"\b(?:restaurant\w*|reserv\w*|tafeltje\w*|menu\w*|"
            r"diner\w*|lunch\w*|wijn\w*|dessert\w*|voorgerecht\w*|"
            r"hoofdgerecht\w*|chef\w*|kok\w*|bediening\w*|"
            r"portie\w*|driegangen\w*|kaart|terras\w*|brunch\w*|"
            r"eten\w*|maaltijd|gerecht\w*|keuken|bezorg\w*|"
            r"pizza\w*|pasta\w*|"
            r"glutenvrij|allergi\w*|dieet\w*|vegan\w*|vegetar\w*)\b",
            re.I,
        ),
        off_topic_exemptions={
            "pizza", "eten", "recept", "bezorg",
        },
    ),
    "ai_saas": BusinessProfile(
        name_hints=[
            "klantenservice.ai", "klantenservice", "ai",
            "saas", "software", "platform", "tech",
        ],
        content_keywords={
            "dashboard": 4, "API": 5, "integratie": 4, "abonnement": 4,
            "pakket": 3, "plan": 3, "voice": 5, "agent": 4,
            "demo": 4, "trial": 4, "onboarding": 4, "webhook": 4,
            "SaaS": 5, "belminut": 5, "calls": 4, "configuratie": 3,
            "AI": 5, "bot": 3, "telefoon": 3, "klantenservice": 5,
        },
        scope_re=re.compile(
            r"\b(?:dashboard\w*|API|integrati\w*|abonnement\w*|"
            r"\w*pakket\w*|voice\s*agent|demo|trial|onboarding|"
            r"webhook\w*|SaaS|belminut\w*|calls?|configurati\w*|"
            r"upgrade\w*|downgrade\w*|inloggen|login|"
            r"proefperiode\w*|widget|plugin|koppeling)\b",
            re.I,
        ),
    ),
    "general": BusinessProfile(
        name_hints=[],
        content_keywords={},
        scope_re=re.compile(r"(?!x)x"),  # never matches
    ),
}


# ═══════════════════════════════════════════════════════════════════
#  INFERENCE FUNCTION
# ═══════════════════════════════════════════════════════════════════

_MIN_CONFIDENCE = 0.15
_NAME_BOOST = 25


def infer_business_type(
    company_name: str,
    chunk_contents: Optional[list[str]] = None,
) -> dict:
    """
    Infer a company's business type from its name and indexed content.

    Returns:
        {
            "business_type": str,        # e.g. "hair_salon"
            "confidence": float,         # 0.0–1.0
            "topics": list[str],         # top matched keywords
            "scores": dict[str, float],  # raw score per type
        }
    """
    scores: dict[str, float] = {}
    topic_hits: dict[str, list[str]] = {}

    name_lower = company_name.lower() if company_name else ""
    all_content = ""
    if chunk_contents:
        all_content = " ".join(chunk_contents).lower()

    for btype, profile in PROFILES.items():
        if btype == "general":
            continue

        score = 0.0
        hits: list[str] = []

        # Name matching (strong signal)
        for hint in profile.name_hints:
            if hint.lower() in name_lower:
                score += _NAME_BOOST
                hits.append(f"name:{hint}")
                break

        # Content keyword frequency
        if all_content:
            for keyword, weight in profile.content_keywords.items():
                kw_lower = keyword.lower()
                count = all_content.count(kw_lower)
                if count > 0:
                    capped = min(count, 15)
                    score += capped * weight
                    hits.append(keyword)

        scores[btype] = score
        topic_hits[btype] = hits

    total = sum(scores.values())
    if total == 0:
        return {
            "business_type": "general",
            "confidence": 0.0,
            "topics": [],
            "scores": scores,
        }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    confidence = best_score / total

    if confidence < _MIN_CONFIDENCE:
        return {
            "business_type": "general",
            "confidence": confidence,
            "topics": [],
            "scores": scores,
        }

    topics = [t for t in topic_hits[best_type] if not t.startswith("name:")][:15]

    return {
        "business_type": best_type,
        "confidence": round(confidence, 3),
        "topics": topics,
        "scores": scores,
    }


def update_company_inference(db, company) -> dict:
    """
    Run inference for a company using its name and all indexed chunks,
    then update the company record.
    """
    from app.services.indexing.models import IdxChunk

    chunks = db.query(IdxChunk.content).filter(
        IdxChunk.company_id == company.id,
    ).all()

    chunk_contents = [c[0] for c in chunks if c[0]]

    result = infer_business_type(company.name, chunk_contents)

    company.inferred_business_type = result["business_type"]
    company.inferred_business_confidence = result["confidence"]
    company.inferred_topics = result["topics"]
    db.commit()

    logger.info(
        "Inferred business type for %s: %s (%.1f%%, %d topics)",
        company.name, result["business_type"],
        result["confidence"] * 100, len(result["topics"]),
    )

    return result
