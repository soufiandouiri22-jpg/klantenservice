"""
URL utilities: normalisation, domain checking, page-type hints from URL.
"""
import re
from typing import Optional
from urllib.parse import urlparse, urljoin


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized.lower()


def is_same_domain(url: str, base_domain: str) -> bool:
    return urlparse(url).netloc.lower() == base_domain.lower()


def resolve_url(href: str, base_url: str) -> Optional[str]:
    """Resolve a relative href against a base URL. Returns None for non-HTTP URLs."""
    full = urljoin(base_url, href)
    parsed = urlparse(full)
    if parsed.scheme not in ("http", "https"):
        return None
    return full


SKIP_EXTENSIONS = frozenset([
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".json", ".xml", ".zip", ".mp4", ".mp3", ".woff",
    ".woff2", ".ttf", ".eot", ".map",
])


def should_skip_url(url: str, blocked_paths: list[str] | None = None) -> bool:
    parsed = urlparse(url)
    path_lower = parsed.path.lower()

    if any(path_lower.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True

    for blocked in (blocked_paths or []):
        if path_lower.startswith(blocked.lower()):
            return True

    return False


# Rule-based page type hint from URL path
_URL_TYPE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^/?$"), "home"),
    (re.compile(r"/(prijs|pricing|plans|tarieven|kosten|packages)", re.I), "pricing"),
    (re.compile(r"/(faq|veelgestelde|frequently)", re.I), "faq"),
    (re.compile(r"/(contact|contacteer|bereik)", re.I), "contact"),
    (re.compile(r"/(over|about|wie-zijn-wij|team)", re.I), "about"),
    (re.compile(r"/(dienst|service|aanbod|oplossing)", re.I), "service"),
    (re.compile(r"/(product|webshop|shop|winkel)", re.I), "product"),
    (re.compile(r"/(privacy|voorwaarden|terms|policy|cookie|disclaimer|retour|annuler|verzend)", re.I), "policy"),
    (re.compile(r"/(blog|nieuws|news|artikel|article)", re.I), "blog"),
    (re.compile(r"/(locatie|vestiging|location|filiaal|adres)", re.I), "location"),
]


def classify_page_type_from_url(url: str) -> str:
    path = urlparse(url).path
    for pattern, page_type in _URL_TYPE_PATTERNS:
        if pattern.search(path):
            return page_type
    return "unknown"
