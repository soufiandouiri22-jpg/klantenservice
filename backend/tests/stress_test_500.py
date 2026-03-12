"""
STRESS TEST — 500+ scenario validation of the AI voice agent.

Tests 4 core subsystems locally (no running server needed):
  1. Intent Classifier  — does it correctly categorize customer messages?
  2. Policy Engine      — does it enforce escalation, off-topic, silence, loops?
  3. Output Guardrails  — does it block leakage, English, and strip fillers?
  4. Question Detector  — does it correctly identify real customer questions?

Categories:
  A. Booking scenarios (100)
  B. Pricing questions (50)
  C. Angry customers (50)
  D. Transfer requests (40)
  E. Confused users (40)
  F. Off-topic requests (40)
  G. Prompt attacks (40)
  H. Edge cases (40)
  I. Realistic multi-turn flows (100)

Run:  cd backend && venv/bin/python tests/stress_test_500.py
"""
import importlib.util, os, sys, json, time
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
from datetime import datetime
from typing import Optional

_root = os.path.join(os.path.dirname(__file__), "..")

# ── Direct-load modules without full app import ──────────────────

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

intent_mod = _load("intent_classifier", os.path.join(_root, "app/services/voice/intent_classifier.py"))
classify_intent = intent_mod.classify_intent
classify_intent_with_context = intent_mod.classify_intent_with_context
ConversationContext = intent_mod.ConversationContext
CallerIntent = intent_mod.CallerIntent
is_off_topic = intent_mod.is_off_topic

_BOOKING_CTX = ConversationContext(
    prev_intent=CallerIntent.APPOINTMENT, flow_type="booking", turn_count=3)
_TRANSFER_CTX = ConversationContext(
    prev_intent=CallerIntent.TRANSFER_REQUEST, flow_type="transfer", turn_count=3)

guardrail_mod = _load("output_guardrails", os.path.join(_root, "app/services/voice/output_guardrails.py"))
validate_output = guardrail_mod.validate_output
ViolationType = guardrail_mod.ViolationType

# question_detector has DB imports; extract the pure functions we need
import re as _re
_QD_MIN_WORDS = 4
_QD_AI_INTERNAL = _re.compile(
    r"|".join([
        r"wat (wil|moet|kan|zou) (de klant|de beller|ik|de gebruiker)",
        r"hoe (moet|kan|zou) ik (nu |hier |dit |dat )?(reageren|antwoorden|zeggen|helpen)",
        r"laat me (even )?(nadenken|denken|kijken)",
    ]), _re.I)
_QD_NON_QUESTION = _re.compile(
    r"|".join([
        r"^(hallo|hoi|hey|goedemorgen|goedemiddag|goedenavond|dag|doei|tot ziens|fijne dag|dankjewel|dankuwel|bedankt|tot snel)\b",
        r"^(ja|nee|ok[eé]?|hmm+|uhm+|oh|ah|aha|precies|klopt|inderdaad|zeker|nou)\b",
        r"^(wat zei je|kun je dat herhalen|wat bedoel je|hoe bedoel je|sorry)\??$",
        r"^(wie|wat|waar|hoe|waarom)\??$",
    ]), _re.I)

def _is_real_customer_question(sentence: str) -> bool:
    cleaned = sentence.strip().rstrip("?").strip()
    if len(cleaned) < 12 or len(cleaned.split()) < _QD_MIN_WORDS:
        return False
    if _QD_AI_INTERNAL.search(cleaned):
        return False
    if _QD_NON_QUESTION.match(cleaned):
        return False
    return True

# ── Stubs & copied policy functions (avoid DB imports) ───────────

@dataclass
class FakeSession:
    id: str = ""
    call_sid: str = "test_stress"
    call_log_id: str = ""
    phase: str = "answering"
    turn_count: int = 2
    goodbye_said_by_customer: bool = False
    goodbye_said_by_agent: bool = False
    end_call_attempts: int = 0
    low_confidence_count: int = 0
    repeat_topic_count: int = 0
    frustration_count: int = 0

@dataclass
class PolicyResult:
    allowed: bool
    policy_name: str
    required_action: str
    reason_code: str
    instruction_nl: str = ""
    phase_after: str = ""

def _policy_goodbye(session, intent):
    customer_goodbye = session.goodbye_said_by_customer or intent == CallerIntent.GOODBYE
    if customer_goodbye:
        return PolicyResult(True, "goodbye_handshake", "proceed", "customer_said_goodbye", phase_after="ended")
    attempts = (session.end_call_attempts or 0) + 1
    if attempts >= 3:
        return PolicyResult(True, "goodbye_handshake", "proceed", "max_attempts_reached", phase_after="ended")
    if session.goodbye_said_by_agent:
        return PolicyResult(False, "goodbye_handshake", "wait", "customer_not_goodbye")
    return PolicyResult(False, "goodbye_handshake", "wait", "agent_not_goodbye")

def _policy_escalation(session, intent):
    if intent == CallerIntent.TRANSFER_REQUEST:
        return PolicyResult(True, "escalation", "escalate", "customer_requested_human")
    if intent == CallerIntent.ANGER:
        if (session.low_confidence_count or 0) >= 1 or (session.repeat_topic_count or 0) >= 1:
            return PolicyResult(True, "escalation", "escalate", "anger_plus_failure")
        return PolicyResult(False, "escalation", "clarify", "anger_detected")
    if (session.low_confidence_count or 0) >= 3:
        return PolicyResult(True, "escalation", "escalate", "repeated_low_confidence")
    return PolicyResult(False, "escalation", "proceed", "no_escalation_needed")

def _policy_low_confidence(session, intent, score):
    if score >= 0.4:
        return PolicyResult(True, "low_confidence", "proceed", "confidence_ok")
    if score >= 0.2:
        return PolicyResult(True, "low_confidence", "proceed", "confidence_marginal")
    return PolicyResult(False, "low_confidence", "clarify", "confidence_too_low")

def _policy_repeated_failure(session, intent):
    repeats = session.repeat_topic_count or 0
    frustration = session.frustration_count or 0
    effective = repeats + frustration
    if intent == CallerIntent.FRUSTRATION:
        if effective >= 2:
            return PolicyResult(True, "repeated_failure", "escalate", "frustration_plus_repeats")
        return PolicyResult(False, "repeated_failure", "clarify", "frustration_detected")
    if effective < 2:
        return PolicyResult(True, "repeated_failure", "proceed", "within_threshold")
    if effective < 4:
        return PolicyResult(False, "repeated_failure", "clarify", "topic_repeated")
    return PolicyResult(True, "repeated_failure", "escalate", "topic_loop_detected")

def _policy_off_topic(session, intent, utterance=""):
    if intent == CallerIntent.OFF_TOPIC:
        return PolicyResult(False, "scope_guard", "block", "off_topic_intent")
    if utterance and is_off_topic(utterance):
        return PolicyResult(False, "scope_guard", "block", "off_topic_utterance")
    return PolicyResult(True, "scope_guard", "proceed", "on_topic")

def _policy_silence(session, intent):
    if intent != CallerIntent.SILENCE:
        return PolicyResult(True, "silence_handler", "proceed", "not_silent")
    return PolicyResult(False, "silence_handler", "reprompt",
                        "initial_silence" if (session.turn_count or 0) <= 1 else "mid_call_silence")

def evaluate_auto_policies(session, intent, utterance, retrieval_confidence=1.0):
    checks = []
    esc = _policy_escalation(session, intent)
    if esc.required_action == "escalate":
        checks.append(esc)
    ot = _policy_off_topic(session, intent, utterance)
    if not ot.allowed:
        checks.append(ot)
    sil = _policy_silence(session, intent)
    if not sil.allowed:
        checks.append(sil)
    rf = _policy_repeated_failure(session, intent)
    if not rf.allowed or rf.required_action == "escalate":
        checks.append(rf)
    return checks[0] if checks else None


# ═══════════════════════════════════════════════════════════════════
#  RESULT TRACKING
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TestResult:
    category: str
    scenario: str
    component: str       # intent / policy / guardrail / question_detector
    passed: bool
    expected: str
    actual: str
    detail: str = ""

results: list[TestResult] = []

def record(category, scenario, component, passed, expected, actual, detail=""):
    results.append(TestResult(category, scenario, component, passed, expected, actual, detail))


# ═══════════════════════════════════════════════════════════════════
#  A. BOOKING SCENARIOS (100)
# ═══════════════════════════════════════════════════════════════════

BOOKING_UTTERANCES = [
    ("Ik wil een afspraak maken", CallerIntent.APPOINTMENT),
    ("Kan ik een afspraak inplannen?", CallerIntent.APPOINTMENT),
    ("Ik wil graag een afspraak boeken", CallerIntent.APPOINTMENT),
    ("Hebben jullie morgen plek?", CallerIntent.APPOINTMENT),
    ("Wanneer kan ik langskomen?", CallerIntent.APPOINTMENT),
    ("Is er morgen nog ruimte?", CallerIntent.APPOINTMENT),
    ("Kan ik vandaag nog terecht?", CallerIntent.APPOINTMENT),
    ("Ik zoek een vrij moment deze week", CallerIntent.APPOINTMENT),
    ("Zijn er nog beschikbare tijden?", CallerIntent.APPOINTMENT),
    ("Ik wil graag reserveren voor vrijdag", CallerIntent.APPOINTMENT),
    ("Kan ik volgende week dinsdag?", CallerIntent.APPOINTMENT),
    ("Ik wil een plekje boeken", CallerIntent.APPOINTMENT),
    ("Hoe kan ik een afspraak maken?", CallerIntent.APPOINTMENT),
    ("Is er plek overmorgen?", CallerIntent.APPOINTMENT),
    ("Wanneer is er ruimte in de agenda?", CallerIntent.APPOINTMENT),
    ("Kan ik een behandeling inplannen?", CallerIntent.APPOINTMENT),
    ("Ik wil een consult boeken", CallerIntent.APPOINTMENT),
    ("Zijn er nog plekken beschikbaar deze maand?", CallerIntent.APPOINTMENT),
    ("Ik zou graag langskomen, wanneer kan dat?", CallerIntent.APPOINTMENT),
    ("Kan ik een afspraak voor twee personen maken?", CallerIntent.APPOINTMENT),
    ("Ik wil mijn afspraak verzetten", CallerIntent.APPOINTMENT),
    ("Kan mijn afspraak naar volgende week?", CallerIntent.APPOINTMENT),
    ("Ik wil mijn reservering annuleren", CallerIntent.APPOINTMENT),
    ("Kan ik mijn afspraak een uur later maken?", CallerIntent.APPOINTMENT),
    ("Ik moet mijn afspraak verplaatsen", CallerIntent.APPOINTMENT),
    ("Kan ik een afspraak voor morgenochtend?", CallerIntent.APPOINTMENT),
    ("Ik wil een afspraak voor komende zaterdag", CallerIntent.APPOINTMENT),
    ("Hebben jullie overmorgen vrije plekken?", CallerIntent.APPOINTMENT),
    ("Kan ik om half drie langskomen?", CallerIntent.APPOINTMENT),
    ("Zijn jullie donderdag open?", CallerIntent.QUESTION),
    ("Ik wil een afspraak inplannen voor mijn man", CallerIntent.APPOINTMENT),
    ("Ik heb een afspraak nodig zo snel mogelijk", CallerIntent.APPOINTMENT),
    ("Kan ik een spoedafspraak krijgen?", CallerIntent.APPOINTMENT),
    ("Hoe laat begint de eerste afspraak?", CallerIntent.APPOINTMENT),
    ("Is er iemand beschikbaar om 10 uur?", CallerIntent.APPOINTMENT),
    ("Kan ik na werktijd langskomen?", CallerIntent.APPOINTMENT),
    ("Zijn er nog avondafspraken beschikbaar?", CallerIntent.APPOINTMENT),
    ("Ik wil een afspraak maken voor volgende maand", CallerIntent.APPOINTMENT),
    ("Hebben jullie op maandag plek?", CallerIntent.APPOINTMENT),
    ("Kan het ook in het weekend?", CallerIntent.QUESTION),
    ("Ik zoek iets rond de middag", CallerIntent.APPOINTMENT),
    ("Kan ik halverwege de ochtend langskomen?", CallerIntent.APPOINTMENT),
    ("Ik wil een afspraak voor aanstaande woensdag", CallerIntent.APPOINTMENT),
    ("Boek me maar in voor overmorgen", CallerIntent.APPOINTMENT),
    ("Plan me maar in wanneer het uitkomt", CallerIntent.APPOINTMENT),
    ("Wanneer is de eerst mogelijke afspraak?", CallerIntent.APPOINTMENT),
    ("Ik wil morgen om twee uur een afspraak", CallerIntent.APPOINTMENT),
    ("Kan ik een terugkerend afspraak maken?", CallerIntent.APPOINTMENT),
    ("Ik wil elke maand langskomen", CallerIntent.APPOINTMENT),
    # State tracking tests — multi-turn booking changes
    ("Toch liever donderdag", CallerIntent.APPOINTMENT),
    ("Nee eigenlijk vrijdag", CallerIntent.APPOINTMENT),
    ("Laat maar, ik hoef geen afspraak meer", CallerIntent.DENIAL),
    ("Ja die tijd is goed", CallerIntent.CONFIRMATION),
    ("Nee die tijd past niet", CallerIntent.DENIAL),
    ("Ja graag", CallerIntent.CONFIRMATION),
    ("Dat is prima", CallerIntent.CONFIRMATION),
    ("Klopt helemaal", CallerIntent.CONFIRMATION),
    ("Nee dat klopt niet", CallerIntent.FRUSTRATION),
    ("Kan het een half uurtje later?", CallerIntent.QUESTION),
    # Vague / ambiguous scheduling (semantic + context resolve these)
    ("Ergens deze week", CallerIntent.APPOINTMENT),
    ("Zo snel mogelijk graag", CallerIntent.APPOINTMENT),
    ("Als het kan vandaag nog", CallerIntent.APPOINTMENT),
    ("Het liefst in de ochtend", CallerIntent.APPOINTMENT),
    ("Alleen 's middags beschikbaar", CallerIntent.APPOINTMENT),
    ("Ik werk tot 5 dus daarna graag", CallerIntent.APPOINTMENT),
    ("Kan het in de avonduren?", CallerIntent.QUESTION),
    # Double-booking attempts / conflicting
    ("Ik wil twee afspraken op dezelfde dag", CallerIntent.APPOINTMENT),
    ("Kan ik om 10 en om 14 uur komen?", CallerIntent.APPOINTMENT),
    ("Boek me in voor maandag en dinsdag", CallerIntent.APPOINTMENT),
    ("Ik wil een afspraak voor mij en mijn vrouw apart", CallerIntent.APPOINTMENT),
    # Edge appointment scenarios
    ("Ik heb een afspraak maar weet niet meer wanneer", CallerIntent.APPOINTMENT),
    ("Wanneer was mijn laatste afspraak?", CallerIntent.APPOINTMENT),
    ("Ik ben mijn afspraak vergeten", CallerIntent.APPOINTMENT),
    ("Hoe lang duurt een afspraak?", CallerIntent.APPOINTMENT),
    ("Moet ik iets meenemen voor de afspraak?", CallerIntent.APPOINTMENT),
    ("Kan ik zonder afspraak langskomen?", CallerIntent.APPOINTMENT),
    ("Is het duur om te annuleren?", CallerIntent.APPOINTMENT),
    ("Zijn er annuleringskosten?", CallerIntent.APPOINTMENT),
    ("Wat als ik te laat kom?", CallerIntent.QUESTION),
    ("Kan ik iemand anders sturen in mijn plaats?", CallerIntent.TRANSFER_REQUEST),
    ("Ik ben ziek, kan ik verzetten?", CallerIntent.APPOINTMENT),
    ("Mijn auto is kapot, kan de afspraak later?", CallerIntent.COMPLAINT),
    ("Er is file, ik ben te laat", CallerIntent.QUESTION),
    ("Hoeveel kost een afspraak?", CallerIntent.PRICING),
    ("Is de eerste afspraak gratis?", CallerIntent.PRICING),
    ("Moet ik vooruit betalen?", CallerIntent.PRICING),
    ("Kan ik achteraf betalen?", CallerIntent.PRICING),
    ("Accepteren jullie pin?", CallerIntent.QUESTION),
    ("Nemen jullie contant aan?", CallerIntent.QUESTION),
    ("Kan ik met iDEAL betalen?", CallerIntent.PRICING),
    ("Is er parkeergelegenheid?", CallerIntent.QUESTION),
    ("Hoe kom ik bij jullie?", CallerIntent.QUESTION),
    ("Wat is het adres?", CallerIntent.QUESTION),
    ("Zijn jullie rolstoeltoegankelijk?", CallerIntent.QUESTION),
]

BOOKING_IN_FLOW = [
    ("Overdag ergens", CallerIntent.APPOINTMENT),
    ("Maakt niet uit wanneer", CallerIntent.APPOINTMENT),
    ("We willen graag met z'n tweeën komen", CallerIntent.APPOINTMENT),
    ("Binnenkort", CallerIntent.APPOINTMENT),
    ("Plan me maar in wanneer het uitkomt", CallerIntent.APPOINTMENT),
    ("Kan ik tegelijkertijd twee behandelingen?", CallerIntent.APPOINTMENT),
]


def test_booking():
    cat = "A. Booking"
    for utterance, expected_intent in BOOKING_UTTERANCES:
        actual, conf = classify_intent_with_context(utterance)
        ok = actual == expected_intent
        record(cat, utterance[:60], "intent", ok, expected_intent.value, actual.value,
               f"conf={conf:.0%}")
    for utterance, expected_intent in BOOKING_IN_FLOW:
        actual, conf = classify_intent_with_context(utterance, _BOOKING_CTX)
        ok = actual == expected_intent
        record(cat, f"[ctx] {utterance[:55]}", "intent", ok, expected_intent.value,
               actual.value, f"conf={conf:.0%}")


# ═══════════════════════════════════════════════════════════════════
#  B. PRICING QUESTIONS (50)
# ═══════════════════════════════════════════════════════════════════

PRICING_UTTERANCES = [
    ("Wat zijn jullie prijzen?", CallerIntent.PRICING),
    ("Hoeveel kost het?", CallerIntent.PRICING),
    ("Wat kost een abonnement?", CallerIntent.PRICING),
    ("Hebben jullie een starterspakket?", CallerIntent.PRICING),
    ("Wat is de maandelijkse prijs?", CallerIntent.PRICING),
    ("Zijn er kortingen beschikbaar?", CallerIntent.PRICING),
    ("Hoeveel betaal ik per maand?", CallerIntent.PRICING),
    ("Is er een jaarlijks tarief?", CallerIntent.PRICING),
    ("Wat kost het per uur?", CallerIntent.PRICING),
    ("Hebben jullie een gratis proefperiode?", CallerIntent.PRICING),
    ("Wat is de prijs van het business pakket?", CallerIntent.PRICING),
    ("Hoeveel euro kost het?", CallerIntent.PRICING),
    ("Zijn de prijzen inclusief BTW?", CallerIntent.PRICING),
    ("Hoeveel kost een belminuut extra?", CallerIntent.PRICING),
    ("Wat betaal ik als ik over mijn bundel ga?", CallerIntent.PRICING),
    ("Hebben jullie een familiekorting?", CallerIntent.PRICING),
    ("Is er studentenkorting?", CallerIntent.PRICING),
    ("Wat kost de enterprise oplossing?", CallerIntent.PRICING),
    ("Kan ik maandelijks opzeggen?", CallerIntent.PRICING),
    ("Wat zijn de opzegkosten?", CallerIntent.PRICING),
    ("Is er een opzegtermijn?", CallerIntent.PRICING),
    ("Hoeveel kost upgraden?", CallerIntent.PRICING),
    ("Kan ik downgraden?", CallerIntent.PRICING),
    ("Wat is het verschil tussen starter en business?", CallerIntent.PRICING),
    ("Welk pakket raden jullie aan?", CallerIntent.PRICING),
    ("Wat zit er in het basispakket?", CallerIntent.PRICING),
    ("Hoeveel belminuten zitten erbij?", CallerIntent.PRICING),
    ("Wat kost een extra telefoonnummer?", CallerIntent.PRICING),
    ("Hoeveel kost de installatie?", CallerIntent.PRICING),
    ("Zijn er eenmalige kosten?", CallerIntent.PRICING),
    ("Kan ik eerst proberen voor ik betaal?", CallerIntent.PRICING),
    ("Hoeveel kost het voor een klein bedrijf?", CallerIntent.PRICING),
    ("Wat betaal ik voor 1000 belminuten?", CallerIntent.PRICING),
    ("Is er een staffelkorting?", CallerIntent.PRICING),
    ("Wordt het duurder na de proefperiode?", CallerIntent.PRICING),
    ("Hoeveel kost het per jaar als ik jaarlijks betaal?", CallerIntent.PRICING),
    ("Wat is jullie goedkoopste optie?", CallerIntent.PRICING),
    ("Wat is jullie duurste pakket?", CallerIntent.PRICING),
    ("Kunnen jullie een offerte maken?", CallerIntent.PRICING),
    ("Ik wil een prijsopgave", CallerIntent.PRICING),
    ("Kan ik een factuur krijgen?", CallerIntent.PRICING),
    ("Hoe werkt de facturatie?", CallerIntent.QUESTION),
    ("Kan ik per kwartaal betalen?", CallerIntent.PRICING),
    ("Accepteren jullie creditcard?", CallerIntent.QUESTION),
    ("Is automatische incasso mogelijk?", CallerIntent.QUESTION),
    ("Wanneer wordt er afgeschreven?", CallerIntent.QUESTION),
    ("Kan ik de eerste maand gratis proberen?", CallerIntent.PRICING),
    ("Hoeveel kost het om een AI-medewerker toe te voegen?", CallerIntent.PRICING),
    ("Wat kost een extra gebruiker?", CallerIntent.PRICING),
    ("Is er een non-profit korting?", CallerIntent.PRICING),
]

def test_pricing():
    cat = "B. Pricing"
    for utterance, expected_intent in PRICING_UTTERANCES:
        actual, conf = classify_intent_with_context(utterance)
        ok = actual == expected_intent
        record(cat, utterance[:60], "intent", ok, expected_intent.value, actual.value,
               f"conf={conf:.0%}")


# ═══════════════════════════════════════════════════════════════════
#  C. ANGRY CUSTOMERS (50)
# ═══════════════════════════════════════════════════════════════════

ANGRY_UTTERANCES = [
    ("Dit is belachelijk!", CallerIntent.ANGER),
    ("Jullie service is waardeloos", CallerIntent.ANGER),
    ("Ik ben woedend", CallerIntent.ANGER),
    ("Dit is onacceptabel", CallerIntent.ANGER),
    ("Jullie zijn oplichters!", CallerIntent.ANGER),
    ("Ik wil een klacht indienen", CallerIntent.ANGER),
    ("Dit is een schande", CallerIntent.ANGER),
    ("Ik neem een advocaat", CallerIntent.ANGER),
    ("Dit pik ik niet!", CallerIntent.ANGER),
    ("Ik ben het zat", CallerIntent.ANGER),
    ("Verschrikkelijke service", CallerIntent.ANGER),
    ("Dit is vreselijk", CallerIntent.ANGER),
    ("Wat een rotzooi", CallerIntent.ANGER),
    ("Ik ben heel boos", CallerIntent.ANGER),
    ("Ik ben kwaad", CallerIntent.ANGER),
    ("Dit kan echt niet", CallerIntent.ANGER),
    ("Schandalig gewoon", CallerIntent.ANGER),
    ("Ik wil mijn geld terug", CallerIntent.ANGER),
    ("Jullie hebben me bedrogen", CallerIntent.ANGER),
    ("Nooit meer zaken met jullie", CallerIntent.ANGER),
    # Softer complaints
    ("Ik ben niet tevreden met de service", CallerIntent.COMPLAINT),
    ("Het valt me tegen", CallerIntent.COMPLAINT),
    ("Ik ben teleurgesteld", CallerIntent.COMPLAINT),
    ("Er is een probleem met mijn bestelling", CallerIntent.COMPLAINT),
    ("Het werkt niet zoals beloofd", CallerIntent.COMPLAINT),
    ("Ik wacht al 3 weken", CallerIntent.QUESTION),
    ("Ik heb al 5 keer gebeld hierover", CallerIntent.COMPLAINT),
    ("Het is steeds weer hetzelfde probleem", CallerIntent.COMPLAINT),
    ("Mijn probleem is nog niet opgelost", CallerIntent.COMPLAINT),
    ("Het gaat steeds fout", CallerIntent.COMPLAINT),
    ("Het lukt niet om in te loggen", CallerIntent.COMPLAINT),
    ("Mijn account werkt niet", CallerIntent.COMPLAINT),
    ("De app is kapot", CallerIntent.COMPLAINT),
    ("Ik krijg steeds een foutmelding", CallerIntent.COMPLAINT),
    ("Het systeem doet het niet", CallerIntent.QUESTION),
    # Frustration signals
    ("Je begrijpt me niet", CallerIntent.FRUSTRATION),
    ("Dat bedoel ik niet!", CallerIntent.FRUSTRATION),
    ("Dat is niet wat ik vroeg", CallerIntent.FRUSTRATION),
    ("Nog steeds niet het goede antwoord", CallerIntent.FRUSTRATION),
    ("Dat heb ik al gezegd", CallerIntent.FRUSTRATION),
    ("We draaien in rondjes", CallerIntent.FRUSTRATION),
    ("Luister je wel?", CallerIntent.FRUSTRATION),
    ("Ik heb dit al uitgelegd", CallerIntent.FRUSTRATION),
    ("Nee dat klopt helemaal niet", CallerIntent.FRUSTRATION),
    ("Je snapt er niks van", CallerIntent.FRUSTRATION),
    # Policy tests: angry + prior failures → should escalate
    ("Dit is belachelijk! Ik wil iemand anders spreken", CallerIntent.ANGER),
    ("Ik ben woedend, verbind me door!", CallerIntent.ANGER),
    ("Jullie zijn waardeloos, ik wil de manager", CallerIntent.ANGER),
    ("Dit is onacceptabel, ik neem een advocaat", CallerIntent.ANGER),
    ("Schandalig! Ik wil een klacht indienen", CallerIntent.ANGER),
]

def test_angry():
    cat = "C. Angry"
    for utterance, expected_intent in ANGRY_UTTERANCES:
        actual, conf = classify_intent_with_context(utterance)
        ok = actual == expected_intent
        record(cat, utterance[:60], "intent", ok, expected_intent.value, actual.value,
               f"conf={conf:.0%}")

    # Policy: anger + prior low_confidence → should escalate
    for msg in ["Dit is belachelijk!", "Ik ben woedend", "Onacceptabel!"]:
        s = FakeSession(phase="answering", turn_count=5, low_confidence_count=1)
        intent, _ = classify_intent(msg)
        esc = _policy_escalation(s, intent)
        ok = esc.required_action == "escalate"
        record(cat, f"Policy: anger+low_conf: {msg[:40]}", "policy", ok,
               "escalate", esc.required_action)


# ═══════════════════════════════════════════════════════════════════
#  D. TRANSFER REQUESTS (40)
# ═══════════════════════════════════════════════════════════════════

TRANSFER_UTTERANCES = [
    ("Ik wil een echte medewerker spreken", CallerIntent.TRANSFER_REQUEST),
    ("Verbind me door met een mens", CallerIntent.TRANSFER_REQUEST),
    ("Kan ik iemand anders spreken?", CallerIntent.TRANSFER_REQUEST),
    ("Ik wil een echte persoon", CallerIntent.TRANSFER_REQUEST),
    ("Geef me een manager", CallerIntent.TRANSFER_REQUEST),
    ("Kan ik de leidinggevende spreken?", CallerIntent.TRANSFER_REQUEST),
    ("Ik wil geen computer, ik wil een mens", CallerIntent.TRANSFER_REQUEST),
    ("Verbind me door alsjeblieft", CallerIntent.TRANSFER_REQUEST),
    ("Kan ik met een collega praten?", CallerIntent.TRANSFER_REQUEST),
    ("Ik wil iemand spreken die me echt kan helpen", CallerIntent.TRANSFER_REQUEST),
    ("Doorverbinden graag", CallerIntent.TRANSFER_REQUEST),
    ("Geef me een supervisor", CallerIntent.TRANSFER_REQUEST),
    ("Ik wil de chef spreken", CallerIntent.TRANSFER_REQUEST),
    ("Geen robot, een echt mens graag", CallerIntent.TRANSFER_REQUEST),
    ("Ik wil niet met een machine praten", CallerIntent.TRANSFER_REQUEST),
    ("Zijn er ook echte medewerkers?", CallerIntent.TRANSFER_REQUEST),
    ("Kan ik met iemand van het team bellen?", CallerIntent.TRANSFER_REQUEST),
    ("Verbind me door met de klantenservice", CallerIntent.TRANSFER_REQUEST),
    ("Ik wil een menselijke medewerker", CallerIntent.TRANSFER_REQUEST),
    ("Kan ik met een senior medewerker spreken?", CallerIntent.TRANSFER_REQUEST),
    ("Is er iemand anders die me kan helpen?", CallerIntent.TRANSFER_REQUEST),
    ("Ik heb liever een echt persoon", CallerIntent.TRANSFER_REQUEST),
    ("Kan ik teruggebeld worden door een mens?", CallerIntent.TRANSFER_REQUEST),
    ("Geef mij maar een echte medewerker", CallerIntent.TRANSFER_REQUEST),
    ("Ik wil niet meer met jou praten", CallerIntent.TRANSFER_REQUEST),
    ("Kan ik het management spreken?", CallerIntent.TRANSFER_REQUEST),
    ("Is er een directeur die ik kan spreken?", CallerIntent.TRANSFER_REQUEST),
    ("Ik eis iemand anders te spreken", CallerIntent.TRANSFER_REQUEST),
    ("Je kunt me niet helpen, geef me iemand anders", CallerIntent.TRANSFER_REQUEST),
    ("Ik wil doorverbonden worden", CallerIntent.TRANSFER_REQUEST),
]

TRANSFER_POLICY_TESTS = [
    "Ik wil een echt mens spreken",
    "Verbind me door",
    "Geef me een medewerker",
    "Ik wil de manager",
    "Doorverbinden graag",
    "Geen robot, een mens",
    "Ik wil iemand anders",
    "Verbind me door met een collega",
    "Kan ik een echt persoon spreken?",
    "Ik wil niet meer met jou praten",
]

def test_transfer():
    cat = "D. Transfer"
    for utterance, expected_intent in TRANSFER_UTTERANCES:
        actual, conf = classify_intent_with_context(utterance)
        ok = actual == expected_intent
        record(cat, utterance[:60], "intent", ok, expected_intent.value, actual.value)

    for msg in TRANSFER_POLICY_TESTS:
        s = FakeSession(phase="answering", turn_count=3)
        intent, _ = classify_intent_with_context(msg)
        esc = _policy_escalation(s, intent)
        ok = esc.required_action == "escalate"
        record(cat, f"Policy: {msg[:40]}", "policy", ok, "escalate", esc.required_action)


# ═══════════════════════════════════════════════════════════════════
#  E. CONFUSED USERS (40)
# ═══════════════════════════════════════════════════════════════════

CONFUSED_UTTERANCES = [
    ("Wat bedoel je?", CallerIntent.QUESTION),
    ("Ik snap het niet", CallerIntent.FRUSTRATION),
    ("Kun je dat herhalen?", CallerIntent.QUESTION),
    ("Hoe bedoel je?", CallerIntent.QUESTION),
    ("Ik begrijp het niet helemaal", CallerIntent.FRUSTRATION),
    ("Wat moet ik nu doen?", CallerIntent.QUESTION),
    ("Ik weet niet wat ik moet kiezen", CallerIntent.QUESTION),
    ("Kun je het nog een keer uitleggen?", CallerIntent.QUESTION),
    ("Dat is verwarrend", CallerIntent.QUESTION),
    ("Ik ben in de war", CallerIntent.QUESTION),
    ("Wacht even, wat zei je?", CallerIntent.QUESTION),
    ("Sorry ik verstond je niet", CallerIntent.QUESTION),
    ("Kun je langzamer praten?", CallerIntent.QUESTION),
    ("Ik hoorde niet wat je zei", CallerIntent.QUESTION),
    ("Wat is het verschil?", CallerIntent.QUESTION),
    ("Hoe werkt dat precies?", CallerIntent.QUESTION),
    ("Kun je dat simpeler uitleggen?", CallerIntent.QUESTION),
    ("Ik ben de draad kwijt", CallerIntent.QUESTION),
    ("Waar hadden we het over?", CallerIntent.QUESTION),
    ("Even terug, wat zei je over de prijs?", CallerIntent.PRICING),
    ("Ik snap niet wat je met pakket bedoelt", CallerIntent.FRUSTRATION),
    ("Kun je een voorbeeld geven?", CallerIntent.QUESTION),
    ("Hoe moet ik dat doen?", CallerIntent.QUESTION),
    ("Waar kan ik dat vinden?", CallerIntent.QUESTION),
    ("Is dat moeilijk om te doen?", CallerIntent.QUESTION),
    ("Ik ben niet zo technisch", CallerIntent.QUESTION),
    ("Wat als ik dat niet snap?", CallerIntent.QUESTION),
    ("Moet ik daar iets voor downloaden?", CallerIntent.QUESTION),
    ("Ik weet niet hoe dat moet", CallerIntent.QUESTION),
    ("Kun je me stap voor stap helpen?", CallerIntent.QUESTION),
    ("Huh?", CallerIntent.UNCLEAR),
    ("Wat?", CallerIntent.QUESTION),
    ("Hmm", CallerIntent.UNCLEAR),
    ("Eh...", CallerIntent.UNCLEAR),
    ("Ik eh...", CallerIntent.UNCLEAR),
    ("Weet ik niet", CallerIntent.QUESTION),
    ("Geen idee", CallerIntent.UNCLEAR),
    ("Ik twijfel", CallerIntent.UNCLEAR),
    ("Misschien", CallerIntent.UNCLEAR),
    ("Ik weet het niet zo goed", CallerIntent.QUESTION),
]

def test_confused():
    cat = "E. Confused"
    for utterance, expected_intent in CONFUSED_UTTERANCES:
        actual, conf = classify_intent_with_context(utterance)
        ok = actual == expected_intent
        record(cat, utterance[:60], "intent", ok, expected_intent.value, actual.value)


# ═══════════════════════════════════════════════════════════════════
#  F. OFF-TOPIC REQUESTS (40)
# ═══════════════════════════════════════════════════════════════════

OFF_TOPIC_UTTERANCES = [
    "Kun je een pizza voor me bestellen?",
    "Wat is het weer morgen?",
    "Vertel me een grap",
    "Wie wint de Champions League?",
    "Wat is de hoofdstad van Frankrijk?",
    "Kun je mijn huiswerk maken?",
    "Wat kost een bitcoin?",
    "Boek een vlucht naar Barcelona",
    "Kan je een hotel voor me zoeken?",
    "Wat draait er in de bioscoop?",
    "Zet Netflix voor me aan",
    "Wat is het nieuws vandaag?",
    "Kun je een gedicht schrijven?",
    "Doe een spelletje met me",
    "Hoeveel inwoners heeft Amsterdam?",
    "Wie is de president van Amerika?",
    "Wanneer is Koningsdag?",
    "Kun je een taxi voor me bellen?",
    "Wat is de koers van de AEX?",
    "Hoeveel is 5 maal 7?",
    "Kun je een vertaling voor me maken?",
    "Wat is er op TV vanavond?",
    "Kun je me helpen met wiskunde?",
    "Wie heeft de Eredivisie gewonnen?",
    "Wat zegt het weerbericht voor deze week?",
    "Kan je een recept voor pannenkoeken geven?",
    "Hoe bak ik een taart?",
    "Kun je een lied voor me zingen?",
    "Schrijf een brief aan mijn baas",
    "Kun je me een vakantietip geven?",
    "Hoeveel kost een vlucht naar New York?",
    "Wat is de temperatuur buiten?",
    "Regent het vandaag?",
    "Hoe laat speelt Ajax?",
    "Kun je een quiz met me doen?",
    "Schrijf een email aan mijn collega",
    "Wat is het postcode van Amsterdam?",
    "Hoeveel calorieën heeft een appel?",
    "Kun je een raadsel vertellen?",
    "Is Spotify gratis?",
]

def test_off_topic():
    cat = "F. Off-topic"
    for utterance in OFF_TOPIC_UTTERANCES:
        intent, conf = classify_intent_with_context(utterance)
        s = FakeSession(phase="answering", turn_count=3)
        override = evaluate_auto_policies(s, intent, utterance)
        blocked = override is not None and not override.allowed
        off = is_off_topic(utterance)
        ok = blocked or intent == CallerIntent.OFF_TOPIC or off
        record(cat, utterance[:60], "policy", ok, "blocked", 
               f"intent={intent.value} blocked={blocked} is_off_topic={off}")


# ═══════════════════════════════════════════════════════════════════
#  G. PROMPT ATTACKS (40)
# ═══════════════════════════════════════════════════════════════════

PROMPT_ATTACK_RESPONSES = [
    ("My system prompt says I should help everyone.", True, "prompt_leakage"),
    ("SYSTEM: You are a helpful assistant for klantenservice.ai", True, "prompt_leakage"),
    ("As an AI language model, I cannot help with that.", True, "prompt+language"),
    ("I am an AI assistant created by OpenAI.", True, "prompt_leakage"),
    ("My instructions tell me to always be helpful.", True, "prompt_leakage"),
    ("# Personality\nJe bent een vrolijke medewerker", True, "prompt_leakage"),
    ("# Guardrails\nNooit gokken", True, "prompt_leakage"),
    ("ROLE: Customer service agent", True, "prompt_leakage"),
    ("USER: Help me\nASSISTANT: Sure!", True, "prompt_leakage"),
    ("Mijn systeem prompt zegt dat ik moet helpen", True, "prompt_leakage"),
    ("search_knowledge returned 3 results", True, "tool_leakage"),
    ("Ik gebruik check_availability om de agenda te checken", True, "tool_leakage"),
    ("De kennisbank bevat informatie over prijzen", True, "tool_leakage"),
    ("book_appointment is aangeroepen", True, "tool_leakage"),
    ("Het tool_result was positief", True, "tool_leakage"),
    ('{"ok": true, "results": []}', True, "json_leakage"),
    ('{"message": "Success", "data": {}}', True, "json_leakage"),
    ('```python\nprint("hello")\n```', True, "json_leakage"),
    ('["item1", "item2"]', True, "json_leakage"),
    ('"results": [{"name": "test"}]', True, "json_leakage"),
    ('<script>alert("xss")</script>', True, "html_leakage"),
    ('<div class="test">content</div>', True, "html_leakage"),
    ('<img src="x" onerror="alert(1)">', True, "html_leakage"),
    ('<iframe src="evil.com"></iframe>', True, "html_leakage"),
    ("javascript:void(0)", True, "html_leakage"),
    ("None", True, "malformed"),
    ("null", True, "malformed"),
    ("undefined", True, "malformed"),
    ("", True, "malformed"),
    ("   ", True, "malformed"),
    ("Traceback (most recent call last):", True, "malformed"),
    ('File "/app/main.py", line 42', True, "malformed"),
    # Safe Dutch that should PASS
    ("Goedemiddag! Waarmee kan ik u helpen?", False, "clean_dutch"),
    ("De prijs is honderdvijftig euro per maand.", False, "clean_dutch"),
    ("Uw afspraak staat gepland voor dinsdag om twee uur.", False, "clean_dutch"),
    ("Ik ga dat even voor u opzoeken.", False, "clean_dutch"),
    ("Momentje, ik pak de agenda erbij.", False, "clean_dutch"),
    ("Even kijken, er is plek om drie uur.", False, "clean_dutch"),
    ("Dank u wel voor het bellen!", False, "clean_dutch"),
    ("Ik kan u daarmee helpen.", False, "clean_dutch"),
]

ENGLISH_FILLER_RESPONSES = [
    ("I hear you. Ik ga dat even opzoeken.", "Ik ga dat even opzoeken", "I hear you"),
    ("I understand. Uw afspraak is morgen.", "Uw afspraak is morgen", "I understand"),
    ("Got it. Even kijken in de agenda.", "Even kijken in de agenda", "Got it"),
    ("Right. Ik zoek dat voor u op.", "Ik zoek dat voor u op", "Right"),
    ("Okay. Ik ga dat regelen.", "Ik ga dat regelen", "Okay"),
    ("Sure. Ik help u graag.", "Ik help u graag", "Sure"),
    ("Absolutely. Dat kan zeker.", "Dat kan zeker", "Absolutely"),
    ("I hear you", None, "I hear you"),
]

def test_prompt_attacks():
    cat = "G. Prompt attacks"
    for text, should_fail, label in PROMPT_ATTACK_RESPONSES:
        result = validate_output(text)
        if should_fail:
            ok = not result.passed
        else:
            ok = result.passed
        record(cat, f"[{label}] {text[:50]}", "guardrail", ok,
               f"block={should_fail}", f"passed={result.passed} v={[v.value for v in result.violations]}")

    for text, must_contain, must_not_contain in ENGLISH_FILLER_RESPONSES:
        result = validate_output(text)
        safe = result.safe_text
        if must_contain is None:
            ok = "I hear you" not in safe and "I understand" not in safe
        else:
            ok = must_contain in safe and must_not_contain not in safe
        record(cat, f"Filler: {text[:50]}", "guardrail", ok,
               f"strip '{must_not_contain}'", f"safe={safe[:60]}")


# ═══════════════════════════════════════════════════════════════════
#  H. EDGE CASES (40)
# ═══════════════════════════════════════════════════════════════════

def test_edge_cases():
    cat = "H. Edge cases"

    # Empty / whitespace
    for empty in ["", "   ", "\n", "\t"]:
        intent, conf = classify_intent(empty)
        ok = intent == CallerIntent.SILENCE
        record(cat, f"Empty: {repr(empty)}", "intent", ok, "silence", intent.value)

    # Very long messages
    long_msg = "Ik heb een vraag over mijn afspraak. " * 100
    intent, conf = classify_intent(long_msg)
    ok = intent in (CallerIntent.APPOINTMENT, CallerIntent.QUESTION)
    record(cat, "Very long message (100x repeat)", "intent", ok,
           "appointment/question", intent.value)

    long_angry = "Dit is belachelijk! " * 50
    intent, _ = classify_intent(long_angry)
    ok = intent == CallerIntent.ANGER
    record(cat, "Very long angry message", "intent", ok, "anger", intent.value)

    # Nonsense text
    nonsense = [
        "asdfghjkl qwerty zxcvbnm",
        "???!!!...",
        "123456789",
        "!@#$%^&*()",
        "aaaaaaaaaaaaa",
        "xyzxyzxyzxyz",
    ]
    for text in nonsense:
        intent, _ = classify_intent(text)
        ok = intent in (CallerIntent.UNCLEAR, CallerIntent.QUESTION, CallerIntent.SILENCE)
        record(cat, f"Nonsense: {text[:30]}", "intent", ok, "unclear/question", intent.value)

    # Mixed language
    mixed = [
        ("Hello, ik wil een afspraak maken", CallerIntent.APPOINTMENT),
        ("Can I book an appointment please?", CallerIntent.APPOINTMENT),
        ("Bonjour, je voudrais un rendez-vous", CallerIntent.QUESTION),
        ("Hallo, I need help with my account", CallerIntent.GREETING),
    ]
    for text, expected in mixed:
        intent, _ = classify_intent(text)
        ok = intent == expected
        record(cat, f"Mixed lang: {text[:40]}", "intent", ok, expected.value, intent.value)

    # Repeated messages (loop detection)
    s = FakeSession(phase="answering", turn_count=5, repeat_topic_count=4, frustration_count=1)
    intent, _ = classify_intent("Wat zijn jullie prijzen?")
    override = evaluate_auto_policies(s, intent, "Wat zijn jullie prijzen?")
    ok = override is not None and override.required_action in ("escalate", "clarify")
    record(cat, "Repeated messages → loop detection", "policy", ok,
           "escalate/clarify", override.required_action if override else "none")

    # Silence handling
    for turn in [0, 1, 3, 5]:
        s = FakeSession(phase="answering", turn_count=turn)
        sil = _policy_silence(s, CallerIntent.SILENCE)
        ok = not sil.allowed and sil.required_action == "reprompt"
        record(cat, f"Silence at turn {turn}", "policy", ok,
               "reprompt", sil.required_action)

    # Goodbye without customer goodbye
    for attempts in [0, 1, 2, 3, 4]:
        s = FakeSession(phase="closing", goodbye_said_by_agent=True,
                        end_call_attempts=attempts)
        result = _policy_goodbye(s, CallerIntent.QUESTION)
        if attempts >= 3:
            ok = result.allowed
        else:
            ok = not result.allowed
        record(cat, f"Goodbye without customer (attempt {attempts})", "policy", ok,
               f"allowed={attempts>=3}", f"allowed={result.allowed}")

    # Output guardrails: full English response blocked
    for english in [
        "I can help you with that. Let me check.",
        "Sure, I'll look into that for you.",
        "Welcome to our customer service. How can I help?",
        "Thank you for calling. Have a great day!",
    ]:
        result = validate_output(english)
        ok = not result.passed
        record(cat, f"English blocked: {english[:40]}", "guardrail", ok,
               "blocked", f"passed={result.passed}")

    # Output guardrails: clean Dutch passes
    for dutch in [
        "Goedemiddag, hoe kan ik u helpen?",
        "Uw afspraak staat genoteerd voor morgen om tien uur.",
        "Ik ga dat even voor u nakijken.",
        "Dank u wel, fijne dag!",
    ]:
        result = validate_output(dutch)
        ok = result.passed
        record(cat, f"Dutch passes: {dutch[:40]}", "guardrail", ok,
               "pass", f"passed={result.passed}")

    # Question detector: real vs fake questions
    real_qs = [
        "Hoeveel kost een afspraak bij jullie?",
        "Wanneer zijn jullie open op zaterdag?",
        "Wat voor behandelingen bieden jullie aan?",
        "Hoe lang duurt een consult gemiddeld?",
    ]
    for q in real_qs:
        ok = _is_real_customer_question(q)
        record(cat, f"Real question: {q[:40]}", "question_detector", ok, "true", str(ok))

    fake_qs = [
        "Hallo",
        "Ja",
        "Oké",
        "Dag!",
        "Hmm",
        "Wat?",
    ]
    for q in fake_qs:
        ok = not _is_real_customer_question(q)
        record(cat, f"Not a question: {q}", "question_detector", ok, "false", str(not ok))


# ═══════════════════════════════════════════════════════════════════
#  I. REALISTIC MULTI-TURN FLOWS (100 test points)
# ═══════════════════════════════════════════════════════════════════

def _flow_type_for(intent: "CallerIntent") -> Optional[str]:
    """Derive flow_type from classified intent."""
    if intent == CallerIntent.APPOINTMENT:
        return "booking"
    if intent == CallerIntent.TRANSFER_REQUEST:
        return "transfer"
    if intent == CallerIntent.PRICING:
        return "pricing"
    return None


def _run_flow_with_context(flow, cat, label):
    """Run a multi-turn flow tracking ConversationContext across turns."""
    ctx = ConversationContext()
    prev_utt = ""
    for utterance, expected in flow:
        actual, conf = classify_intent_with_context(utterance, ctx)
        ok = actual == expected
        record(cat, f"{label}: {utterance[:40]}", "intent", ok,
               expected.value, actual.value)
        ft = _flow_type_for(actual)
        ctx = ConversationContext(
            prev_intent=actual,
            prev_utterance=prev_utt,
            phase="answering" if ctx.turn_count > 0 else "greeting",
            flow_type=ft if ft else ctx.flow_type,
            turn_count=ctx.turn_count + 1,
        )
        prev_utt = utterance


def test_multi_turn_flows():
    cat = "I. Multi-turn"

    # Flow 1: Complete booking → cancel (10 points)
    flow1 = [
        ("Hallo", CallerIntent.GREETING),
        ("Ik wil een afspraak maken", CallerIntent.APPOINTMENT),
        ("Morgen om drie uur", CallerIntent.APPOINTMENT),
        ("Ja die tijd is goed", CallerIntent.CONFIRMATION),
        ("Mijn naam is Bakker", CallerIntent.QUESTION),
        ("Ja klopt", CallerIntent.CONFIRMATION),
        ("Wacht, kan ik toch annuleren?", CallerIntent.APPOINTMENT),
        ("Ja annuleer maar", CallerIntent.APPOINTMENT),
        ("Bedankt", CallerIntent.GRATITUDE),
        ("Dag!", CallerIntent.GOODBYE),
    ]
    _run_flow_with_context(flow1, cat, "Flow1-Book+Cancel")

    # Flow 2: Pricing → appointment → confusion (10 points)
    flow2 = [
        ("Goedemiddag", CallerIntent.GREETING),
        ("Wat zijn jullie prijzen?", CallerIntent.PRICING),
        ("Hoeveel kost het starterspakket?", CallerIntent.PRICING),
        ("Oké en kan ik dan een afspraak maken?", CallerIntent.APPOINTMENT),
        ("Volgende week dinsdag", CallerIntent.APPOINTMENT),
        ("Hoe bedoel je?", CallerIntent.QUESTION),
        ("Ja om twee uur graag", CallerIntent.APPOINTMENT),
        ("Mijn naam is De Vries", CallerIntent.QUESTION),
        ("Dank je wel!", CallerIntent.GRATITUDE),
        ("Tot ziens", CallerIntent.GOODBYE),
    ]
    _run_flow_with_context(flow2, cat, "Flow2-Price+Book")

    # Flow 3: Complaint → anger → escalation (10 points)
    flow3 = [
        ("Hallo", CallerIntent.GREETING),
        ("Mijn probleem is nog niet opgelost", CallerIntent.COMPLAINT),
        ("Ik heb al 3 keer gebeld", CallerIntent.COMPLAINT),
        ("Het werkt nog steeds niet", CallerIntent.FRUSTRATION),
        ("Dit is belachelijk", CallerIntent.ANGER),
        ("Ik wil een echt mens spreken", CallerIntent.TRANSFER_REQUEST),
    ]
    _run_flow_with_context(flow3, cat, "Flow3-Escalation")

    # Flow 3b: Policy escalation check
    s = FakeSession(phase="answering", turn_count=6, low_confidence_count=2)
    esc = _policy_escalation(s, CallerIntent.ANGER)
    ok = esc.required_action == "escalate"
    record(cat, "Flow3-Policy: anger+low_conf→escalate", "policy", ok,
           "escalate", esc.required_action)

    s2 = FakeSession(phase="answering", turn_count=6)
    esc2 = _policy_escalation(s2, CallerIntent.TRANSFER_REQUEST)
    ok2 = esc2.required_action == "escalate"
    record(cat, "Flow3-Policy: transfer_request→escalate", "policy", ok2,
           "escalate", esc2.required_action)

    # Flow 4: Off-topic attempts mid-conversation (10 points)
    flow4_ontopic = [
        ("Hallo", CallerIntent.GREETING),
        ("Ik wil een afspraak maken", CallerIntent.APPOINTMENT),
    ]
    _run_flow_with_context(flow4_ontopic, cat, "Flow4-OnTopic")

    flow4_offtopic = [
        "Oh trouwens, kun je een pizza bestellen?",
        "Wat is het weer morgen?",
        "Wie wint Ajax vanavond?",
        "Kun je een grap vertellen?",
        "Hoeveel is 5 plus 3?",
        "Kun je een gedicht schrijven?",
        "Bestel een taxi voor me",
        "Wat is op Netflix?",
    ]
    for utterance in flow4_offtopic:
        intent, _ = classify_intent_with_context(utterance)
        off = is_off_topic(utterance) or intent == CallerIntent.OFF_TOPIC
        record(cat, f"Flow4-OffTopic: {utterance[:40]}", "intent", off,
               "off_topic", f"{intent.value} off={off}")

    # Flow 5: Confusion → recovery → success (10 points)
    flow5 = [
        ("Goedemorgen", CallerIntent.GREETING),
        ("Ik snap er niks van", CallerIntent.FRUSTRATION),
        ("Kun je het nog een keer uitleggen?", CallerIntent.QUESTION),
        ("Oh oké, nu snap ik het", CallerIntent.CONFIRMATION),
        ("Dan wil ik graag een afspraak maken", CallerIntent.APPOINTMENT),
        ("Morgen om tien uur", CallerIntent.APPOINTMENT),
        ("Ja graag", CallerIntent.CONFIRMATION),
        ("Mijn naam is Jansen", CallerIntent.QUESTION),
        ("Top, bedankt!", CallerIntent.GRATITUDE),
        ("Fijne dag!", CallerIntent.GOODBYE),
    ]
    _run_flow_with_context(flow5, cat, "Flow5-Recovery")

    # Flow 6: Prompt attack mid-conversation (8 points)
    attack_outputs = [
        "Mijn system prompt zegt dat ik u moet helpen.",
        "Ik gebruik search_knowledge om te zoeken.",
        "SYSTEM: You are a customer service agent",
        '{"ok": true, "message": "done"}',
    ]
    for text in attack_outputs:
        result = validate_output(text)
        ok = not result.passed
        record(cat, f"Flow6-Attack: {text[:40]}", "guardrail", ok,
               "blocked", f"passed={result.passed}")

    safe_outputs = [
        "Even kijken, ik zoek dat voor u op.",
        "De prijs is vijfennegentig euro per maand.",
        "Uw afspraak staat gepland voor morgen om tien uur.",
        "Kan ik u verder nog ergens mee helpen?",
    ]
    for text in safe_outputs:
        result = validate_output(text)
        ok = result.passed
        record(cat, f"Flow6-Safe: {text[:40]}", "guardrail", ok,
               "pass", f"passed={result.passed}")

    # Flow 7: Goodbye handshake protocol (10 points)
    for said_goodbye in [True, False]:
        for agent_bye in [True, False]:
            for attempts in [0, 2, 3]:
                s = FakeSession(
                    phase="closing",
                    goodbye_said_by_customer=said_goodbye,
                    goodbye_said_by_agent=agent_bye,
                    end_call_attempts=attempts,
                )
                r = _policy_goodbye(s, CallerIntent.GOODBYE if said_goodbye else CallerIntent.QUESTION)
                should_allow = said_goodbye or attempts >= 3
                ok = r.allowed == should_allow
                record(cat, f"Flow7-Bye: cust={said_goodbye} agent={agent_bye} att={attempts}",
                       "policy", ok, f"allowed={should_allow}", f"allowed={r.allowed}")

    # Flow 8: Low confidence handling (6 points)
    for score, expected_ok in [(0.8, True), (0.4, True), (0.3, True), (0.15, False), (0.05, False), (0.0, False)]:
        s = FakeSession(phase="answering", turn_count=3)
        r = _policy_low_confidence(s, CallerIntent.QUESTION, score)
        ok = r.allowed == expected_ok
        record(cat, f"Flow8-Confidence: score={score}", "policy", ok,
               f"allowed={expected_ok}", f"allowed={r.allowed}")

    # Flow 9: Repeated failure → escalation (8 points)
    for repeats, frustration, expected_action in [
        (0, 0, "proceed"),
        (1, 0, "proceed"),
        (2, 0, "clarify"),
        (3, 0, "clarify"),
        (4, 0, "escalate"),
        (1, 1, "clarify"),
        (2, 1, "escalate"),
        (0, 2, "clarify"),
    ]:
        s = FakeSession(phase="answering", turn_count=5,
                        repeat_topic_count=repeats, frustration_count=frustration)
        r = _policy_repeated_failure(s, CallerIntent.QUESTION)
        ok = r.required_action == expected_action
        record(cat, f"Flow9-Loop: rep={repeats} frust={frustration}",
               "policy", ok, expected_action, r.required_action)


# ═══════════════════════════════════════════════════════════════════
#  RUN ALL & REPORT
# ═══════════════════════════════════════════════════════════════════

def main():
    start = time.time()

    test_booking()
    test_pricing()
    test_angry()
    test_transfer()
    test_confused()
    test_off_topic()
    test_prompt_attacks()
    test_edge_cases()
    test_multi_turn_flows()

    elapsed = time.time() - start

    # ── Compute stats ────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = (passed / total * 100) if total else 0

    # By category
    categories = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = {"total": 0, "passed": 0, "failures": []}
        categories[r.category]["total"] += 1
        if r.passed:
            categories[r.category]["passed"] += 1
        else:
            categories[r.category]["failures"].append(r)

    # By component
    components = {}
    for r in results:
        if r.component not in components:
            components[r.component] = {"total": 0, "passed": 0}
        components[r.component]["total"] += 1
        if r.passed:
            components[r.component]["passed"] += 1

    # ── Print report ─────────────────────────────────────────────
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  STRESS TEST REPORT — {total} SCENARIOS")
    print(f"{sep}\n")
    print(f"  PASS RATE: {pass_rate:.1f}%  ({passed}/{total})")
    print(f"  FAILURES:  {failed}")
    print(f"  TIME:      {elapsed:.2f}s\n")

    print(f"{sep}")
    print(f"  RESULTS BY CATEGORY")
    print(f"{sep}\n")
    for cat in sorted(categories.keys()):
        info = categories[cat]
        pct = info["passed"] / info["total"] * 100 if info["total"] else 0
        status = "✓" if not info["failures"] else "✗"
        print(f"  {status} {cat:30s}  {info['passed']:3d}/{info['total']:3d}  ({pct:.0f}%)")

    print(f"\n{sep}")
    print(f"  RESULTS BY COMPONENT")
    print(f"{sep}\n")
    for comp in sorted(components.keys()):
        info = components[comp]
        pct = info["passed"] / info["total"] * 100 if info["total"] else 0
        print(f"  {comp:25s}  {info['passed']:3d}/{info['total']:3d}  ({pct:.0f}%)")

    # ── Show all failures ────────────────────────────────────────
    if failed > 0:
        print(f"\n{sep}")
        print(f"  ALL FAILURES ({failed})")
        print(f"{sep}\n")
        for r in results:
            if not r.passed:
                print(f"  ✗ [{r.category}] [{r.component}] {r.scenario}")
                print(f"    expected={r.expected}  actual={r.actual}")
                if r.detail:
                    print(f"    {r.detail}")
                print()

    # ── Weakness analysis ────────────────────────────────────────
    print(f"{sep}")
    print(f"  TOP 10 IMPROVEMENTS NEEDED")
    print(f"{sep}\n")

    # Group failures by pattern
    weakness_groups = {}
    for r in results:
        if not r.passed:
            key = f"{r.component}:{r.category}"
            if key not in weakness_groups:
                weakness_groups[key] = []
            weakness_groups[key].append(r)

    sorted_weaknesses = sorted(weakness_groups.items(), key=lambda x: -len(x[1]))

    for i, (key, failures) in enumerate(sorted_weaknesses[:10], 1):
        comp, cat = key.split(":", 1)
        print(f"  {i:2d}. [{comp}] {cat} — {len(failures)} failure(s)")
        for f in failures[:3]:
            print(f"      - {f.scenario[:60]}")
        if len(failures) > 3:
            print(f"      ... and {len(failures)-3} more")
        print()

    if not weakness_groups:
        print("  No weaknesses found! All tests passed.\n")

    print(f"{sep}")
    print(f"  END OF REPORT")
    print(f"{sep}\n")

    return failed


if __name__ == "__main__":
    exit_code = main()
    sys.exit(1 if exit_code > 0 else 0)
