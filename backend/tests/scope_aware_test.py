"""
SCOPE-AWARE CROSS-INDUSTRY TEST
================================

Goal: Verify that the same user utterance is classified differently
depending on the company / business context.

A phrase must not be treated as globally on-topic or globally off-topic.
It must be evaluated relative to the active company.

Industries tested:
  1. klantenservice.ai  (AI voice SaaS)
  2. Hair salon / barber
  3. Pizza restaurant
  4. Dentist
  5. Car garage / mechanic
  6. Restaurant / reservations

Run:  cd backend && venv/bin/python tests/scope_aware_test.py
"""

import importlib.util
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

_root = os.path.join(os.path.dirname(__file__), "..")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


intent_mod = _load(
    "intent_classifier",
    os.path.join(_root, "app/services/voice/intent_classifier.py"),
)
classify_intent = intent_mod.classify_intent
classify_intent_with_context = intent_mod.classify_intent_with_context
ConversationContext = intent_mod.ConversationContext
CallerIntent = intent_mod.CallerIntent
is_off_topic = intent_mod.is_off_topic
CompanyScope = intent_mod.CompanyScope
check_company_scope = intent_mod.check_company_scope

# Pre-load domain_inference so the lazy import inside check_company_scope works
_load("app.services.domain_inference",
      os.path.join(_root, "app/services/domain_inference.py"))

CI = CallerIntent


# ═══════════════════════════════════════════════════════════════════
#  COMPANY PROFILES
# ═══════════════════════════════════════════════════════════════════

COMPANIES = {
    "klantenservice_ai": {
        "name": "klantenservice.ai",
        "business_type": "ai_saas",
    },
    "hair_salon": {
        "name": "Kapsalon De Stijl",
        "business_type": "hair_salon",
    },
    "pizza_restaurant": {
        "name": "Pizza Napoli",
        "business_type": "pizza_restaurant",
    },
    "dentist": {
        "name": "Tandartspraktijk Molenwijk",
        "business_type": "dentist",
    },
    "car_garage": {
        "name": "Autogarage Centrum",
        "business_type": "car_garage",
    },
    "restaurant": {
        "name": "Restaurant De Gouden Lepel",
        "business_type": "restaurant",
    },
}

# Pre-build CompanyScope objects for each company
COMPANY_SCOPES = {
    key: CompanyScope(business_type=info["business_type"])
    for key, info in COMPANIES.items()
}


# ═══════════════════════════════════════════════════════════════════
#  SCENARIO DATA
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ScopeScenario:
    utterance: str
    company: str
    expected_scope: str        # "on_topic" or "off_topic"
    expected_intent: CallerIntent
    category: str              # scenario category for reporting


def _s(utt, company, scope, intent, cat):
    return ScopeScenario(utt, company, scope, intent, cat)


SCENARIOS: list[ScopeScenario] = []


# ── 1. COMPLAINT: same complaint, different companies ────────────

# "Mijn pizza was koud"
SCENARIOS += [
    _s("Mijn pizza was koud", "pizza_restaurant", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Mijn pizza was koud", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn pizza was koud", "hair_salon", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn pizza was koud", "dentist", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn pizza was koud", "car_garage", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn pizza was koud", "restaurant", "on_topic", CI.COMPLAINT, "complaint_cross"),
]

# "Mijn haar zit helemaal niet goed"
SCENARIOS += [
    _s("Mijn haar zit helemaal niet goed", "hair_salon", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Mijn haar zit helemaal niet goed", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn haar zit helemaal niet goed", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn haar zit helemaal niet goed", "dentist", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn haar zit helemaal niet goed", "car_garage", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn haar zit helemaal niet goed", "restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]

# "Mijn auto start niet"
SCENARIOS += [
    _s("Mijn auto start niet", "car_garage", "on_topic", CI.QUESTION, "complaint_cross"),
    _s("Mijn auto start niet", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn auto start niet", "hair_salon", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn auto start niet", "dentist", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn auto start niet", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn auto start niet", "restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]

# "De vulling is eruit gevallen"
SCENARIOS += [
    _s("De vulling is eruit gevallen", "dentist", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("De vulling is eruit gevallen", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("De vulling is eruit gevallen", "hair_salon", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("De vulling is eruit gevallen", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("De vulling is eruit gevallen", "car_garage", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("De vulling is eruit gevallen", "restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]

# "Het eten was koud"
SCENARIOS += [
    _s("Het eten was koud", "restaurant", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Het eten was koud", "pizza_restaurant", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Het eten was koud", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Het eten was koud", "hair_salon", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Het eten was koud", "dentist", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Het eten was koud", "car_garage", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]

# "Er zat een haar in mijn eten"
SCENARIOS += [
    _s("Er zat een haar in mijn eten", "restaurant", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Er zat een haar in mijn eten", "pizza_restaurant", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Er zat een haar in mijn eten", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Er zat een haar in mijn eten", "hair_salon", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Er zat een haar in mijn eten", "dentist", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Er zat een haar in mijn eten", "car_garage", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]

# "Mijn band is lek"
SCENARIOS += [
    _s("Mijn band is lek", "car_garage", "on_topic", CI.QUESTION, "complaint_cross"),
    _s("Mijn band is lek", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn band is lek", "hair_salon", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn band is lek", "dentist", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn band is lek", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Mijn band is lek", "restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]

# "De airco doet het niet meer"
SCENARIOS += [
    _s("De airco doet het niet meer", "car_garage", "on_topic", CI.QUESTION, "complaint_cross"),
    _s("De airco doet het niet meer", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("De airco doet het niet meer", "hair_salon", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("De airco doet het niet meer", "dentist", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("De airco doet het niet meer", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("De airco doet het niet meer", "restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]

# "Ik heb pijn aan mijn kies"
SCENARIOS += [
    _s("Ik heb pijn aan mijn kies", "dentist", "on_topic", CI.QUESTION, "complaint_cross"),
    _s("Ik heb pijn aan mijn kies", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Ik heb pijn aan mijn kies", "hair_salon", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Ik heb pijn aan mijn kies", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Ik heb pijn aan mijn kies", "car_garage", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Ik heb pijn aan mijn kies", "restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]

# "Het dashboard geeft een foutmelding"
SCENARIOS += [
    _s("Het dashboard geeft een foutmelding", "klantenservice_ai", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Het dashboard geeft een foutmelding", "car_garage", "on_topic", CI.COMPLAINT, "complaint_cross"),
    _s("Het dashboard geeft een foutmelding", "hair_salon", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Het dashboard geeft een foutmelding", "dentist", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Het dashboard geeft een foutmelding", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
    _s("Het dashboard geeft een foutmelding", "restaurant", "off_topic", CI.OFF_TOPIC, "complaint_cross"),
]


# ── 2. BOOKING: same booking phrase, different companies ─────────

# "Ik wil een afspraak maken"
SCENARIOS += [
    _s("Ik wil een afspraak maken", "dentist", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een afspraak maken", "hair_salon", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een afspraak maken", "car_garage", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een afspraak maken", "klantenservice_ai", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een afspraak maken", "restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een afspraak maken", "pizza_restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
]

# "Ik wil een tafeltje reserveren"
SCENARIOS += [
    _s("Ik wil een tafeltje reserveren", "restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een tafeltje reserveren", "pizza_restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een tafeltje reserveren", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een tafeltje reserveren", "hair_salon", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een tafeltje reserveren", "dentist", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een tafeltje reserveren", "car_garage", "off_topic", CI.OFF_TOPIC, "booking_cross"),
]

# "Kan ik morgen langskomen?"
SCENARIOS += [
    _s("Kan ik morgen langskomen?", "hair_salon", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Kan ik morgen langskomen?", "dentist", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Kan ik morgen langskomen?", "car_garage", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Kan ik morgen langskomen?", "restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Kan ik morgen langskomen?", "pizza_restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Kan ik morgen langskomen?", "klantenservice_ai", "on_topic", CI.APPOINTMENT, "booking_cross"),
]

# "Ik wil een pizza bestellen"
SCENARIOS += [
    _s("Ik wil een pizza bestellen", "pizza_restaurant", "on_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een pizza bestellen", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een pizza bestellen", "hair_salon", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een pizza bestellen", "dentist", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een pizza bestellen", "car_garage", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een pizza bestellen", "restaurant", "on_topic", CI.OFF_TOPIC, "booking_cross"),
]

# "Ik wil mijn haar laten knippen"
SCENARIOS += [
    _s("Ik wil mijn haar laten knippen", "hair_salon", "on_topic", CI.QUESTION, "booking_cross"),
    _s("Ik wil mijn haar laten knippen", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil mijn haar laten knippen", "dentist", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil mijn haar laten knippen", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil mijn haar laten knippen", "car_garage", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil mijn haar laten knippen", "restaurant", "off_topic", CI.OFF_TOPIC, "booking_cross"),
]

# "Kan ik mijn auto laten keuren?"
SCENARIOS += [
    _s("Kan ik mijn auto laten keuren?", "car_garage", "on_topic", CI.QUESTION, "booking_cross"),
    _s("Kan ik mijn auto laten keuren?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Kan ik mijn auto laten keuren?", "hair_salon", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Kan ik mijn auto laten keuren?", "dentist", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Kan ik mijn auto laten keuren?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Kan ik mijn auto laten keuren?", "restaurant", "off_topic", CI.OFF_TOPIC, "booking_cross"),
]

# "Ik wil een controle inplannen" — generic scheduling, no domain keywords
SCENARIOS += [
    _s("Ik wil een controle inplannen", "dentist", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een controle inplannen", "car_garage", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een controle inplannen", "klantenservice_ai", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een controle inplannen", "hair_salon", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een controle inplannen", "pizza_restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Ik wil een controle inplannen", "restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
]

# "Hebben jullie plek morgen?"
SCENARIOS += [
    _s("Hebben jullie plek morgen?", "hair_salon", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Hebben jullie plek morgen?", "dentist", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Hebben jullie plek morgen?", "restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Hebben jullie plek morgen?", "car_garage", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Hebben jullie plek morgen?", "pizza_restaurant", "on_topic", CI.APPOINTMENT, "booking_cross"),
    _s("Hebben jullie plek morgen?", "klantenservice_ai", "on_topic", CI.APPOINTMENT, "booking_cross"),
]

# "Ik wil een APK laten doen"
SCENARIOS += [
    _s("Ik wil een APK laten doen", "car_garage", "on_topic", CI.QUESTION, "booking_cross"),
    _s("Ik wil een APK laten doen", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een APK laten doen", "hair_salon", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een APK laten doen", "dentist", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een APK laten doen", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "booking_cross"),
    _s("Ik wil een APK laten doen", "restaurant", "off_topic", CI.OFF_TOPIC, "booking_cross"),
]


# ── 3. PRICING: domain-specific pricing questions ────────────────

# "Wat kost knippen?"
SCENARIOS += [
    _s("Wat kost knippen?", "hair_salon", "on_topic", CI.PRICING, "pricing_cross"),
    _s("Wat kost knippen?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost knippen?", "dentist", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost knippen?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost knippen?", "car_garage", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost knippen?", "restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
]

# "Wat kost een vulling?"
SCENARIOS += [
    _s("Wat kost een vulling?", "dentist", "on_topic", CI.PRICING, "pricing_cross"),
    _s("Wat kost een vulling?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een vulling?", "hair_salon", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een vulling?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een vulling?", "car_garage", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een vulling?", "restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
]

# "Wat kost een APK?"
SCENARIOS += [
    _s("Wat kost een APK?", "car_garage", "on_topic", CI.PRICING, "pricing_cross"),
    _s("Wat kost een APK?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een APK?", "hair_salon", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een APK?", "dentist", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een APK?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een APK?", "restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
]

# "Hoeveel kost een pizza margherita?"
SCENARIOS += [
    _s("Hoeveel kost een pizza margherita?", "pizza_restaurant", "on_topic", CI.PRICING, "pricing_cross"),
    _s("Hoeveel kost een pizza margherita?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Hoeveel kost een pizza margherita?", "hair_salon", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Hoeveel kost een pizza margherita?", "dentist", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Hoeveel kost een pizza margherita?", "car_garage", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Hoeveel kost een pizza margherita?", "restaurant", "on_topic", CI.PRICING, "pricing_cross"),
]

# "Wat kost het starterspakket?"
SCENARIOS += [
    _s("Wat kost het starterspakket?", "klantenservice_ai", "on_topic", CI.PRICING, "pricing_cross"),
    _s("Wat kost het starterspakket?", "hair_salon", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost het starterspakket?", "dentist", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost het starterspakket?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost het starterspakket?", "car_garage", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost het starterspakket?", "restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
]

# "Wat kosten jullie behandelingen?"
SCENARIOS += [
    _s("Wat kosten jullie behandelingen?", "hair_salon", "on_topic", CI.PRICING, "pricing_cross"),
    _s("Wat kosten jullie behandelingen?", "dentist", "on_topic", CI.PRICING, "pricing_cross"),
    _s("Wat kosten jullie behandelingen?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kosten jullie behandelingen?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kosten jullie behandelingen?", "car_garage", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kosten jullie behandelingen?", "restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
]

# "Wat kost een oliewissel?"
SCENARIOS += [
    _s("Wat kost een oliewissel?", "car_garage", "on_topic", CI.PRICING, "pricing_cross"),
    _s("Wat kost een oliewissel?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een oliewissel?", "hair_salon", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een oliewissel?", "dentist", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een oliewissel?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Wat kost een oliewissel?", "restaurant", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
]

# "Hebben jullie een driegangenmenu?"
SCENARIOS += [
    _s("Hebben jullie een driegangenmenu?", "restaurant", "on_topic", CI.QUESTION, "pricing_cross"),
    _s("Hebben jullie een driegangenmenu?", "pizza_restaurant", "on_topic", CI.QUESTION, "pricing_cross"),
    _s("Hebben jullie een driegangenmenu?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Hebben jullie een driegangenmenu?", "hair_salon", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Hebben jullie een driegangenmenu?", "dentist", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
    _s("Hebben jullie een driegangenmenu?", "car_garage", "off_topic", CI.OFF_TOPIC, "pricing_cross"),
]


# ── 4. DOMAIN-SPECIFIC VOCABULARY ────────────────────────────────

# "Doen jullie ook highlights?"
SCENARIOS += [
    _s("Doen jullie ook highlights?", "hair_salon", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Doen jullie ook highlights?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Doen jullie ook highlights?", "dentist", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Doen jullie ook highlights?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Doen jullie ook highlights?", "car_garage", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Doen jullie ook highlights?", "restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
]

# "Kan ik ook een wortelkanaalbehandeling krijgen?"
SCENARIOS += [
    _s("Kan ik ook een wortelkanaalbehandeling krijgen?", "dentist", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Kan ik ook een wortelkanaalbehandeling krijgen?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik ook een wortelkanaalbehandeling krijgen?", "hair_salon", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik ook een wortelkanaalbehandeling krijgen?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik ook een wortelkanaalbehandeling krijgen?", "car_garage", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik ook een wortelkanaalbehandeling krijgen?", "restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
]

# "Doen jullie ook remmen vervangen?"
SCENARIOS += [
    _s("Doen jullie ook remmen vervangen?", "car_garage", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Doen jullie ook remmen vervangen?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Doen jullie ook remmen vervangen?", "hair_salon", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Doen jullie ook remmen vervangen?", "dentist", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Doen jullie ook remmen vervangen?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Doen jullie ook remmen vervangen?", "restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
]

# "Kan ik ook glutenvrij bestellen?"
SCENARIOS += [
    _s("Kan ik ook glutenvrij bestellen?", "restaurant", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Kan ik ook glutenvrij bestellen?", "pizza_restaurant", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Kan ik ook glutenvrij bestellen?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik ook glutenvrij bestellen?", "hair_salon", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik ook glutenvrij bestellen?", "dentist", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik ook glutenvrij bestellen?", "car_garage", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
]

# "Hebben jullie ook een API?"
SCENARIOS += [
    _s("Hebben jullie ook een API?", "klantenservice_ai", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Hebben jullie ook een API?", "hair_salon", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Hebben jullie ook een API?", "dentist", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Hebben jullie ook een API?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Hebben jullie ook een API?", "car_garage", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Hebben jullie ook een API?", "restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
]

# "Kan de airco bijgevuld worden?"
SCENARIOS += [
    _s("Kan de airco bijgevuld worden?", "car_garage", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Kan de airco bijgevuld worden?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan de airco bijgevuld worden?", "hair_salon", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan de airco bijgevuld worden?", "dentist", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan de airco bijgevuld worden?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan de airco bijgevuld worden?", "restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
]

# "Kan ik een proefperiode starten?"
SCENARIOS += [
    _s("Kan ik een proefperiode starten?", "klantenservice_ai", "on_topic", CI.PRICING, "domain_vocab"),
    _s("Kan ik een proefperiode starten?", "hair_salon", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik een proefperiode starten?", "dentist", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik een proefperiode starten?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik een proefperiode starten?", "car_garage", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Kan ik een proefperiode starten?", "restaurant", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
]

# "Hebben jullie een wijnkaart?"
SCENARIOS += [
    _s("Hebben jullie een wijnkaart?", "restaurant", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Hebben jullie een wijnkaart?", "pizza_restaurant", "on_topic", CI.QUESTION, "domain_vocab"),
    _s("Hebben jullie een wijnkaart?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Hebben jullie een wijnkaart?", "hair_salon", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Hebben jullie een wijnkaart?", "dentist", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
    _s("Hebben jullie een wijnkaart?", "car_garage", "off_topic", CI.OFF_TOPIC, "domain_vocab"),
]


# ── 5. AMBIGUOUS UTTERANCES ──────────────────────────────────────

# "Het werkt niet" (universally on-topic — could be anything)
SCENARIOS += [
    _s("Het werkt niet", "klantenservice_ai", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Het werkt niet", "car_garage", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Het werkt niet", "hair_salon", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Het werkt niet", "dentist", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Het werkt niet", "pizza_restaurant", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Het werkt niet", "restaurant", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
]

# "Ik ben niet tevreden" (universally on-topic complaint)
SCENARIOS += [
    _s("Ik ben niet tevreden", "klantenservice_ai", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Ik ben niet tevreden", "car_garage", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Ik ben niet tevreden", "hair_salon", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Ik ben niet tevreden", "dentist", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Ik ben niet tevreden", "pizza_restaurant", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
    _s("Ik ben niet tevreden", "restaurant", "on_topic", CI.COMPLAINT, "ambiguous_cross"),
]

# "Ik wil mijn afspraak annuleren" (universally on-topic)
SCENARIOS += [
    _s("Ik wil mijn afspraak annuleren", "dentist", "on_topic", CI.APPOINTMENT, "ambiguous_cross"),
    _s("Ik wil mijn afspraak annuleren", "hair_salon", "on_topic", CI.APPOINTMENT, "ambiguous_cross"),
    _s("Ik wil mijn afspraak annuleren", "car_garage", "on_topic", CI.APPOINTMENT, "ambiguous_cross"),
    _s("Ik wil mijn afspraak annuleren", "restaurant", "on_topic", CI.APPOINTMENT, "ambiguous_cross"),
    _s("Ik wil mijn afspraak annuleren", "klantenservice_ai", "on_topic", CI.APPOINTMENT, "ambiguous_cross"),
    _s("Ik wil mijn afspraak annuleren", "pizza_restaurant", "on_topic", CI.APPOINTMENT, "ambiguous_cross"),
]

# "Kan ik een mens spreken?" (universally transfer)
SCENARIOS += [
    _s("Kan ik een mens spreken?", "klantenservice_ai", "on_topic", CI.TRANSFER_REQUEST, "ambiguous_cross"),
    _s("Kan ik een mens spreken?", "hair_salon", "on_topic", CI.TRANSFER_REQUEST, "ambiguous_cross"),
    _s("Kan ik een mens spreken?", "dentist", "on_topic", CI.TRANSFER_REQUEST, "ambiguous_cross"),
    _s("Kan ik een mens spreken?", "pizza_restaurant", "on_topic", CI.TRANSFER_REQUEST, "ambiguous_cross"),
    _s("Kan ik een mens spreken?", "car_garage", "on_topic", CI.TRANSFER_REQUEST, "ambiguous_cross"),
    _s("Kan ik een mens spreken?", "restaurant", "on_topic", CI.TRANSFER_REQUEST, "ambiguous_cross"),
]


# ── 6. OFF-TOPIC: genuinely off-topic everywhere ────────────────

GLOBAL_OFF_TOPIC = [
    ("Wat is de hoofdstad van Frankrijk?", CI.OFF_TOPIC),
    ("Hoe laat speelt Ajax?", CI.OFF_TOPIC),
    ("Vertel een grap", CI.OFF_TOPIC),
    ("Wat is het weer vandaag?", CI.OFF_TOPIC),
    ("Hoeveel is 5 maal 7?", CI.OFF_TOPIC),
    ("Schrijf een gedicht over de lente", CI.OFF_TOPIC),
    ("Wat is bitcoin waard?", CI.OFF_TOPIC),
    ("Kan je een hotel boeken in Barcelona?", CI.OFF_TOPIC),
]

for utt, intent in GLOBAL_OFF_TOPIC:
    for company_key in COMPANIES:
        SCENARIOS.append(_s(utt, company_key, "off_topic", intent, "global_off_topic"))


# ── 7. TRANSFER: role-based, company-specific ───────────────────

# "Kan ik de tandarts spreken?"
SCENARIOS += [
    _s("Kan ik de tandarts spreken?", "dentist", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de tandarts spreken?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de tandarts spreken?", "hair_salon", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de tandarts spreken?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de tandarts spreken?", "car_garage", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de tandarts spreken?", "restaurant", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
]

# "Kan ik de monteur spreken?"
SCENARIOS += [
    _s("Kan ik de monteur spreken?", "car_garage", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de monteur spreken?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de monteur spreken?", "hair_salon", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de monteur spreken?", "dentist", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de monteur spreken?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de monteur spreken?", "restaurant", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
]

# "Kan ik de chef spreken?"
SCENARIOS += [
    _s("Kan ik de chef spreken?", "restaurant", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de chef spreken?", "pizza_restaurant", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de chef spreken?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de chef spreken?", "hair_salon", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de chef spreken?", "dentist", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de chef spreken?", "car_garage", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
]

# "Kan ik de kapster spreken?"
SCENARIOS += [
    _s("Kan ik de kapster spreken?", "hair_salon", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de kapster spreken?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de kapster spreken?", "dentist", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de kapster spreken?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de kapster spreken?", "car_garage", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
    _s("Kan ik de kapster spreken?", "restaurant", "off_topic", CI.OFF_TOPIC, "transfer_cross"),
]

# "Kan ik de eigenaar spreken?" — universally on-topic transfer
SCENARIOS += [
    _s("Kan ik de eigenaar spreken?", "klantenservice_ai", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de eigenaar spreken?", "hair_salon", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de eigenaar spreken?", "dentist", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de eigenaar spreken?", "pizza_restaurant", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de eigenaar spreken?", "car_garage", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
    _s("Kan ik de eigenaar spreken?", "restaurant", "on_topic", CI.TRANSFER_REQUEST, "transfer_cross"),
]


# ── 8. ANGRY: domain-specific anger ─────────────────────────────

# "Wat een prutsers, mijn haar is verpest!"
SCENARIOS += [
    _s("Wat een prutsers, mijn haar is verpest!", "hair_salon", "on_topic", CI.ANGER, "angry_cross"),
    _s("Wat een prutsers, mijn haar is verpest!", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Wat een prutsers, mijn haar is verpest!", "dentist", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Wat een prutsers, mijn haar is verpest!", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Wat een prutsers, mijn haar is verpest!", "car_garage", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Wat een prutsers, mijn haar is verpest!", "restaurant", "off_topic", CI.OFF_TOPIC, "angry_cross"),
]

# "Jullie hebben mijn auto kapotgemaakt!"
SCENARIOS += [
    _s("Jullie hebben mijn auto kapotgemaakt!", "car_garage", "on_topic", CI.QUESTION, "angry_cross"),
    _s("Jullie hebben mijn auto kapotgemaakt!", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Jullie hebben mijn auto kapotgemaakt!", "hair_salon", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Jullie hebben mijn auto kapotgemaakt!", "dentist", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Jullie hebben mijn auto kapotgemaakt!", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Jullie hebben mijn auto kapotgemaakt!", "restaurant", "off_topic", CI.OFF_TOPIC, "angry_cross"),
]

# "Dit is de slechtste tandarts ooit!"
SCENARIOS += [
    _s("Dit is de slechtste tandarts ooit!", "dentist", "on_topic", CI.ANGER, "angry_cross"),
    _s("Dit is de slechtste tandarts ooit!", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Dit is de slechtste tandarts ooit!", "hair_salon", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Dit is de slechtste tandarts ooit!", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Dit is de slechtste tandarts ooit!", "car_garage", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Dit is de slechtste tandarts ooit!", "restaurant", "off_topic", CI.OFF_TOPIC, "angry_cross"),
]

# "Ik ben razend, het eten was verschrikkelijk!"
SCENARIOS += [
    _s("Ik ben razend, het eten was verschrikkelijk!", "restaurant", "on_topic", CI.ANGER, "angry_cross"),
    _s("Ik ben razend, het eten was verschrikkelijk!", "pizza_restaurant", "on_topic", CI.ANGER, "angry_cross"),
    _s("Ik ben razend, het eten was verschrikkelijk!", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Ik ben razend, het eten was verschrikkelijk!", "hair_salon", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Ik ben razend, het eten was verschrikkelijk!", "dentist", "off_topic", CI.OFF_TOPIC, "angry_cross"),
    _s("Ik ben razend, het eten was verschrikkelijk!", "car_garage", "off_topic", CI.OFF_TOPIC, "angry_cross"),
]

# "Dit is echt belachelijk" — universally on-topic anger (no domain words)
SCENARIOS += [
    _s("Dit is echt belachelijk", "klantenservice_ai", "on_topic", CI.ANGER, "angry_cross"),
    _s("Dit is echt belachelijk", "hair_salon", "on_topic", CI.ANGER, "angry_cross"),
    _s("Dit is echt belachelijk", "dentist", "on_topic", CI.ANGER, "angry_cross"),
    _s("Dit is echt belachelijk", "pizza_restaurant", "on_topic", CI.ANGER, "angry_cross"),
    _s("Dit is echt belachelijk", "car_garage", "on_topic", CI.ANGER, "angry_cross"),
    _s("Dit is echt belachelijk", "restaurant", "on_topic", CI.ANGER, "angry_cross"),
]


# ── 9. CONFUSED: domain-specific confusion ──────────────────────

# "Ik snap niet hoe ik moet inloggen"
SCENARIOS += [
    _s("Ik snap niet hoe ik moet inloggen", "klantenservice_ai", "on_topic", CI.FRUSTRATION, "confused_cross"),
    _s("Ik snap niet hoe ik moet inloggen", "hair_salon", "off_topic", CI.OFF_TOPIC, "confused_cross"),
    _s("Ik snap niet hoe ik moet inloggen", "dentist", "off_topic", CI.OFF_TOPIC, "confused_cross"),
    _s("Ik snap niet hoe ik moet inloggen", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "confused_cross"),
    _s("Ik snap niet hoe ik moet inloggen", "car_garage", "off_topic", CI.OFF_TOPIC, "confused_cross"),
    _s("Ik snap niet hoe ik moet inloggen", "restaurant", "off_topic", CI.OFF_TOPIC, "confused_cross"),
]

# "Hoe zet ik de voice agent aan?" (SaaS-specific)
SCENARIOS += [
    _s("Hoe zet ik de voice agent aan?", "klantenservice_ai", "on_topic", CI.QUESTION, "confused_cross"),
    _s("Hoe zet ik de voice agent aan?", "hair_salon", "off_topic", CI.OFF_TOPIC, "confused_cross"),
    _s("Hoe zet ik de voice agent aan?", "dentist", "off_topic", CI.OFF_TOPIC, "confused_cross"),
    _s("Hoe zet ik de voice agent aan?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "confused_cross"),
    _s("Hoe zet ik de voice agent aan?", "car_garage", "off_topic", CI.OFF_TOPIC, "confused_cross"),
    _s("Hoe zet ik de voice agent aan?", "restaurant", "off_topic", CI.OFF_TOPIC, "confused_cross"),
]


# ── 10. RESCHEDULE/CANCEL: domain-specific ──────────────────────

# "Ik kan helaas niet meer komen voor mijn knipbeurt"
SCENARIOS += [
    _s("Ik kan helaas niet meer komen voor mijn knipbeurt", "hair_salon", "on_topic", CI.APPOINTMENT, "reschedule_cross"),
    _s("Ik kan helaas niet meer komen voor mijn knipbeurt", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik kan helaas niet meer komen voor mijn knipbeurt", "dentist", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik kan helaas niet meer komen voor mijn knipbeurt", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik kan helaas niet meer komen voor mijn knipbeurt", "car_garage", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik kan helaas niet meer komen voor mijn knipbeurt", "restaurant", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
]

# "Ik wil mijn APK afspraak verzetten"
SCENARIOS += [
    _s("Ik wil mijn APK afspraak verzetten", "car_garage", "on_topic", CI.APPOINTMENT, "reschedule_cross"),
    _s("Ik wil mijn APK afspraak verzetten", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik wil mijn APK afspraak verzetten", "hair_salon", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik wil mijn APK afspraak verzetten", "dentist", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik wil mijn APK afspraak verzetten", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik wil mijn APK afspraak verzetten", "restaurant", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
]

# "Ik wil mijn reservering annuleren" (restaurant-specific)
SCENARIOS += [
    _s("Ik wil mijn reservering annuleren", "restaurant", "on_topic", CI.APPOINTMENT, "reschedule_cross"),
    _s("Ik wil mijn reservering annuleren", "pizza_restaurant", "on_topic", CI.APPOINTMENT, "reschedule_cross"),
    _s("Ik wil mijn reservering annuleren", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik wil mijn reservering annuleren", "hair_salon", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik wil mijn reservering annuleren", "dentist", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
    _s("Ik wil mijn reservering annuleren", "car_garage", "off_topic", CI.OFF_TOPIC, "reschedule_cross"),
]


# ── 11. SAME UTTERANCE, DIFFERENT SCOPE (more examples) ─────────

# "Het duurt veel te lang" — generic complaint, no domain keywords
SCENARIOS += [
    _s("Het duurt veel te lang", "klantenservice_ai", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Het duurt veel te lang", "car_garage", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Het duurt veel te lang", "hair_salon", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Het duurt veel te lang", "dentist", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Het duurt veel te lang", "pizza_restaurant", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Het duurt veel te lang", "restaurant", "on_topic", CI.QUESTION, "same_utt_cross"),
]

# "Ik wil graag een demo"
SCENARIOS += [
    _s("Ik wil graag een demo", "klantenservice_ai", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Ik wil graag een demo", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik wil graag een demo", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik wil graag een demo", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik wil graag een demo", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik wil graag een demo", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "Kan ik mijn abonnement opzeggen?"
SCENARIOS += [
    _s("Kan ik mijn abonnement opzeggen?", "klantenservice_ai", "on_topic", CI.PRICING, "same_utt_cross"),
    _s("Kan ik mijn abonnement opzeggen?", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Kan ik mijn abonnement opzeggen?", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Kan ik mijn abonnement opzeggen?", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Kan ik mijn abonnement opzeggen?", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Kan ik mijn abonnement opzeggen?", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "Mijn tand doet pijn"
SCENARIOS += [
    _s("Mijn tand doet pijn", "dentist", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Mijn tand doet pijn", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Mijn tand doet pijn", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Mijn tand doet pijn", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Mijn tand doet pijn", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Mijn tand doet pijn", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "De motor maakt een raar geluid"
SCENARIOS += [
    _s("De motor maakt een raar geluid", "car_garage", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("De motor maakt een raar geluid", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("De motor maakt een raar geluid", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("De motor maakt een raar geluid", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("De motor maakt een raar geluid", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("De motor maakt een raar geluid", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "Ik wil upgraden naar het premium pakket"
SCENARIOS += [
    _s("Ik wil upgraden naar het premium pakket", "klantenservice_ai", "on_topic", CI.PRICING, "same_utt_cross"),
    _s("Ik wil upgraden naar het premium pakket", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik wil upgraden naar het premium pakket", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik wil upgraden naar het premium pakket", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik wil upgraden naar het premium pakket", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik wil upgraden naar het premium pakket", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "Kunnen jullie ook bezorgen?"
SCENARIOS += [
    _s("Kunnen jullie ook bezorgen?", "pizza_restaurant", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Kunnen jullie ook bezorgen?", "restaurant", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Kunnen jullie ook bezorgen?", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Kunnen jullie ook bezorgen?", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Kunnen jullie ook bezorgen?", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Kunnen jullie ook bezorgen?", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "Hoe laat gaan jullie dicht?"
SCENARIOS += [
    _s("Hoe laat gaan jullie dicht?", "klantenservice_ai", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Hoe laat gaan jullie dicht?", "hair_salon", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Hoe laat gaan jullie dicht?", "dentist", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Hoe laat gaan jullie dicht?", "pizza_restaurant", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Hoe laat gaan jullie dicht?", "car_garage", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Hoe laat gaan jullie dicht?", "restaurant", "on_topic", CI.QUESTION, "same_utt_cross"),
]

# "Wat is jullie adres?"
SCENARIOS += [
    _s("Wat is jullie adres?", "klantenservice_ai", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Wat is jullie adres?", "hair_salon", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Wat is jullie adres?", "dentist", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Wat is jullie adres?", "pizza_restaurant", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Wat is jullie adres?", "car_garage", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Wat is jullie adres?", "restaurant", "on_topic", CI.QUESTION, "same_utt_cross"),
]

# "Mijn baard moet bijgetrimd worden"
SCENARIOS += [
    _s("Mijn baard moet bijgetrimd worden", "hair_salon", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Mijn baard moet bijgetrimd worden", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Mijn baard moet bijgetrimd worden", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Mijn baard moet bijgetrimd worden", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Mijn baard moet bijgetrimd worden", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Mijn baard moet bijgetrimd worden", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "De portie was veel te klein"
SCENARIOS += [
    _s("De portie was veel te klein", "restaurant", "on_topic", CI.COMPLAINT, "same_utt_cross"),
    _s("De portie was veel te klein", "pizza_restaurant", "on_topic", CI.COMPLAINT, "same_utt_cross"),
    _s("De portie was veel te klein", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("De portie was veel te klein", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("De portie was veel te klein", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("De portie was veel te klein", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "Ik zoek een integratie met Slack"
SCENARIOS += [
    _s("Ik zoek een integratie met Slack", "klantenservice_ai", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Ik zoek een integratie met Slack", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik zoek een integratie met Slack", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik zoek een integratie met Slack", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik zoek een integratie met Slack", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Ik zoek een integratie met Slack", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "Er zit een kras op mijn auto"
SCENARIOS += [
    _s("Er zit een kras op mijn auto", "car_garage", "on_topic", CI.COMPLAINT, "same_utt_cross"),
    _s("Er zit een kras op mijn auto", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Er zit een kras op mijn auto", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Er zit een kras op mijn auto", "dentist", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Er zit een kras op mijn auto", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Er zit een kras op mijn auto", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]

# "Het bloedend tandvlees is nog niet gestopt"
SCENARIOS += [
    _s("Het bloedend tandvlees is nog niet gestopt", "dentist", "on_topic", CI.QUESTION, "same_utt_cross"),
    _s("Het bloedend tandvlees is nog niet gestopt", "klantenservice_ai", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Het bloedend tandvlees is nog niet gestopt", "hair_salon", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Het bloedend tandvlees is nog niet gestopt", "pizza_restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Het bloedend tandvlees is nog niet gestopt", "car_garage", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
    _s("Het bloedend tandvlees is nog niet gestopt", "restaurant", "off_topic", CI.OFF_TOPIC, "same_utt_cross"),
]


# ═══════════════════════════════════════════════════════════════════
#  TEST RUNNER
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TestResult:
    scenario: ScopeScenario
    actual_intent: CallerIntent
    actual_off_topic: bool
    actual_scope: str
    intent_correct: bool
    scope_correct: bool
    passed: bool
    failure_reason: str = ""


def run_scenario(sc: ScopeScenario) -> TestResult:
    """Run a single scope-aware scenario using company-aware scope checking."""
    company_scope = COMPANY_SCOPES.get(sc.company, CompanyScope())

    intent, conf = classify_intent_with_context(sc.utterance)
    off_topic_flag = is_off_topic(sc.utterance, company_scope)

    # Layer 1: intent-based off-topic with domain exemption
    if intent == CI.OFF_TOPIC:
        scope_result = check_company_scope(sc.utterance, company_scope)
        if scope_result == "on_topic":
            actual_scope = "on_topic"
        else:
            actual_scope = "off_topic"
    elif off_topic_flag:
        actual_scope = "off_topic"
    else:
        # Layer 2: cross-domain scope check
        scope_result = check_company_scope(sc.utterance, company_scope)
        if scope_result == "off_topic":
            actual_scope = "off_topic"
        else:
            actual_scope = "on_topic"

    scope_correct = (actual_scope == sc.expected_scope)

    if sc.expected_scope == "on_topic":
        intent_correct = (intent == sc.expected_intent)
    else:
        intent_correct = True

    passed = scope_correct and intent_correct

    failure_reason = ""
    if not scope_correct:
        failure_reason = (
            f"SCOPE MISMATCH: expected={sc.expected_scope} "
            f"actual={actual_scope} (intent={intent.value}, "
            f"off_topic_flag={off_topic_flag}, "
            f"company_scope={company_scope.business_type})"
        )
    elif not intent_correct:
        failure_reason = (
            f"INTENT MISMATCH: expected={sc.expected_intent.value} "
            f"actual={intent.value}"
        )

    return TestResult(
        scenario=sc,
        actual_intent=intent,
        actual_off_topic=off_topic_flag,
        actual_scope=actual_scope,
        intent_correct=intent_correct,
        scope_correct=scope_correct,
        passed=passed,
        failure_reason=failure_reason,
    )


def run_all():
    print(f"\n{'='*72}")
    print(f"  SCOPE-AWARE CROSS-INDUSTRY TEST")
    print(f"  {len(SCENARIOS)} scenarios across {len(COMPANIES)} companies")
    print(f"{'='*72}\n")

    t0 = time.time()
    results: list[TestResult] = [run_scenario(sc) for sc in SCENARIOS]
    elapsed = time.time() - t0

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    # ── Overall metrics ──────────────────────────────────────────
    print(f"{'─'*72}")
    print(f"  OVERALL RESULTS")
    print(f"{'─'*72}")
    print(f"  Total scenarios:  {total}")
    print(f"  Passed:           {passed} ({100*passed/total:.1f}%)")
    print(f"  Failed:           {failed} ({100*failed/total:.1f}%)")
    print(f"  Runtime:          {elapsed:.2f}s")
    print()

    # ── Scope correctness breakdown ──────────────────────────────
    scope_correct = sum(1 for r in results if r.scope_correct)
    scope_wrong = total - scope_correct
    print(f"  SCOPE ACCURACY:   {scope_correct}/{total} ({100*scope_correct/total:.1f}%)")
    print(f"  Scope failures:   {scope_wrong}")
    print()

    # Count specific scope failure types
    should_be_off_but_on = sum(
        1 for r in results
        if not r.scope_correct and r.scenario.expected_scope == "off_topic"
    )
    should_be_on_but_off = sum(
        1 for r in results
        if not r.scope_correct and r.scenario.expected_scope == "on_topic"
    )
    print(f"  Should be OFF-TOPIC but treated as ON-TOPIC:  {should_be_off_but_on}")
    print(f"  Should be ON-TOPIC but treated as OFF-TOPIC:  {should_be_on_but_off}")
    print()

    # ── By company ───────────────────────────────────────────────
    print(f"{'─'*72}")
    print(f"  RESULTS BY COMPANY")
    print(f"{'─'*72}")
    for ckey, cinfo in COMPANIES.items():
        cr = [r for r in results if r.scenario.company == ckey]
        cp = sum(1 for r in cr if r.passed)
        cs = sum(1 for r in cr if r.scope_correct)
        print(f"  {cinfo['name']:35s}  pass={cp:3d}/{len(cr):3d} ({100*cp/len(cr):5.1f}%)  "
              f"scope={cs:3d}/{len(cr):3d} ({100*cs/len(cr):5.1f}%)")
    print()

    # ── By category ──────────────────────────────────────────────
    print(f"{'─'*72}")
    print(f"  RESULTS BY CATEGORY")
    print(f"{'─'*72}")
    categories = sorted(set(r.scenario.category for r in results))
    for cat in categories:
        cr = [r for r in results if r.scenario.category == cat]
        cp = sum(1 for r in cr if r.passed)
        cs = sum(1 for r in cr if r.scope_correct)
        print(f"  {cat:25s}  pass={cp:3d}/{len(cr):3d} ({100*cp/len(cr):5.1f}%)  "
              f"scope={cs:3d}/{len(cr):3d} ({100*cs/len(cr):5.1f}%)")
    print()

    # ── Failure analysis ─────────────────────────────────────────
    failures = [r for r in results if not r.passed]
    if failures:
        print(f"{'─'*72}")
        print(f"  FAILURE ANALYSIS ({len(failures)} failures)")
        print(f"{'─'*72}")

        # Cluster: same utterance classified identically across all companies
        # (shows the global classification problem)
        print(f"\n  --- GLOBAL CLASSIFICATION PROBLEMS ---")
        print(f"  (Same utterance classified identically regardless of company)\n")

        utterance_groups: dict[str, list[TestResult]] = {}
        for r in results:
            utterance_groups.setdefault(r.scenario.utterance, []).append(r)

        global_problem_count = 0
        for utt, group in utterance_groups.items():
            scopes_expected = set(r.scenario.expected_scope for r in group)
            # Only interesting if the utterance SHOULD differ across companies
            if len(scopes_expected) < 2:
                continue

            scopes_actual = set(r.actual_scope for r in group)
            if len(scopes_actual) == 1:
                # Classified the same for ALL companies — this is the problem
                actual = list(scopes_actual)[0]
                should_be_on = [r for r in group if r.scenario.expected_scope == "on_topic"]
                should_be_off = [r for r in group if r.scenario.expected_scope == "off_topic"]

                if actual == "on_topic" and should_be_off:
                    global_problem_count += 1
                    companies_wrong = [COMPANIES[r.scenario.company]["name"] for r in should_be_off]
                    companies_right = [COMPANIES[r.scenario.company]["name"] for r in should_be_on]
                    print(f"  [{global_problem_count}] \"{utt}\"")
                    print(f"      Classified globally as: ON-TOPIC ({group[0].actual_intent.value})")
                    print(f"      Correct for:   {', '.join(companies_right)}")
                    print(f"      WRONG for:     {', '.join(companies_wrong)} (should be off-topic)")
                    print()
                elif actual == "off_topic" and should_be_on:
                    global_problem_count += 1
                    companies_wrong = [COMPANIES[r.scenario.company]["name"] for r in should_be_on]
                    companies_right = [COMPANIES[r.scenario.company]["name"] for r in should_be_off]
                    print(f"  [{global_problem_count}] \"{utt}\"")
                    print(f"      Classified globally as: OFF-TOPIC")
                    print(f"      Correct for:   {', '.join(companies_right)}")
                    print(f"      WRONG for:     {', '.join(companies_wrong)} (should be on-topic)")
                    print()

        if global_problem_count == 0:
            print(f"  (None detected)")
        else:
            print(f"  Total global classification problems: {global_problem_count}")
        print()

        # List all failures
        print(f"\n  --- ALL FAILURES (detailed) ---\n")
        for i, r in enumerate(failures[:80], 1):
            cname = COMPANIES[r.scenario.company]["name"]
            print(f"  [{i:3d}] [{cname}] \"{r.scenario.utterance}\"")
            print(f"        {r.failure_reason}")

        if len(failures) > 80:
            print(f"\n  ... and {len(failures)-80} more failures (truncated)")

    # ── Architecture gap analysis ────────────────────────────────
    # ── Remaining failures detail ──────────────────────────────
    if not failures:
        print(f"\n  ALL SCENARIOS PASSED — company-aware scope handling is working.")
    else:
        print(f"\n  {len(failures)} remaining failures to investigate.")

    print(f"{'='*72}")
    print(f"  END OF REPORT")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    run_all()
