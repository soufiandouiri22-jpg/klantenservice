"""
Page type & chunk type classification — rule-based, fast, deterministic.
"""
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Page type classification
# ---------------------------------------------------------------------------

_PAGE_TYPE_RULES: list[tuple[re.Pattern, str]] = [
    # URL patterns
    (re.compile(r"/(prijs|pricing|plans?|tarieven|kosten|packages?)", re.I), "pricing"),
    (re.compile(r"/(faq|veelgestelde|frequently)", re.I), "faq"),
    (re.compile(r"/(contact|contacteer|bereik-ons)", re.I), "contact"),
    (re.compile(r"/(over-ons|about|wie-zijn-wij|team|ons-verhaal)", re.I), "about"),
    (re.compile(r"/(dienst|service|aanbod|oplossing|wat-wij-doen)", re.I), "service"),
    (re.compile(r"/(product|webshop|shop|winkel|collectie)", re.I), "product"),
    (re.compile(r"/(privacy|voorwaarden|terms|policy|cookie|disclaimer|retour|annuler|verzend|garantie)", re.I), "policy"),
    (re.compile(r"/(blog|nieuws|news|artikel|article|magazine)", re.I), "blog"),
    (re.compile(r"/(locatie|vestiging|location|filiaal|adres|route)", re.I), "location"),
]

_HOME_PATH = re.compile(r"^/?$")


def classify_page_type(
    url: str = "",
    title: str = "",
    h1: str = "",
    content: str = "",
) -> str:
    """Classify a page into one of the known page types."""
    from urllib.parse import urlparse
    path = urlparse(url).path if url else ""

    if _HOME_PATH.match(path):
        return "home"

    # Check URL path
    for pattern, ptype in _PAGE_TYPE_RULES:
        if pattern.search(path):
            return ptype

    # Check title / h1
    combined = f"{title} {h1}".lower()
    if any(w in combined for w in ("prijs", "pricing", "tarief", "kosten", "pakket")):
        return "pricing"
    if any(w in combined for w in ("faq", "veelgestelde", "frequently asked")):
        return "faq"
    if any(w in combined for w in ("contact", "bereik", "neem contact")):
        return "contact"
    if any(w in combined for w in ("over ons", "about", "wie zijn wij", "ons team")):
        return "about"
    if any(w in combined for w in ("privacy", "voorwaarden", "terms", "beleid", "retour")):
        return "policy"
    if any(w in combined for w in ("blog", "nieuws", "article", "artikel")):
        return "blog"
    if any(w in combined for w in ("locatie", "vestiging", "adres", "route")):
        return "location"

    # Content signals (first 2000 chars)
    snippet = content[:2000].lower() if content else ""
    if snippet.count("€") >= 2 or snippet.count("per maand") >= 2:
        return "pricing"
    if snippet.count("?") >= 4:
        return "faq"

    return "unknown"


# ---------------------------------------------------------------------------
# Chunk type classification
# ---------------------------------------------------------------------------

def classify_chunk_type(
    text: str,
    page_type: str = "unknown",
    section_path: str = "",
    heading: str = "",
) -> str:
    """Classify an individual chunk into a chunk type."""
    lower = text.lower()
    heading_lower = heading.lower() if heading else ""
    section_lower = section_path.lower() if section_path else ""

    # FAQ: contains question-like patterns
    q_count = len(re.findall(r"\?\s*\n", text))
    if q_count >= 1 and page_type == "faq":
        return "faq"
    if q_count >= 2:
        return "faq"
    if any(w in heading_lower for w in ("faq", "veelgestelde", "vraag")):
        return "faq"

    # Pricing: contains price indicators
    price_signals = (
        lower.count("€") + lower.count("per maand") + lower.count("/mo")
        + lower.count("per jaar") + lower.count("/yr")
    )
    if price_signals >= 2:
        return "pricing"
    if any(w in heading_lower for w in ("prijs", "pricing", "tarief", "pakket", "plan")):
        return "pricing"
    if page_type == "pricing":
        return "pricing"

    # Contact
    contact_signals = _count_contact_signals(lower)
    if contact_signals >= 2:
        return "contact"
    if any(w in heading_lower for w in ("contact", "bereik", "openingstijden", "adres")):
        return "contact"
    if page_type == "contact":
        return "contact"

    # Location
    if any(w in heading_lower for w in ("locatie", "vestiging", "adres", "route")):
        return "location"
    if page_type == "location":
        return "location"

    # Policy
    if any(w in heading_lower for w in ("privacy", "voorwaarden", "retour", "annuler", "beleid", "garantie", "verzend")):
        return "policy"
    if page_type == "policy":
        return "policy"

    # Product / service
    if page_type == "product":
        return "product"
    if page_type == "service":
        return "service"

    # Blog
    if page_type == "blog":
        return "blog"

    return "general"


def _count_contact_signals(text: str) -> int:
    count = 0
    if re.search(r"\b\d{2,4}[\s\-]?\d{3,4}[\s\-]?\d{2,4}\b", text):
        count += 1
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
        count += 1
    if any(w in text for w in ("openingstijden", "bereikbaar", "ma t/m", "maandag")):
        count += 1
    if any(w in text for w in ("adres", "postcode", "straat")):
        count += 1
    return count
