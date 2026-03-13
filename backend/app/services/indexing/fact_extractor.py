"""
Structured business fact extraction.

Runs after chunking during indexing.  Scans pages and chunks for
pricing plans, contact info, opening hours, locations, and services,
then writes deterministic rows to the business_* tables.

These rows are queried at runtime *before* RAG so the voice AI can
give stable answers for questions like "Wat zijn jullie prijzen?"
"""
import logging
import re
from datetime import time as dt_time
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.business_facts import (
    PricingPlan,
    ContactInfo,
    OpeningHours,
    BusinessLocation,
    BusinessService,
)

logger = logging.getLogger(__name__)

# ── Shared regex ──────────────────────────────────────────────────

_PRICE_RE = re.compile(
    r"€\s*(\d+[\d.,]*)"
    r"|(\d+[\d.,]*)\s*(?:euro|EUR)"
    r"|[£$]\s*(\d+[\d.,]*)"
    r"|(\d+[\d.,]*)\s*(?:GBP|USD)",
    re.I,
)

_CURRENCY_RE = re.compile(r"[£$]|GBP|USD", re.I)

_PER_PERIOD_RE = re.compile(
    r"per\s+(?P<period>maand|jaar|month|year|week)"
    r"|/\s*(?P<slash>mo|yr|maand|jaar|month|year|week)",
    re.I,
)

_PLAN_NAME_RE = re.compile(
    r"\b(starter|basic|standaard|standard|business|professional|pro|"
    r"premium|enterprise|plus|growth|advanced|lite|team)\b",
    re.I,
)

_CONTACT_REQUIRED_RE = re.compile(
    r"op\s+aanvraag|neem\s+contact\s+op|contact\s+us"
    r"|request\s+(?:pricing|quote|a\s+quote)|offerte"
    r"|custom\s+pricing|enterprise\s+pricing",
    re.I,
)

_FREE_TRIAL_RE = re.compile(
    r"gratis\s+(?:proef|trial|probeer|uitproberen|starten|testen)"
    r"|(?:probeer|start|test)\w*\s+(?:het\s+)?gratis"
    r"|dagen?\s+gratis"
    r"|gratis\s+(?:uit|•|,|\.|$)"
    r"|free\s+trial",
    re.I,
)

_PHONE_RE = re.compile(r"(?:\+31|0)\s*[\d\s\-().]{7,15}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_POSTCODE_RE = re.compile(r"\b(\d{4})\s?([A-Z]{2})\b")

_WEEKDAY_MAP: Dict[str, int] = {
    "ma": 0, "maandag": 0, "monday": 0, "mon": 0,
    "di": 1, "dinsdag": 1, "tuesday": 1, "tue": 1,
    "wo": 2, "woensdag": 2, "wednesday": 2, "wed": 2,
    "do": 3, "donderdag": 3, "thursday": 3, "thu": 3,
    "vr": 4, "vrijdag": 4, "friday": 4, "fri": 4,
    "za": 5, "zaterdag": 5, "saturday": 5, "sat": 5,
    "zo": 6, "zondag": 6, "sunday": 6, "sun": 6,
}

_HOURS_LINE_RE = re.compile(
    r"(?P<day1>ma(?:andag)?|di(?:nsdag)?|wo(?:ensdag)?|do(?:nderdag)?|"
    r"vr(?:ijdag)?|za(?:terdag)?|zo(?:ndag)?|"
    r"mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
    r"(?:\s*(?:t/m|-|–|tot)\s*"
    r"(?P<day2>ma(?:andag)?|di(?:nsdag)?|wo(?:ensdag)?|do(?:nderdag)?|"
    r"vr(?:ijdag)?|za(?:terdag)?|zo(?:ndag)?|"
    r"mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?))?"
    r"[\s:]+(?P<open>\d{1,2})[.:](?P<open_m>\d{2})"
    r"\s*(?:-|–|tot|to)\s*"
    r"(?P<close>\d{1,2})[.:](?P<close_m>\d{2})"
    r"(?:.*?(?P<closed>gesloten|closed))?",
    re.I,
)

_CLOSED_LINE_RE = re.compile(
    r"(?P<day1>ma(?:andag)?|di(?:nsdag)?|wo(?:ensdag)?|do(?:nderdag)?|"
    r"vr(?:ijdag)?|za(?:terdag)?|zo(?:ndag)?|"
    r"mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
    r"[\s:]+(?:gesloten|closed|dicht)",
    re.I,
)

_SERVICE_BULLET_RE = re.compile(
    r"^[\s]*[-•✓*]\s+(.{3,80})$", re.MULTILINE,
)

_ADDRESS_RE = re.compile(
    r"([A-Z][a-zéèëïöüá]+(?:straat|laan|weg|plein|kade|gracht|singel|hof|dreef|pad|steeg|dijk|park)\s+\d+\w?)",
    re.MULTILINE,
)

_CITY_RE = re.compile(
    r"\b\d{4}\s?[A-Z]{2}\s+([A-Z][a-zéèëïöüá]+(?:\s+[a-z]+)?)\b",
)


# ── Main entry point ─────────────────────────────────────────────

def extract_business_facts(
    db: Session,
    company_id: str,
    site_id: str,
    pages: List[Dict],
    chunks: List[Dict],
) -> Dict[str, int]:
    """
    Extract structured business facts from crawled pages and chunks.

    Args:
        db: database session
        company_id: UUID string
        site_id: UUID string
        pages: list of dicts with at least {url, page_type, cleaned_content, title}
        chunks: list of dicts with at least {content, chunk_type, url, page_title}

    Returns:
        dict with counts per fact type
    """
    _delete_existing(db, company_id, site_id)

    all_text_blocks = _collect_text_blocks(pages, chunks)

    counts: Dict[str, int] = {}
    counts["pricing"] = _extract_pricing(db, company_id, site_id, all_text_blocks)
    counts["contact"] = _extract_contact(db, company_id, site_id, all_text_blocks)
    counts["hours"] = _extract_hours(db, company_id, site_id, all_text_blocks)
    counts["locations"] = _extract_locations(db, company_id, site_id, all_text_blocks)
    counts["services"] = _extract_services(db, company_id, site_id, all_text_blocks)

    db.flush()
    logger.info(
        "[fact_extractor] company=%s site=%s extracted: %s",
        company_id, site_id, counts,
    )
    return counts


# ── Helpers ───────────────────────────────────────────────────────

def _delete_existing(db: Session, company_id: str, site_id: str) -> None:
    for model in (PricingPlan, ContactInfo, OpeningHours, BusinessLocation, BusinessService):
        db.query(model).filter_by(company_id=company_id).delete()


def _collect_text_blocks(pages: List[Dict], chunks: List[Dict]) -> List[Dict]:
    """Merge page and chunk texts into a unified list of text blocks."""
    blocks: List[Dict] = []
    seen: set = set()

    for p in pages:
        content = (p.get("cleaned_content") or "").strip()
        if not content:
            continue
        key = hash(content[:200])
        if key in seen:
            continue
        seen.add(key)
        blocks.append({
            "text": content,
            "url": p.get("url", ""),
            "title": p.get("title", ""),
            "page_type": p.get("page_type", "unknown"),
            "chunk_type": None,
        })

    for c in chunks:
        content = (c.get("content") or "").strip()
        if not content:
            continue
        key = hash(content[:200])
        if key in seen:
            continue
        seen.add(key)
        blocks.append({
            "text": content,
            "url": c.get("url", ""),
            "title": c.get("page_title", ""),
            "page_type": None,
            "chunk_type": c.get("chunk_type", "general"),
        })

    return blocks


# ── Pricing ───────────────────────────────────────────────────────

def _parse_price(raw: str) -> Optional[Decimal]:
    cleaned = raw.replace(".", "").replace(",", ".").strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _detect_currency(text: str) -> str:
    if "$" in text or re.search(r"\bUSD\b", text, re.I):
        return "USD"
    if "£" in text or re.search(r"\bGBP\b", text, re.I):
        return "GBP"
    return "EUR"


def _detect_period(text: str) -> Optional[str]:
    m = _PER_PERIOD_RE.search(text)
    if not m:
        return None
    raw = (m.group("period") or m.group("slash") or "").lower()
    mapping = {
        "maand": "maand", "mo": "maand", "month": "maand",
        "jaar": "jaar", "yr": "jaar", "year": "jaar",
        "week": "week",
    }
    return mapping.get(raw)


def _extract_pricing(
    db: Session, company_id: str, site_id: str, blocks: List[Dict],
) -> int:
    """Extract pricing plans from text blocks."""
    pricing_texts: List[Tuple[str, str]] = []

    for b in blocks:
        text = b["text"]
        url = b["url"]
        is_pricing_page = b.get("page_type") == "pricing" or b.get("chunk_type") == "pricing"
        has_price_signal = bool(_PRICE_RE.search(text))
        has_plan_name = bool(_PLAN_NAME_RE.search(text))
        has_contact_price = bool(_CONTACT_REQUIRED_RE.search(text))

        if is_pricing_page or (has_plan_name and (has_price_signal or has_contact_price)):
            pricing_texts.append((text, url))

    if not pricing_texts:
        return 0

    combined = "\n\n---\n\n".join(t for t, _ in pricing_texts)
    source_url = pricing_texts[0][1]

    plans = _parse_plans(combined, source_url)

    seen_names: set = set()
    saved = 0
    for i, plan in enumerate(plans):
        name_key = plan["name"].lower()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        db.add(PricingPlan(
            id=uuid4(),
            company_id=company_id,
            site_id=site_id,
            name=plan["name"],
            price=plan.get("price"),
            currency=plan.get("currency", "EUR"),
            billing_period=plan.get("billing_period"),
            price_type=plan["price_type"],
            description=plan.get("description"),
            features=plan.get("features"),
            display_order=i,
            source_url=plan.get("source_url", source_url),
        ))
        saved += 1

    return saved


_PROXIMITY_CHARS = 150


def _find_price_after(text: str, start_pos: int) -> Tuple[Optional[Decimal], Optional[str]]:
    """Find the first valid €-price in the text within _PROXIMITY_CHARS after start_pos."""
    end_pos = min(len(text), start_pos + _PROXIMITY_CHARS)
    window = text[start_pos:end_pos]

    m = _PRICE_RE.search(window)
    if not m:
        return None, "EUR"

    raw = next((g for g in m.groups() if g), None)
    if not raw:
        return None, "EUR"

    price = _parse_price(raw)
    if price is None or price <= 0:
        return None, "EUR"

    currency = _detect_currency(window[m.start():m.end() + 20])
    return price, currency


def _parse_plans(text: str, default_url: str) -> List[Dict]:
    """Parse individual plans from combined pricing text."""
    plans: List[Dict] = []
    seen_names: set = set()

    for m in _PLAN_NAME_RE.finditer(text):
        pname = m.group(1)
        name_key = pname.lower()
        if name_key in seen_names:
            continue

        plan = _extract_single_plan(text, pname, m.start(), default_url)
        if plan:
            seen_names.add(name_key)
            plans.append(plan)

    return plans


def _find_plan_boundary(text: str, name_pos: int) -> int:
    """Find end of a plan section: the next plan name occurrence or end of text."""
    search_from = name_pos + 5
    m = _PLAN_NAME_RE.search(text[search_from:])
    if m:
        return search_from + m.start()
    return len(text)


def _extract_single_plan(
    text: str, plan_name: str, name_pos: int, source_url: str,
) -> Optional[Dict]:
    """Extract a single plan's details using the text near name_pos."""
    name = plan_name.strip().capitalize()

    window_start = max(0, name_pos - 20)
    window_end = min(len(text), name_pos + _PROXIMITY_CHARS)
    window = text[window_start:window_end]

    price, currency = _find_price_after(text, name_pos)
    billing_period = _detect_period(window)

    nearby_contact = bool(_CONTACT_REQUIRED_RE.search(window))

    if price is not None:
        price_type = "fixed"
    elif nearby_contact:
        price_type = "contact_required"
    else:
        return None

    boundary = _find_plan_boundary(text, name_pos)
    feature_section = text[name_pos:boundary]
    features = []
    for line in feature_section.split("\n"):
        line = line.strip()
        if line.startswith(("- ", "• ", "✓ ", "* ")):
            feat = line.lstrip("-•✓* ").strip()
            if feat and 3 < len(feat) < 120:
                features.append(feat)

    desc_from_name = text[name_pos:name_pos + 300]
    desc_lines = [
        l.strip() for l in desc_from_name.split("\n")
        if l.strip() and not l.strip().startswith(("#", "-", "•", "✓", "*"))
    ]
    description = " ".join(desc_lines[:3])[:500] if desc_lines else None

    return {
        "name": name,
        "price": price,
        "currency": currency,
        "billing_period": billing_period,
        "price_type": price_type,
        "description": description,
        "features": features[:20] or None,
        "source_url": source_url,
    }


# ── Contact ───────────────────────────────────────────────────────

def _extract_contact(
    db: Session, company_id: str, site_id: str, blocks: List[Dict],
) -> int:
    phones: List[str] = []
    emails: List[str] = []
    source_url = ""

    for b in blocks:
        text = b["text"]
        is_contact = b.get("page_type") == "contact" or b.get("chunk_type") == "contact"

        found_phones = _PHONE_RE.findall(text)
        found_emails = _EMAIL_RE.findall(text)

        if found_phones or found_emails or is_contact:
            if not source_url and b["url"]:
                source_url = b["url"]
            phones.extend(p.strip() for p in found_phones)
            emails.extend(found_emails)

    phones = list(dict.fromkeys(phones))[:5]
    emails = list(dict.fromkeys(emails))[:5]

    if not phones and not emails:
        return 0

    db.add(ContactInfo(
        id=uuid4(),
        company_id=company_id,
        site_id=site_id,
        phone=phones[0] if phones else None,
        email=emails[0] if emails else None,
        source_url=source_url,
    ))
    return 1


# ── Opening Hours ─────────────────────────────────────────────────

def _extract_hours(
    db: Session, company_id: str, site_id: str, blocks: List[Dict],
) -> int:
    hours_rows: Dict[int, Dict] = {}
    source_url = ""

    for b in blocks:
        text = b["text"]
        if not source_url and b["url"]:
            source_url = b["url"]

        for m in _HOURS_LINE_RE.finditer(text):
            day1_str = m.group("day1").lower()
            day2_str = (m.group("day2") or "").lower()

            day1 = _WEEKDAY_MAP.get(day1_str)
            if day1 is None:
                continue

            try:
                open_t = dt_time(int(m.group("open")), int(m.group("open_m")))
                close_t = dt_time(int(m.group("close")), int(m.group("close_m")))
            except (ValueError, TypeError):
                continue

            if day2_str:
                day2 = _WEEKDAY_MAP.get(day2_str)
                if day2 is not None:
                    d = day1
                    while True:
                        hours_rows[d] = {"open": open_t, "close": close_t, "closed": False}
                        if d == day2:
                            break
                        d = (d + 1) % 7
                    continue

            hours_rows[day1] = {"open": open_t, "close": close_t, "closed": False}

        for m in _CLOSED_LINE_RE.finditer(text):
            day_str = m.group("day1").lower()
            day = _WEEKDAY_MAP.get(day_str)
            if day is not None:
                hours_rows[day] = {"open": None, "close": None, "closed": True}

    if not hours_rows:
        return 0

    for weekday, info in sorted(hours_rows.items()):
        db.add(OpeningHours(
            id=uuid4(),
            company_id=company_id,
            site_id=site_id,
            weekday=weekday,
            open_time=info["open"],
            close_time=info["close"],
            closed=info["closed"],
            source_url=source_url,
        ))

    return len(hours_rows)


# ── Locations ─────────────────────────────────────────────────────

def _extract_locations(
    db: Session, company_id: str, site_id: str, blocks: List[Dict],
) -> int:
    locations: List[Dict] = []
    seen_postcodes: set = set()

    for b in blocks:
        text = b["text"]
        url = b["url"]

        postcodes = _POSTCODE_RE.findall(text)
        addresses = _ADDRESS_RE.findall(text)
        cities = _CITY_RE.findall(text)

        if not postcodes and not addresses:
            continue

        for pc_digits, pc_letters in postcodes:
            pc = f"{pc_digits} {pc_letters}"
            if pc in seen_postcodes:
                continue
            seen_postcodes.add(pc)

            city = cities[0] if cities else None
            address = addresses[0] if addresses else None

            locations.append({
                "address": address,
                "city": city,
                "postal_code": pc,
                "source_url": url,
            })

    if not locations:
        return 0

    for loc in locations[:10]:
        db.add(BusinessLocation(
            id=uuid4(),
            company_id=company_id,
            site_id=site_id,
            address=loc.get("address"),
            city=loc.get("city"),
            postal_code=loc.get("postal_code"),
            source_url=loc.get("source_url"),
        ))

    return len(locations)


# ── Services ──────────────────────────────────────────────────────

def _extract_services(
    db: Session, company_id: str, site_id: str, blocks: List[Dict],
) -> int:
    service_names: List[Tuple[str, str]] = []
    seen: set = set()

    for b in blocks:
        is_service = b.get("page_type") == "service" or b.get("chunk_type") == "service"
        text = b["text"]
        url = b["url"]

        if not is_service:
            continue

        bullets = _SERVICE_BULLET_RE.findall(text)
        for item in bullets:
            name = item.strip()
            if name.lower() in seen or len(name) < 3:
                continue
            seen.add(name.lower())
            service_names.append((name, url))

    if not service_names:
        return 0

    for name, url in service_names[:50]:
        db.add(BusinessService(
            id=uuid4(),
            company_id=company_id,
            site_id=site_id,
            name=name,
            source_url=url,
        ))

    return len(service_names)
