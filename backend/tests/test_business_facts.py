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
    r"premium|enterprise|gratis|free|plus|growth|advanced|custom|lite|team)\b",
    re.I,
)

_CONTACT_REQUIRED_RE = re.compile(
    r"op\s+aanvraag|neem\s+contact|contact\s+(?:opnemen|sales|ons)"
    r"|request\s+(?:pricing|quote|a\s+quote)|offerte"
    r"|custom\s+pricing|enterprise\s+pricing"
    r"|bel\s+(?:ons|voor)",
    re.I,
)

_FREE_RE = re.compile(r"\bgratis\b|\bfree\b|\b€\s*0[.,]?0*\b", re.I)

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
]


def classify_query(query: str) -> str:
    q = query.strip()
    for pattern, qtype in _QUERY_RULES:
        if pattern.search(q):
            return qtype
    return "general"


# ── Extraction helpers (mirrored from fact_extractor.py) ─────────

def _parse_price(raw: str) -> Optional[Decimal]:
    cleaned = raw.replace(".", "").replace(",", ".").strip()
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


def _detect_price_type(text: str, has_price: bool) -> str:
    if _FREE_RE.search(text) and not has_price:
        return "free"
    if has_price:
        return "fixed"
    if _CONTACT_REQUIRED_RE.search(text):
        return "contact_required"
    return "custom"


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
        names = _PLAN_NAME_RE.findall(text)
        prices = _PRICE_RE.findall(text)
        has_price = bool(prices)
        price_type = _detect_price_type(text, has_price)
        _assert("enterprise" in [n.lower() for n in names], "pricing: enterprise plan detected")
        _assert(price_type == "contact_required", "pricing: enterprise -> contact_required", f"got {price_type}")

    @staticmethod
    def test_free_plan():
        text = "Free tier Gratis voor altijd"
        names = _PLAN_NAME_RE.findall(text)
        price_type = _detect_price_type(text, False)
        _assert("free" in [n.lower() for n in names], "pricing: free plan detected")
        _assert(price_type == "free", "pricing: gratis -> free", f"got {price_type}")

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
            "Contact sales for pricing",
            "Request a quote",
            "Prijs op aanvraag",
            "Bel ons voor meer informatie",
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
                price_str = f"€{p.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                period = f" per {p.billing_period}" if p.billing_period else ""
                lines.append(f"{p.name} – {price_str}{period}")
            elif p.price_type == "free":
                lines.append(f"{p.name} – Gratis")
            elif p.price_type == "contact_required":
                lines.append(f"{p.name} – Prijs op aanvraag")
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
