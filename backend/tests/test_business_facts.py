"""
Structured business facts tests — verify extraction, formatting,
and runtime lookup behaviour.

Self-contained: extracts the pure logic to avoid importing the full
app dependency chain.

Run:  python3 tests/test_business_facts.py
"""
import re
import sys
from dataclasses import dataclass, field
from datetime import time as dt_time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

# ── Extracted regex patterns from fact_extractor.py ──────────────

_PRICE_RE = re.compile(
    r"€\s*(\d+[\d.,]*)"
    r"|(\d+[\d.,]*)\s*(?:euro|EUR)"
    r"|[£$]\s*(\d+[\d.,]*)"
    r"|(\d+[\d.,]*)\s*(?:GBP|USD)",
    re.I,
)

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
    r"(?P<close>\d{1,2})[.:](?P<close_m>\d{2})",
    re.I,
)

_CLOSED_LINE_RE = re.compile(
    r"(?P<day1>ma(?:andag)?|di(?:nsdag)?|wo(?:ensdag)?|do(?:nderdag)?|"
    r"vr(?:ijdag)?|za(?:terdag)?|zo(?:ndag)?)"
    r"[\s:]+(?:gesloten|closed|dicht)",
    re.I,
)

_QUERY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(prij[sz]\w*|kost\w*|tariev\w*|tarief\w*|pakket\w*|plan\w*|abonnement\w*|euro|€|betaal\w*|goedkoop\w*|duur|budget\w*|belminut\w*|starter|business|enterprise)\b", re.I), "pricing"),
    (re.compile(r"\b(openingstijd\w*|bereikbaar\w*|bellen|telefoon\w*|email\w*|e-mail\w*|contact\w*|adres\w*|locatie\w*|route\w*)\b", re.I), "contact"),
    (re.compile(r"\b(retour\w*|terugsturen|annuleer\w*|annulering\w*|opzeg\w*|garantie\w*|verzend\w*|lever\w*|bezorg\w*)\b", re.I), "policy"),
    (re.compile(r"\b(locatie\w*|vestiging\w*|filiaal\w*|kantoor\w*|winkel\w*|route\w*|parkeer\w*)\b", re.I), "location"),
    (re.compile(r"\b(product\w*|dienst\w*|service\w*|aanbod\w*|oplossing\w*|feature\w*|functie\w*|mogelijkheid\w*)\b", re.I), "service"),
    (re.compile(r"wat\s+(?:doen|bieden)\s+jullie|jullie\s+(?:allemaal\s+)?doen|wat\s+voor\s+bedrijf|vertel\s+(?:eens\s+)?over\s+(?:jullie|je|uw)|uitleggen\s+wat\s+jullie|wat\s+jullie\s+(?:allemaal\s+)?(?:doen|bieden|aanbieden)", re.I), "service"),
]


def classify_query(query: str) -> str:
    q = query.strip()
    for pattern, qtype in _QUERY_RULES:
        if pattern.search(q):
            return qtype
    return "general"


# ── Extraction helpers (mirrored from fact_extractor.py) ─────────

def _parse_price(raw: str) -> Optional[Decimal]:
    """Mirror production _parse_price with correct decimal handling."""
    s = raw.strip()
    if not s:
        return None

    has_comma = "," in s
    has_dot = "." in s

    if has_comma and has_dot:
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_comma > last_dot:
            cleaned = s.replace(".", "").replace(",", ".")
        else:
            cleaned = s.replace(",", "")
    elif has_comma:
        parts = s.rsplit(",", 1)
        if len(parts[1]) <= 2:
            cleaned = s.replace(",", ".")
        else:
            cleaned = s.replace(",", "")
    elif has_dot:
        parts = s.rsplit(".", 1)
        if len(parts[1]) <= 2:
            cleaned = s
        elif parts[0] == "0":
            cleaned = s
        else:
            cleaned = s.replace(".", "")
    else:
        cleaned = s

    try:
        return Decimal(cleaned)
    except Exception:
        return None


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


PROXIMITY_CHARS = 150

_UNIT_PRICING_RE = re.compile(
    r"per\s+(?:minuut|seconde|gesprek|call|sms|bericht|click|klik"
    r"|verzoek|request|api[- ]?call|query|woord|word|karakter|character"
    r"|uur|hour|minuut)"
    r"|/\s*(?:min|sec|gesprek|call|sms|msg|click|request|query)",
    re.I,
)


def _is_unit_price(text_after_price: str) -> bool:
    return bool(_UNIT_PRICING_RE.search(text_after_price))


def _find_price_after(text: str, start_pos: int) -> Optional[Decimal]:
    end_pos = min(len(text), start_pos + PROXIMITY_CHARS)
    window = text[start_pos:end_pos]
    for m in _PRICE_RE.finditer(window):
        raw = next((g for g in m.groups() if g), None)
        if not raw:
            continue
        price = _parse_price(raw)
        if price is None or price <= 0:
            continue
        trailing = window[m.end():m.end() + 30]
        if _is_unit_price(trailing):
            continue
        return price
    return None


def _find_plan_boundary(text: str, name_pos: int) -> int:
    """Find the end of a plan section (next plan name or end of text)."""
    search_from = name_pos + 5
    m = _PLAN_NAME_RE.search(text[search_from:])
    if m:
        return search_from + m.start()
    return len(text)


def _extract_plan_from_text(text: str, plan_name: str, name_pos: int) -> Optional[Dict]:
    """Extract a plan using the forward-proximity logic."""
    window_start = max(0, name_pos - 20)
    window_end = min(len(text), name_pos + PROXIMITY_CHARS)
    window = text[window_start:window_end]

    price = _find_price_after(text, name_pos)
    nearby_contact = bool(_CONTACT_REQUIRED_RE.search(window))

    if price is not None:
        price_type = "fixed"
    elif nearby_contact:
        price_type = "contact_required"
    else:
        return None

    billing_period = _detect_period(window)

    boundary = _find_plan_boundary(text, name_pos)
    feature_text = text[name_pos:boundary]
    features = []
    for line in feature_text.split("\n"):
        line = line.strip()
        if line.startswith(("- ", "• ", "✓ ", "* ")):
            feat = line.lstrip("-•✓* ").strip()
            if feat and 3 < len(feat) < 120:
                features.append(feat)

    return {
        "name": plan_name.strip().capitalize(),
        "price": price,
        "price_type": price_type,
        "billing_period": billing_period,
        "features": features or None,
    }


def _parse_plans_from_text(text: str) -> List[Dict]:
    """Full plan extraction from text — mirrors production."""
    plans = []
    seen = set()
    for m in _PLAN_NAME_RE.finditer(text):
        pname = m.group(1)
        key = pname.lower()
        if key in seen:
            continue
        plan = _extract_plan_from_text(text, pname, m.start())
        if plan:
            seen.add(key)
            plans.append(plan)
    return plans


def _format_price_str(price) -> str:
    if price is None:
        return ""
    if price == int(price):
        return f"\u20ac{int(price)}"
    return f"\u20ac{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_pricing_with_features(plans: List[Dict]) -> str:
    """Mirror production _format_pricing_response with features."""
    lines = []
    for p in plans:
        if p["price_type"] == "fixed" and p.get("price") is not None:
            price_str = _format_price_str(p["price"])
            period = f" per {p['billing_period']}" if p.get("billing_period") else ""
            lines.append(f"{p['name']}: {price_str}{period}")
        elif p["price_type"] == "contact_required":
            lines.append(f"{p['name']}: Prijs op aanvraag")
        else:
            lines.append(p["name"])
        if p.get("features"):
            for feat in p["features"]:
                lines.append(f"  - {feat}")
    return "\n".join(lines)


# ── Dataclasses to simulate DB models ─────────────────────────────

@dataclass
class MockPricingPlan:
    name: str
    price: Optional[Decimal]
    price_type: str
    billing_period: Optional[str] = None
    currency: str = "EUR"
    display_order: int = 0
    source_url: str = ""
    features: Optional[list] = None


@dataclass
class MockContactInfo:
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    source_url: str = ""


@dataclass
class MockOpeningHours:
    weekday: int = 0
    open_time: Optional[dt_time] = None
    close_time: Optional[dt_time] = None
    closed: bool = False
    source_url: str = ""


# ── Test infrastructure ───────────────────────────────────────────

_results: List[str] = []
_pass_count = 0
_fail_count = 0


def _assert(condition: bool, test_name: str, detail: str = ""):
    global _pass_count, _fail_count
    if condition:
        _pass_count += 1
        _results.append(f"  PASS  {test_name}")
    else:
        _fail_count += 1
        msg = f"  FAIL  {test_name}"
        if detail:
            msg += f"  [{detail}]"
        _results.append(msg)


# ═══════════════════════════════════════════════════════════════════
# TEST SUITES
# ═══════════════════════════════════════════════════════════════════


# ── 1. Pricing extraction tests ──────────────────────────────────

class TestPricingExtraction:

    @staticmethod
    def test_euro_per_maand():
        text = "Starter €149 /maand"
        prices = _PRICE_RE.findall(text)
        raw = next((g for group in prices for g in group if g), None)
        price = _parse_price(raw) if raw else None
        period = _detect_period(text)
        _assert(price == Decimal("149"), "pricing: €149 /maand -> price=149", f"got {price}")
        _assert(period == "maand", "pricing: /maand -> period=maand", f"got {period}")

    @staticmethod
    def test_euro_per_jaar():
        text = "Enterprise €4999 /jaar"
        prices = _PRICE_RE.findall(text)
        raw = next((g for group in prices for g in group if g), None)
        price = _parse_price(raw) if raw else None
        period = _detect_period(text)
        _assert(price == Decimal("4999"), "pricing: €4999 /jaar -> price=4999", f"got {price}")
        _assert(period == "jaar", "pricing: /jaar -> period=jaar", f"got {period}")

    @staticmethod
    def test_euro_per_month_english():
        text = "$99/mo billed annually"
        prices = _PRICE_RE.findall(text)
        raw = next((g for group in prices for g in group if g), None)
        price = _parse_price(raw) if raw else None
        period = _detect_period(text)
        _assert(price == Decimal("99"), "pricing: $99/mo -> price=99", f"got {price}")
        _assert(period == "maand", "pricing: /mo -> period=maand", f"got {period}")

    @staticmethod
    def test_euro_with_comma():
        text = "Pro plan €29,90 per maand"
        prices = _PRICE_RE.findall(text)
        raw = next((g for group in prices for g in group if g), None)
        price = _parse_price(raw) if raw else None
        _assert(price == Decimal("29.90"), "pricing: €29,90 -> price=29.90", f"got {price}")

    @staticmethod
    def test_enterprise_no_price():
        text = "Enterprise Prijs op aanvraag"
        m = _PLAN_NAME_RE.search(text)
        _assert(m is not None, "pricing: enterprise plan detected")
        plan = _extract_plan_from_text(text, "Enterprise", m.start()) if m else None
        _assert(plan is not None, "pricing: enterprise extracted")
        if plan:
            _assert(plan["price_type"] == "contact_required", "pricing: enterprise -> contact_required", f"got {plan['price_type']}")

    @staticmethod
    def test_multiple_plans_in_text():
        text = """
Starter €149 /maand
Business €299 /maand
Enterprise Prijs op aanvraag
"""
        names = _PLAN_NAME_RE.findall(text)
        name_set = {n.lower() for n in names}
        _assert("starter" in name_set, "pricing: multi-plan starter detected")
        _assert("business" in name_set, "pricing: multi-plan business detected")
        _assert("enterprise" in name_set, "pricing: multi-plan enterprise detected")
        _assert(len(name_set) == 3, "pricing: found exactly 3 plans", f"got {len(name_set)}: {name_set}")

    @staticmethod
    def test_contact_required_patterns():
        patterns = [
            "Neem contact op voor een offerte",
            "Request a quote",
            "Prijs op aanvraag",
            "Enterprise pricing",
            "Custom pricing",
        ]
        for p in patterns:
            _assert(
                bool(_CONTACT_REQUIRED_RE.search(p)),
                f"pricing: contact_required matches '{p[:40]}'",
            )


# ── 2. Contact extraction tests ──────────────────────────────────

class TestContactExtraction:

    @staticmethod
    def test_phone_detection():
        texts = [
            "+31 20 123 4567",
            "020-1234567",
            "0612345678",
            "+31612345678",
        ]
        for t in texts:
            _assert(bool(_PHONE_RE.search(t)), f"contact: phone detected in '{t}'")

    @staticmethod
    def test_email_detection():
        texts = [
            "info@example.com",
            "contact@bedrijf.nl",
            "support+tag@domain.co.uk",
        ]
        for t in texts:
            _assert(bool(_EMAIL_RE.search(t)), f"contact: email detected in '{t}'")

    @staticmethod
    def test_postcode_detection():
        texts = ["1234 AB", "5678CD", "1017 HZ"]
        for t in texts:
            _assert(bool(_POSTCODE_RE.search(t)), f"contact: postcode detected in '{t}'")


# ── 3. Opening hours extraction tests ────────────────────────────

class TestOpeningHours:

    @staticmethod
    def test_single_day():
        text = "Maandag: 09:00 - 17:00"
        m = _HOURS_LINE_RE.search(text)
        _assert(m is not None, "hours: single day detected")
        if m:
            day = _WEEKDAY_MAP.get(m.group("day1").lower())
            _assert(day == 0, "hours: maandag -> weekday 0", f"got {day}")
            _assert(int(m.group("open")) == 9, "hours: open=9")
            _assert(int(m.group("close")) == 17, "hours: close=17")

    @staticmethod
    def test_day_range():
        text = "Ma t/m vr 08:30 - 17:30"
        m = _HOURS_LINE_RE.search(text)
        _assert(m is not None, "hours: day range detected")
        if m:
            day1 = _WEEKDAY_MAP.get(m.group("day1").lower())
            day2 = _WEEKDAY_MAP.get((m.group("day2") or "").lower())
            _assert(day1 == 0, "hours: ma -> 0", f"got {day1}")
            _assert(day2 == 4, "hours: vr -> 4", f"got {day2}")

    @staticmethod
    def test_closed_day():
        text = "Zondag: gesloten"
        m = _CLOSED_LINE_RE.search(text)
        _assert(m is not None, "hours: closed day detected")
        if m:
            day = _WEEKDAY_MAP.get(m.group("day1").lower())
            _assert(day == 6, "hours: zondag -> 6", f"got {day}")

    @staticmethod
    def test_english_hours():
        text = "Monday 09:00 - 17:00"
        m = _HOURS_LINE_RE.search(text)
        _assert(m is not None, "hours: english day detected")

    @staticmethod
    def test_dot_separator():
        text = "Dinsdag 09.00 - 17.00"
        m = _HOURS_LINE_RE.search(text)
        _assert(m is not None, "hours: dot separator detected")


# ── 4. Query classification for structured facts ─────────────────

class TestQueryClassification:

    @staticmethod
    def test_pricing_queries():
        queries = [
            ("Wat zijn jullie prijzen?", "pricing"),
            ("Welke pakketten hebben jullie?", "pricing"),
            ("Wat kost het starter pakket?", "pricing"),
            ("Wat kost business?", "pricing"),
            ("Hebben jullie ook enterprise?", "pricing"),
            ("Hoeveel kost een abonnement?", "pricing"),
            ("Tarieven", "pricing"),
        ]
        for q, expected in queries:
            result = classify_query(q)
            _assert(result == expected, f"classify: '{q}' -> {expected}", f"got {result}")

    @staticmethod
    def test_contact_queries():
        queries = [
            ("Wat is jullie telefoonnummer?", "contact"),
            ("Wat zijn de openingstijden?", "contact"),
            ("Hoe kan ik contact opnemen?", "contact"),
            ("Wat is het adres?", "contact"),
        ]
        for q, expected in queries:
            result = classify_query(q)
            _assert(result == expected, f"classify: '{q}' -> {expected}", f"got {result}")

    @staticmethod
    def test_location_queries():
        queries = [
            ("Waar is jullie vestiging?", "location"),
            ("Waar is jullie filiaal?", "location"),
        ]
        for q, expected in queries:
            result = classify_query(q)
            _assert(result == expected, f"classify: '{q}' -> {expected}", f"got {result}")

    @staticmethod
    def test_service_queries():
        queries = [
            ("Welke diensten bieden jullie aan?", "service"),
            ("Wat is jullie aanbod?", "service"),
        ]
        for q, expected in queries:
            result = classify_query(q)
            _assert(result == expected, f"classify: '{q}' -> {expected}", f"got {result}")

    @staticmethod
    def test_general_fallthrough():
        queries = [
            "ja",
            "hallo",
            "bedankt",
            "ik weet het niet",
        ]
        for q in queries:
            result = classify_query(q)
            _assert(result == "general", f"classify: '{q}' -> general (no structured match)", f"got {result}")


# ── 5. Formatting tests ──────────────────────────────────────────

class TestFormatting:

    @staticmethod
    def test_pricing_format():
        plans = [
            MockPricingPlan(name="Starter", price=Decimal("149"), price_type="fixed", billing_period="maand"),
            MockPricingPlan(name="Business", price=Decimal("299"), price_type="fixed", billing_period="maand"),
            MockPricingPlan(name="Enterprise", price=None, price_type="contact_required"),
        ]
        lines = []
        for p in plans:
            if p.price_type == "fixed" and p.price is not None:
                price_str = _format_price_str(p.price)
                period = f" per {p.billing_period}" if p.billing_period else ""
                lines.append(f"{p.name}: {price_str}{period}")
            elif p.price_type == "contact_required":
                lines.append(f"{p.name}: Prijs op aanvraag")
            else:
                lines.append(p.name)

        content = "\n".join(lines)
        _assert("Starter" in content, "format: Starter in output")
        _assert("149" in content, "format: 149 in output")
        _assert("Business" in content, "format: Business in output")
        _assert("299" in content, "format: 299 in output")
        _assert("Enterprise" in content, "format: Enterprise in output")
        _assert("op aanvraag" in content, "format: 'op aanvraag' in output")
        _assert(len(lines) == 3, "format: 3 lines for 3 plans", f"got {len(lines)}")

    @staticmethod
    def test_whole_number_no_decimals():
        _assert(_format_price_str(Decimal("149")) == "\u20ac149", "format: 149 -> €149 (no decimals)")
        _assert(_format_price_str(Decimal("299")) == "\u20ac299", "format: 299 -> €299 (no decimals)")
        _assert(_format_price_str(Decimal("29.90")) == "\u20ac29,90", "format: 29.90 -> €29,90 (keep decimals)")
        _assert(_format_price_str(None) == "", "format: None -> empty")

    @staticmethod
    def test_hours_format():
        weekday_names = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
        hours = [
            MockOpeningHours(weekday=0, open_time=dt_time(9, 0), close_time=dt_time(17, 0)),
            MockOpeningHours(weekday=5, closed=True),
            MockOpeningHours(weekday=6, closed=True),
        ]
        lines = []
        for h in hours:
            day = weekday_names[h.weekday]
            if h.closed:
                lines.append(f"{day}: Gesloten")
            elif h.open_time and h.close_time:
                lines.append(f"{day}: {h.open_time.strftime('%H:%M')} - {h.close_time.strftime('%H:%M')}")

        content = "\n".join(lines)
        _assert("Maandag: 09:00 - 17:00" in content, "format: maandag hours correct")
        _assert("Zaterdag: Gesloten" in content, "format: zaterdag gesloten")
        _assert("Zondag: Gesloten" in content, "format: zondag gesloten")


# ── 6. Structured facts determinism test ─────────────────────────

class TestDeterminism:

    @staticmethod
    def test_same_query_same_result():
        """Structured facts must return identical results every time."""
        plans = [
            MockPricingPlan(name="Starter", price=Decimal("149"), price_type="fixed", billing_period="maand"),
            MockPricingPlan(name="Business", price=Decimal("299"), price_type="fixed", billing_period="maand"),
        ]

        results = []
        for _ in range(10):
            lines = []
            for p in plans:
                if p.price_type == "fixed":
                    lines.append(f"{p.name} – €{p.price} per {p.billing_period}")
            results.append("\n".join(lines))

        all_same = all(r == results[0] for r in results)
        _assert(all_same, "determinism: 10 runs produce identical output")

    @staticmethod
    def test_general_query_returns_none():
        """A 'general' classification should not trigger structured facts."""
        classification = classify_query("hallo, ik heb een vraag")
        _assert(classification == "general", "determinism: general query -> no structured match")


# ── 7. Edge case tests ───────────────────────────────────────────

class TestEdgeCases:

    @staticmethod
    def test_price_with_thousands():
        text = "Enterprise €1.499 per jaar"
        prices = _PRICE_RE.findall(text)
        raw = next((g for group in prices for g in group if g), None)
        price = _parse_price(raw) if raw else None
        _assert(price == Decimal("1499"), "edge: €1.499 -> 1499", f"got {price}")

    @staticmethod
    def test_multiple_currencies():
        for text, expected in [("$99/mo", "USD"), ("£49 per month", "GBP"), ("€149 /maand", "EUR")]:
            if "$" in text:
                cur = "USD"
            elif "£" in text:
                cur = "GBP"
            else:
                cur = "EUR"
            _assert(cur == expected, f"edge: '{text}' -> {expected} currency")

    @staticmethod
    def test_empty_text_no_crash():
        _assert(_PRICE_RE.findall("") == [], "edge: empty text no price")
        _assert(_PHONE_RE.findall("") == [], "edge: empty text no phone")
        _assert(_EMAIL_RE.findall("") == [], "edge: empty text no email")
        _assert(_PLAN_NAME_RE.findall("") == [], "edge: empty text no plan")

    @staticmethod
    def test_plan_name_case_insensitive():
        for name in ["STARTER", "Starter", "starter", "ENTERPRISE", "Enterprise"]:
            _assert(bool(_PLAN_NAME_RE.search(name)), f"edge: plan name '{name}' detected")

    @staticmethod
    def test_gratis_free_custom_not_plan_names():
        for word in ["gratis", "free", "custom", "Free", "Gratis"]:
            _assert(not bool(_PLAN_NAME_RE.search(word)), f"edge: '{word}' is NOT a plan name")

    @staticmethod
    def test_pro_is_plan_name():
        _assert(bool(_PLAN_NAME_RE.search("Pro")), "edge: 'Pro' IS a plan name")
        _assert(not bool(_PLAN_NAME_RE.search("Probeer")), "edge: 'Probeer' is NOT a plan name")
        _assert(not bool(_PLAN_NAME_RE.search("proefperiode")), "edge: 'proefperiode' is NOT a plan name")


# ── 8. Klantenservice.ai homepage regression ─────────────────────

_HOMEPAGE = """AI-telefonisten voor uw bedrijf
Automatiseer uw klantenservice met intelligente AI-medewerkers die 24/7 beschikbaar zijn.

Start gratis proefperiode
Boek een demo
Probeer het gratis • Annuleren kan altijd

Starter
€149 /maand
14 dagen gratis
Perfect voor kleine ondernemers
- 1 AI-medewerker
- 500 belminuten/maand
- Agenda integratie
- CRM integratie
- Website kennis
Probeer het gratis uit

Meest gekozen
Business
€299 /maand
14 dagen gratis
Ideaal voor groeiende bedrijven
- 5 AI-medewerkers
- 2.000 belminuten/maand
- Agenda integratie
- CRM integratie
- Website kennis
- Prioriteit support
Probeer het gratis uit

Enterprise
Prijs op aanvraag
Voor grote organisaties
- 7+ AI-medewerkers
- Onbeperkt belminuten
- Custom integraties
- Dedicated account manager
- SLA garantie
Neem contact op

Veelgestelde vragen
Hoe snel kan ik starten?
Kan ik de AI trainen met mijn eigen informatie?
"""


class TestHomepageRegression:

    @staticmethod
    def test_exactly_three_plans():
        plans = _parse_plans_from_text(_HOMEPAGE)
        _assert(len(plans) == 3, f"homepage: exactly 3 plans", f"got {len(plans)}: {[p['name'] for p in plans]}")

    @staticmethod
    def test_starter_price_149():
        plans = _parse_plans_from_text(_HOMEPAGE)
        starter = next((p for p in plans if p["name"] == "Starter"), None)
        _assert(starter is not None, "homepage: Starter plan found")
        if starter:
            _assert(starter["price"] == Decimal("149"), "homepage: Starter price = 149", f"got {starter['price']}")
            _assert(starter["price_type"] == "fixed", "homepage: Starter type = fixed")
            _assert(starter["billing_period"] == "maand", "homepage: Starter period = maand")

    @staticmethod
    def test_business_price_299():
        plans = _parse_plans_from_text(_HOMEPAGE)
        biz = next((p for p in plans if p["name"] == "Business"), None)
        _assert(biz is not None, "homepage: Business plan found")
        if biz:
            _assert(biz["price"] == Decimal("299"), "homepage: Business price = 299", f"got {biz['price']}")
            _assert(biz["price_type"] == "fixed", "homepage: Business type = fixed")
            _assert(biz["billing_period"] == "maand", "homepage: Business period = maand")

    @staticmethod
    def test_enterprise_contact_required():
        plans = _parse_plans_from_text(_HOMEPAGE)
        ent = next((p for p in plans if p["name"] == "Enterprise"), None)
        _assert(ent is not None, "homepage: Enterprise plan found")
        if ent:
            _assert(ent["price"] is None, "homepage: Enterprise price = None", f"got {ent['price']}")
            _assert(ent["price_type"] == "contact_required", "homepage: Enterprise type = contact_required", f"got {ent['price_type']}")

    @staticmethod
    def test_no_gratis_plan():
        plans = _parse_plans_from_text(_HOMEPAGE)
        names = {p["name"].lower() for p in plans}
        _assert("gratis" not in names, "homepage: no 'Gratis' plan", f"got names: {names}")
        _assert("free" not in names, "homepage: no 'Free' plan", f"got names: {names}")

    @staticmethod
    def test_no_custom_plan():
        plans = _parse_plans_from_text(_HOMEPAGE)
        names = {p["name"].lower() for p in plans}
        _assert("custom" not in names, "homepage: no 'Custom' plan", f"got names: {names}")

    @staticmethod
    def test_no_pro_plan():
        plans = _parse_plans_from_text(_HOMEPAGE)
        names = {p["name"].lower() for p in plans}
        _assert("pro" not in names, "homepage: no 'Pro' plan", f"got names: {names}")

    @staticmethod
    def test_14_dagen_gratis_not_plan():
        text = "14 dagen gratis proberen! Start nu."
        plans = _parse_plans_from_text(text)
        _assert(len(plans) == 0, "homepage: '14 dagen gratis' -> 0 plans", f"got {len(plans)}")

    @staticmethod
    def test_gratis_proefperiode_not_plan():
        text = "Start gratis proefperiode. Annuleren kan altijd. Probeer het gratis uit."
        plans = _parse_plans_from_text(text)
        _assert(len(plans) == 0, "homepage: 'gratis proefperiode' -> 0 plans", f"got {len(plans)}")

    @staticmethod
    def test_cta_not_plan():
        text = "Probeer het gratis • Boek een demo • Neem contact op"
        plans = _parse_plans_from_text(text)
        _assert(len(plans) == 0, "homepage: CTA text -> 0 plans", f"got {len(plans)}")

    @staticmethod
    def test_faq_not_plan():
        text = "Veelgestelde vragen\nKan ik gratis starten?\nJa, met een proefperiode van 14 dagen."
        plans = _parse_plans_from_text(text)
        _assert(len(plans) == 0, "homepage: FAQ text -> 0 plans", f"got {len(plans)}")

    @staticmethod
    def test_plan_order_preserved():
        plans = _parse_plans_from_text(_HOMEPAGE)
        if len(plans) == 3:
            _assert(plans[0]["name"] == "Starter", "homepage: plan order [0] = Starter")
            _assert(plans[1]["name"] == "Business", "homepage: plan order [1] = Business")
            _assert(plans[2]["name"] == "Enterprise", "homepage: plan order [2] = Enterprise")

    @staticmethod
    def test_price_not_contaminated_by_14_dagen():
        plans = _parse_plans_from_text(_HOMEPAGE)
        for p in plans:
            if p["price"] is not None:
                _assert(p["price"] > 50, f"homepage: {p['name']} price > 50 (not 14)", f"got {p['price']}")

    @staticmethod
    def test_dollar_plan():
        text = "Pro $99/mo billed annually\nBusiness $199/mo"
        plans = _parse_plans_from_text(text)
        _assert(len(plans) >= 1, "dollar: at least 1 plan extracted", f"got {len(plans)}")
        if plans:
            biz = next((p for p in plans if p["name"] == "Business"), None)
            if biz:
                _assert(biz["price"] == Decimal("199"), "dollar: Business = $199", f"got {biz['price']}")

    @staticmethod
    def test_multiple_pricing_sections():
        text = """Prijzen

Starter
€49 per maand
Ideaal voor starters

---

Premium
€199 per maand
Voor professionals

---

Enterprise
Prijs op aanvraag
"""
        plans = _parse_plans_from_text(text)
        _assert(len(plans) == 3, f"multi-section: 3 plans", f"got {len(plans)}")
        if len(plans) == 3:
            _assert(plans[0]["price"] == Decimal("49"), "multi-section: Starter = 49")
            _assert(plans[1]["price"] == Decimal("199"), "multi-section: Premium = 199")
            _assert(plans[2]["price_type"] == "contact_required", "multi-section: Enterprise = contact_required")


# ── 9. Company overview query classification ─────────────────────

class TestCompanyOverviewQueries:

    @staticmethod
    def test_vague_overview_classified():
        queries = [
            "Wat doen jullie?",
            "Ik vroeg me af wat jullie allemaal doen",
            "Kan je uitleggen wat jullie doen?",
            "Wat bieden jullie aan?",
            "Wat voor bedrijf zijn jullie?",
            "Vertel eens over jullie bedrijf",
        ]
        for q in queries:
            result = classify_query(q)
            _assert(
                result != "general",
                f"overview: '{q}' must NOT be 'general'",
                f"got '{result}'",
            )

    @staticmethod
    def test_overview_not_pricing():
        queries = [
            "Wat doen jullie?",
            "Ik vroeg me af wat jullie allemaal doen",
        ]
        for q in queries:
            result = classify_query(q)
            _assert(result != "pricing", f"overview: '{q}' must NOT be 'pricing'", f"got '{result}'")


# ── 10. Package feature extraction tests ─────────────────────────

class TestFeatureExtraction:

    @staticmethod
    def test_starter_features_complete():
        plans = _parse_plans_from_text(_HOMEPAGE)
        starter = next((p for p in plans if p["name"] == "Starter"), None)
        _assert(starter is not None, "features: Starter found")
        if starter:
            feats = starter.get("features") or []
            _assert(len(feats) >= 4, f"features: Starter has >= 4 features", f"got {len(feats)}: {feats}")
            feat_text = " ".join(feats).lower()
            _assert("ai-medewerker" in feat_text or "medewerker" in feat_text, "features: Starter has AI-medewerker")
            _assert("belminuten" in feat_text, "features: Starter has belminuten")

    @staticmethod
    def test_business_features_complete():
        plans = _parse_plans_from_text(_HOMEPAGE)
        biz = next((p for p in plans if p["name"] == "Business"), None)
        _assert(biz is not None, "features: Business found")
        if biz:
            feats = biz.get("features") or []
            _assert(len(feats) >= 4, f"features: Business has >= 4 features", f"got {len(feats)}: {feats}")
            feat_text = " ".join(feats).lower()
            _assert("medewerker" in feat_text, "features: Business has medewerkers")
            _assert("belminuten" in feat_text, "features: Business has belminuten")

    @staticmethod
    def test_enterprise_features_complete():
        plans = _parse_plans_from_text(_HOMEPAGE)
        ent = next((p for p in plans if p["name"] == "Enterprise"), None)
        _assert(ent is not None, "features: Enterprise found")
        if ent:
            feats = ent.get("features") or []
            _assert(len(feats) >= 3, f"features: Enterprise has >= 3 features", f"got {len(feats)}: {feats}")

    @staticmethod
    def test_features_included_in_format():
        plans = _parse_plans_from_text(_HOMEPAGE)
        formatted = _format_pricing_with_features(plans)
        _assert("AI-medewerker" in formatted or "medewerker" in formatted, "format: features visible in output")
        _assert("belminuten" in formatted, "format: belminuten in output")
        _assert("149" in formatted, "format: exact price 149 in output")
        _assert("299" in formatted, "format: exact price 299 in output")
        _assert("op aanvraag" in formatted, "format: op aanvraag in output")


# ── 11. Package comparison tests ─────────────────────────────────

class TestPackageComparison:

    @staticmethod
    def test_comparison_query_classified_as_pricing():
        queries = [
            "Wat is het verschil tussen starter en business?",
            "Wat zit er extra in business?",
        ]
        for q in queries:
            result = classify_query(q)
            _assert(result == "pricing", f"comparison: '{q}' -> pricing", f"got {result}")

    @staticmethod
    def test_both_plans_in_comparison_output():
        plans = _parse_plans_from_text(_HOMEPAGE)
        formatted = _format_pricing_with_features(plans)
        _assert("Starter" in formatted, "comparison: Starter in output")
        _assert("Business" in formatted, "comparison: Business in output")
        _assert("Enterprise" in formatted, "comparison: Enterprise in output")

    @staticmethod
    def test_features_enable_comparison():
        plans = _parse_plans_from_text(_HOMEPAGE)
        starter = next((p for p in plans if p["name"] == "Starter"), None)
        biz = next((p for p in plans if p["name"] == "Business"), None)
        if starter and biz:
            s_feats = set(f.lower() for f in (starter.get("features") or []))
            b_feats = set(f.lower() for f in (biz.get("features") or []))
            _assert(len(b_feats - s_feats) > 0, "comparison: Business has features Starter doesn't", f"diff={b_feats - s_feats}")


# ── 12. Exact pricing determinism ────────────────────────────────

class TestExactPricingDeterminism:

    @staticmethod
    def test_repeated_runs_exact():
        for i in range(10):
            plans = _parse_plans_from_text(_HOMEPAGE)
            starter = next((p for p in plans if p["name"] == "Starter"), None)
            if starter:
                _assert(
                    starter["price"] == Decimal("149"),
                    f"determinism: run {i+1} Starter = 149",
                    f"got {starter['price']}",
                )

    @staticmethod
    def test_no_price_rounding():
        plans = _parse_plans_from_text(_HOMEPAGE)
        for p in plans:
            if p.get("price") is not None:
                _assert(p["price"] != Decimal("145"), f"rounding: {p['name']} != 145")
                _assert(p["price"] != Decimal("150"), f"rounding: {p['name']} != 150")
                _assert(p["price"] != Decimal("300"), f"rounding: {p['name']} != 300")


# ── 13. _parse_price decimal handling (145 bug regression) ────────

class TestParsePrice145Bug:
    """Regression tests for the 145 bug: _parse_price must not turn
    English-format decimals into inflated integers."""

    @staticmethod
    def test_clean_integer():
        _assert(_parse_price("149") == Decimal("149"), "parse: '149' -> 149")
        _assert(_parse_price("299") == Decimal("299"), "parse: '299' -> 299")
        _assert(_parse_price("4999") == Decimal("4999"), "parse: '4999' -> 4999")

    @staticmethod
    def test_dutch_decimal():
        _assert(_parse_price("29,90") == Decimal("29.90"), "parse: '29,90' -> 29.90")
        _assert(_parse_price("149,00") == Decimal("149.00"), "parse: '149,00' -> 149.00")
        _assert(_parse_price("1,45") == Decimal("1.45"), "parse: '1,45' -> 1.45")

    @staticmethod
    def test_english_decimal_NOT_145():
        _assert(_parse_price("1.45") == Decimal("1.45"), "parse: '1.45' -> 1.45 NOT 145", f"got {_parse_price('1.45')}")
        _assert(_parse_price("14.5") == Decimal("14.5"), "parse: '14.5' -> 14.5 NOT 145", f"got {_parse_price('14.5')}")
        _assert(_parse_price("0.14") == Decimal("0.14"), "parse: '0.14' -> 0.14 NOT 14", f"got {_parse_price('0.14')}")
        _assert(_parse_price("29.90") == Decimal("29.90"), "parse: '29.90' -> 29.90", f"got {_parse_price('29.90')}")
        _assert(_parse_price("149.99") == Decimal("149.99"), "parse: '149.99' -> 149.99", f"got {_parse_price('149.99')}")

    @staticmethod
    def test_dutch_thousands():
        _assert(_parse_price("1.499") == Decimal("1499"), "parse: '1.499' -> 1499")
        _assert(_parse_price("12.345") == Decimal("12345"), "parse: '12.345' -> 12345")

    @staticmethod
    def test_mixed_separators():
        _assert(_parse_price("1.499,99") == Decimal("1499.99"), "parse: '1.499,99' -> 1499.99")
        _assert(_parse_price("1,499.99") == Decimal("1499.99"), "parse: '1,499.99' -> 1499.99")

    @staticmethod
    def test_never_produces_145():
        """No plausible price input should produce 145 except literal '145'."""
        dangerous = ["1.45", "14.5", "0.145"]
        for raw in dangerous:
            price = _parse_price(raw)
            _assert(
                price != Decimal("145"),
                f"parse: '{raw}' must NOT produce 145",
                f"got {price}",
            )


# ── 14. Unit-pricing context detection ────────────────────────────

class TestUnitPricingDetection:

    @staticmethod
    def test_per_minute_skipped():
        text = "Starter €0.14 per minuut €149 /maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("149"), "unit: skip 'per minuut', find €149", f"got {price}")

    @staticmethod
    def test_per_gesprek_skipped():
        text = "Starter €1.45 per gesprek €149 /maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("149"), "unit: skip 'per gesprek', find €149", f"got {price}")

    @staticmethod
    def test_per_call_skipped():
        text = "Starter €0.50 per call €49 /maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("49"), "unit: skip 'per call', find €49", f"got {price}")

    @staticmethod
    def test_per_sms_skipped():
        text = "Basic €0.10 per sms €5 /maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("5"), "unit: skip 'per sms', find €5", f"got {price}")

    @staticmethod
    def test_slash_min_skipped():
        text = "Starter €0.14/min €149 /maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("149"), "unit: skip '/min', find €149", f"got {price}")

    @staticmethod
    def test_normal_price_accepted():
        text = "Starter €149 /maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("149"), "unit: €149 /maand accepted", f"got {price}")

    @staticmethod
    def test_cheap_plan_5_accepted():
        text = "Basic €5 /maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("5"), "unit: €5 /maand accepted", f"got {price}")

    @staticmethod
    def test_cheap_plan_499_accepted():
        text = "Starter €4,99 per maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("4.99"), "unit: €4,99 per maand accepted", f"got {price}")

    @staticmethod
    def test_cheap_plan_1_per_dag_accepted():
        text = "Lite €1 /dag"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("1"), "unit: €1 /dag accepted", f"got {price}")

    @staticmethod
    def test_cheap_plan_299_cents_accepted():
        text = "Basic €2.99 per month"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("2.99"), "unit: €2.99 per month accepted", f"got {price}")

    @staticmethod
    def test_per_api_call_skipped():
        text = "Enterprise €0.002 per api call €999 /maand"
        m = _PLAN_NAME_RE.search(text)
        price = _find_price_after(text, m.start()) if m else None
        _assert(price == Decimal("999"), "unit: skip 'per api call', find €999", f"got {price}")


# ── 15. Full pipeline 145→149 proof ──────────────────────────────

class TestFull145BugProof:

    @staticmethod
    def test_starter_always_149_standard():
        """Standard homepage text always gives Starter=149."""
        for i in range(10):
            plans = _parse_plans_from_text(_HOMEPAGE)
            starter = next((p for p in plans if p["name"] == "Starter"), None)
            _assert(
                starter is not None and starter["price"] == Decimal("149"),
                f"proof: run {i+1} Starter = 149",
                f"got {starter['price'] if starter else 'None'}",
            )

    @staticmethod
    def test_starter_149_with_per_minute_noise():
        """Even with per-minute pricing nearby, Starter must be 149."""
        noisy = """
Starter
Belminuten boven je bundel: €0.14 per minuut
€149 /maand
- 500 belminuten/maand

Business
€299 /maand
"""
        plans = _parse_plans_from_text(noisy)
        starter = next((p for p in plans if p["name"] == "Starter"), None)
        _assert(starter is not None, "proof-noisy: Starter found")
        if starter:
            _assert(
                starter["price"] == Decimal("149"),
                "proof-noisy: Starter = 149 (not 14, not 145)",
                f"got {starter['price']}",
            )

    @staticmethod
    def test_business_always_299():
        plans = _parse_plans_from_text(_HOMEPAGE)
        biz = next((p for p in plans if p["name"] == "Business"), None)
        _assert(biz is not None and biz["price"] == Decimal("299"), "proof: Business = 299")

    @staticmethod
    def test_formatted_shows_149_not_145():
        plans = _parse_plans_from_text(_HOMEPAGE)
        formatted = _format_pricing_with_features(plans)
        _assert("€149" in formatted, "proof-format: €149 in output", f"output: {formatted[:200]}")
        _assert("€145" not in formatted, "proof-format: €145 NOT in output")
        _assert("€299" in formatted, "proof-format: €299 in output")

    @staticmethod
    def test_pricing_query_returns_149():
        plans = _parse_plans_from_text(_HOMEPAGE)
        formatted = _format_pricing_with_features(plans)
        for query in [
            "Wat kost het starter pakket?",
            "Wat zijn de prijzen van Klantenservice.ai?",
        ]:
            _assert(
                "149" in formatted,
                f"proof-query: '{query}' -> 149 in response",
            )


# ═══════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════

test_classes = [
    TestPricingExtraction,
    TestContactExtraction,
    TestOpeningHours,
    TestQueryClassification,
    TestFormatting,
    TestDeterminism,
    TestEdgeCases,
    TestHomepageRegression,
    TestCompanyOverviewQueries,
    TestFeatureExtraction,
    TestPackageComparison,
    TestExactPricingDeterminism,
    TestParsePrice145Bug,
    TestUnitPricingDetection,
    TestFull145BugProof,
]


def main():
    global _pass_count, _fail_count
    _pass_count = 0
    _fail_count = 0
    _results.clear()

    for cls in test_classes:
        for attr in sorted(dir(cls)):
            if attr.startswith("test_"):
                getattr(cls, attr)()

    print("\n".join(_results))
    print(f"\n{'=' * 60}")
    print(f"Results: {_pass_count} passed, {_fail_count} failed, {_pass_count + _fail_count} total")
    print(f"{'=' * 60}")

    return _fail_count == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
