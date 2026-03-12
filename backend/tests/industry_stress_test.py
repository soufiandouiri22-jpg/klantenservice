"""
INDUSTRY STRESS TEST — Multi-vertical evaluation of the AI voice agent.

Tests the same 4 subsystems across 5 real-world business verticals:
  1. Hair salon / barber
  2. Dentist / dental clinic
  3. Car garage / mechanic
  4. Restaurant / reservations
  5. SaaS / customer support

Categories per vertical:
  • Booking           • Pricing         • Rescheduling / cancellation
  • Complaints        • Confused users  • Angry users
  • Off-topic         • Transfer        • Ambiguous / vague
  • Multi-turn flows

Run:  cd backend && venv/bin/python tests/industry_stress_test.py
"""
import importlib.util, os, sys, time, re as _re
from dataclasses import dataclass
from typing import Optional

_root = os.path.join(os.path.dirname(__file__), "..")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


intent_mod = _load("intent_classifier",
                    os.path.join(_root, "app/services/voice/intent_classifier.py"))
classify_intent = intent_mod.classify_intent
classify_intent_with_context = intent_mod.classify_intent_with_context
ConversationContext = intent_mod.ConversationContext
CallerIntent = intent_mod.CallerIntent
is_off_topic = intent_mod.is_off_topic

guardrail_mod = _load("output_guardrails",
                       os.path.join(_root, "app/services/voice/output_guardrails.py"))
validate_output = guardrail_mod.validate_output

CI = CallerIntent

# ── Stub policy functions ────────────────────────────────────────

@dataclass
class PolicyResult:
    allowed: bool
    policy_name: str
    required_action: str
    reason_code: str

@dataclass
class FakeSession:
    phase: str = "answering"
    turn_count: int = 2
    goodbye_said_by_customer: bool = False
    goodbye_said_by_agent: bool = False
    end_call_attempts: int = 0
    low_confidence_count: int = 0
    repeat_topic_count: int = 0
    frustration_count: int = 0


def _policy_escalation(session, intent):
    if intent == CI.TRANSFER_REQUEST:
        return PolicyResult(True, "escalation", "escalate", "customer_requested_human")
    if intent == CI.ANGER:
        if (session.low_confidence_count or 0) >= 1 or (session.repeat_topic_count or 0) >= 1:
            return PolicyResult(True, "escalation", "escalate", "anger_plus_failure")
        return PolicyResult(False, "escalation", "clarify", "anger_detected")
    return PolicyResult(False, "escalation", "proceed", "no_escalation_needed")


def _policy_off_topic(session, intent, utterance=""):
    if intent == CI.OFF_TOPIC:
        return PolicyResult(False, "scope_guard", "block", "off_topic_intent")
    if utterance and is_off_topic(utterance):
        return PolicyResult(False, "scope_guard", "block", "off_topic_utterance")
    return PolicyResult(True, "scope_guard", "proceed", "on_topic")


# ── Result tracking ──────────────────────────────────────────────

@dataclass
class TestResult:
    vertical: str
    category: str
    scenario: str
    component: str
    passed: bool
    expected: str
    actual: str
    detail: str = ""

results: list[TestResult] = []


def record(vertical, category, scenario, component, passed, expected, actual, detail=""):
    results.append(TestResult(vertical, category, scenario, component,
                              passed, expected, actual, detail))


def _test_intent(vertical, category, utterance, expected, ctx=None):
    actual, conf = classify_intent_with_context(utterance, ctx)
    ok = actual == expected
    record(vertical, category, utterance[:60], "intent", ok,
           expected.value, actual.value, f"conf={conf:.0%}")


def _test_offtopic_blocked(vertical, utterance):
    intent, _ = classify_intent_with_context(utterance)
    off = is_off_topic(utterance) or intent == CI.OFF_TOPIC
    record(vertical, "Off-topic", utterance[:60], "policy", off,
           "blocked", f"intent={intent.value} off={off}")


def _test_transfer_escalates(vertical, utterance):
    intent, _ = classify_intent_with_context(utterance)
    s = FakeSession(phase="answering", turn_count=3)
    esc = _policy_escalation(s, intent)
    ok = esc.required_action == "escalate"
    record(vertical, "Transfer", utterance[:60], "policy", ok,
           "escalate", esc.required_action)


def _test_guardrail(vertical, text, should_block):
    result = validate_output(text)
    ok = (not result.passed) if should_block else result.passed
    record(vertical, "Guardrail", text[:60], "guardrail", ok,
           f"block={should_block}", f"passed={result.passed}")


_BOOKING_CTX = ConversationContext(
    prev_intent=CI.APPOINTMENT, flow_type="booking", turn_count=3)


def _flow_type_for(intent):
    if intent == CI.APPOINTMENT: return "booking"
    if intent == CI.TRANSFER_REQUEST: return "transfer"
    if intent == CI.PRICING: return "pricing"
    return None


def _test_flow(vertical, label, turns):
    ctx = ConversationContext()
    prev_utt = ""
    for utterance, expected in turns:
        actual, conf = classify_intent_with_context(utterance, ctx)
        ok = actual == expected
        record(vertical, "Multi-turn", f"{label}: {utterance[:40]}", "intent",
               ok, expected.value, actual.value)
        ft = _flow_type_for(actual)
        ctx = ConversationContext(
            prev_intent=actual, prev_utterance=prev_utt,
            phase="answering" if ctx.turn_count > 0 else "greeting",
            flow_type=ft if ft else ctx.flow_type,
            turn_count=ctx.turn_count + 1)
        prev_utt = utterance


# ═══════════════════════════════════════════════════════════════════
#  1. HAIR SALON / BARBER  (~100 scenarios)
# ═══════════════════════════════════════════════════════════════════

def test_hair_salon():
    V = "Hair salon"

    # ── Booking (20) ─────────────────────────────────────────────
    for u, e in [
        ("Ik wil een afspraak maken voor knippen", CI.APPOINTMENT),
        ("Hebben jullie morgen nog plek om 3 uur?", CI.APPOINTMENT),
        ("Kan ik vandaag nog langskomen?", CI.APPOINTMENT),
        ("Is er nog ruimte deze week?", CI.APPOINTMENT),
        ("Ik wil graag een afspraak voor vrijdag", CI.APPOINTMENT),
        ("Kan ik mijn dochter ook inplannen?", CI.APPOINTMENT),
        ("We willen met z'n tweeën komen", CI.APPOINTMENT),
        ("Hebben jullie plek rond het middaguur?", CI.APPOINTMENT),
        ("Kan ik zo snel mogelijk terecht?", CI.APPOINTMENT),
        ("Ik zoek een plek volgende week woensdag", CI.APPOINTMENT),
        ("Boek mij maar in voor zaterdag", CI.APPOINTMENT),
        ("Zijn er vrije plekken op dinsdag?", CI.APPOINTMENT),
        ("Kan ik een afspraak maken voor morgenochtend?", CI.APPOINTMENT),
        ("Graag een afspraak voor aanstaande maandag", CI.APPOINTMENT),
        ("Is er nog iets vrij vanmiddag?", CI.APPOINTMENT),
        ("Ik wil een knipbeurt boeken", CI.APPOINTMENT),
        ("Kan ik ergens deze week terecht?", CI.APPOINTMENT),
        ("Doe mij maar de eerste vrije plek", CI.QUESTION),
        ("Hoe laat kan ik het beste komen?", CI.QUESTION),
        ("Welke dagen zijn jullie open?", CI.QUESTION),
    ]:
        _test_intent(V, "Booking", u, e)

    # ── Pricing (12) ─────────────────────────────────────────────
    for u, e in [
        ("Hoeveel kost een knipbeurt?", CI.PRICING),
        ("Wat zijn jullie prijzen?", CI.PRICING),
        ("Hoeveel kost knippen en föhnen?", CI.PRICING),
        ("Is er verschil in prijs tussen kort en lang haar?", CI.PRICING),
        ("Wat kost een kinderknipmenu?", CI.PRICING),
        ("Hebben jullie een abonnement?", CI.PRICING),
        ("Is er korting voor studenten?", CI.PRICING),
        ("Hoeveel kost verven?", CI.PRICING),
        ("Wat zijn de tarieven voor een herenknipbeurt?", CI.PRICING),
        ("Kan ik met PIN betalen?", CI.PRICING),
        ("Moet ik vooruit betalen?", CI.PRICING),
        ("Hebben jullie een klantenkaart?", CI.QUESTION),
    ]:
        _test_intent(V, "Pricing", u, e)

    # ── Reschedule / cancel (8) ──────────────────────────────────
    for u, e in [
        ("Ik wil mijn afspraak verzetten", CI.APPOINTMENT),
        ("Kan ik mijn afspraak verplaatsen naar donderdag?", CI.APPOINTMENT),
        ("Ik wil annuleren", CI.APPOINTMENT),
        ("Ik kan helaas niet meer komen morgen", CI.APPOINTMENT),
        ("Kan mijn afspraak een uur later?", CI.APPOINTMENT),
        ("Ik wil mijn afspraak annuleren", CI.APPOINTMENT),
        ("Kan ik omboeken naar volgende week?", CI.APPOINTMENT),
        ("Ik kom toch niet, wil je het afzeggen?", CI.APPOINTMENT),
    ]:
        _test_intent(V, "Reschedule", u, e)

    # ── Complaints (8) ───────────────────────────────────────────
    for u, e in [
        ("Mijn haar zit helemaal niet goed na de vorige keer", CI.COMPLAINT),
        ("Ik ben niet tevreden met het resultaat", CI.COMPLAINT),
        ("De kleur is helemaal anders dan afgesproken", CI.COMPLAINT),
        ("Ik heb lang moeten wachten bij mijn laatste bezoek", CI.COMPLAINT),
        ("Er zit een kale plek in mijn kapsel", CI.COMPLAINT),
        ("Het duurde veel te lang", CI.COMPLAINT),
        ("Ik ben echt teleurgesteld", CI.COMPLAINT),
        ("Dit is niet wat ik gevraagd heb", CI.COMPLAINT),
    ]:
        _test_intent(V, "Complaint", u, e)

    # ── Angry (6) ────────────────────────────────────────────────
    for u, e in [
        ("Jullie hebben mijn haar verpest!", CI.ANGER),
        ("Dit is belachelijk, ik wil mijn geld terug", CI.ANGER),
        ("Ik ben woedend over de service", CI.ANGER),
        ("Dit is de slechtste kapper ooit", CI.ANGER),
        ("Schaam je, wat een rommeltje", CI.ANGER),
        ("Ik ga een klacht indienen", CI.ANGER),
    ]:
        _test_intent(V, "Angry", u, e)

    # ── Confused (6) ─────────────────────────────────────────────
    for u, e in [
        ("Ik weet niet precies wat ik wil", CI.QUESTION),
        ("Wat raden jullie aan voor dun haar?", CI.QUESTION),
        ("Wat is het verschil tussen highlights en balayage?", CI.QUESTION),
        ("Hoe bedoel je precies?", CI.QUESTION),
        ("Ik snap het niet helemaal", CI.FRUSTRATION),
        ("Kun je dat nog een keer uitleggen?", CI.QUESTION),
    ]:
        _test_intent(V, "Confused", u, e)

    # ── Transfer (6) ─────────────────────────────────────────────
    for u in [
        "Kan ik de eigenaar spreken?",
        "Ik wil iemand anders spreken",
        "Verbind me door met een medewerker",
        "Geef me een echt persoon",
        "Ik wil niet met een computer praten",
        "Is er iemand anders die mij kan helpen?",
    ]:
        _test_transfer_escalates(V, u)

    # ── Off-topic (6) ────────────────────────────────────────────
    for u in [
        "Kun je een pizza voor me bestellen?",
        "Wat is het weer vandaag?",
        "Hoeveel is 7 keer 8?",
        "Schrijf een gedicht voor me",
        "Waar is de dichtstbijzijnde bioscoop?",
        "Wat is het laatste nieuws?",
    ]:
        _test_offtopic_blocked(V, u)

    # ── Ambiguous / vague (8) ────────────────────────────────────
    for u, e in [
        ("Alleen knippen, geen wassen", CI.QUESTION),
        ("Ik kom 10 minuten later, is dat ok?", CI.QUESTION),
        ("Ik zoek iets rond de middag", CI.APPOINTMENT),
        ("Overdag ergens zou goed zijn", CI.APPOINTMENT),
        ("Wanneer het jullie uitkomt", CI.APPOINTMENT),
        ("Het liefst in de ochtend", CI.APPOINTMENT),
        ("Plan me maar in wanneer het kan", CI.APPOINTMENT),
        ("Maakt niet uit wanneer", CI.APPOINTMENT),
    ]:
        ctx = _BOOKING_CTX if e == CI.APPOINTMENT else None
        _test_intent(V, "Ambiguous", u, e, ctx)

    # ── Multi-turn flows (20) ────────────────────────────────────
    _test_flow(V, "Book+reschedule", [
        ("Hallo", CI.GREETING),
        ("Ik wil een afspraak voor knippen", CI.APPOINTMENT),
        ("Morgen om twee uur", CI.APPOINTMENT),
        ("Ja die tijd is goed", CI.CONFIRMATION),
        ("Wacht, kan het toch vrijdag?", CI.APPOINTMENT),
        ("Ja om drie uur graag", CI.APPOINTMENT),
        ("Mijn naam is Van Dijk", CI.QUESTION),
        ("Bedankt!", CI.GRATITUDE),
        ("Dag!", CI.GOODBYE),
    ])

    _test_flow(V, "Price+book", [
        ("Goedemiddag", CI.GREETING),
        ("Wat kost knippen?", CI.PRICING),
        ("En föhnen erbij?", CI.QUESTION),
        ("Oké, ik wil graag een afspraak", CI.APPOINTMENT),
        ("Volgende week dinsdag", CI.APPOINTMENT),
        ("Ja prima", CI.CONFIRMATION),
        ("Dank je wel", CI.GRATITUDE),
        ("Tot ziens", CI.GOODBYE),
    ])


# ═══════════════════════════════════════════════════════════════════
#  2. DENTIST / DENTAL CLINIC  (~100 scenarios)
# ═══════════════════════════════════════════════════════════════════

def test_dentist():
    V = "Dentist"

    # ── Booking (20) ─────────────────────────────────────────────
    for u, e in [
        ("Ik wil een afspraak maken bij de tandarts", CI.APPOINTMENT),
        ("Kan ik vandaag nog langskomen?", CI.APPOINTMENT),
        ("Ik heb kiespijn sinds vanochtend", CI.COMPLAINT),
        ("Ik wil graag een controle inplannen", CI.APPOINTMENT),
        ("Hebben jullie deze week nog plek?", CI.APPOINTMENT),
        ("Kan ik een spoedafspraak krijgen?", CI.APPOINTMENT),
        ("Ik wil een afspraak voor mijn zoontje", CI.APPOINTMENT),
        ("Wanneer kan ik het snelst terecht?", CI.APPOINTMENT),
        ("Kan ik morgenochtend komen?", CI.APPOINTMENT),
        ("Is er nog plek volgende week?", CI.APPOINTMENT),
        ("Ik wil een afspraak voor een vulling", CI.APPOINTMENT),
        ("Kan ik zo snel mogelijk langskomen?", CI.APPOINTMENT),
        ("Hebben jullie nog ruimte op vrijdag?", CI.APPOINTMENT),
        ("Ik wil me graag inschrijven als nieuwe patiënt", CI.APPOINTMENT),
        ("Ik heb een verwijzing van de huisarts", CI.QUESTION),
        ("Accepteren jullie nieuwe patiënten?", CI.QUESTION),
        ("Hoe lang duurt een controle?", CI.QUESTION),
        ("Moet ik nuchter komen?", CI.QUESTION),
        ("Kan ik mijn hele gezin inplannen?", CI.APPOINTMENT),
        ("Hebben jullie een wachtlijst?", CI.QUESTION),
    ]:
        _test_intent(V, "Booking", u, e)

    # ── Pricing (12) ─────────────────────────────────────────────
    for u, e in [
        ("Wat kost een controle?", CI.PRICING),
        ("Hoeveel kost een vulling?", CI.PRICING),
        ("Worden de kosten vergoed door de verzekering?", CI.PRICING),
        ("Wat zijn jullie tarieven?", CI.PRICING),
        ("Hoeveel kost een kroon?", CI.PRICING),
        ("Wat kost bleken?", CI.PRICING),
        ("Zit tanden bleken in het pakket?", CI.PRICING),
        ("Hoeveel kost een wortelkanaalbehandeling?", CI.PRICING),
        ("Kan ik in termijnen betalen?", CI.PRICING),
        ("Hebben jullie een betalingsregeling?", CI.PRICING),
        ("Wat kost het als ik geen verzekering heb?", CI.PRICING),
        ("Is de eerste controle gratis?", CI.PRICING),
    ]:
        _test_intent(V, "Pricing", u, e)

    # ── Reschedule / cancel (8) ──────────────────────────────────
    for u, e in [
        ("Ik wil mijn afspraak verzetten", CI.APPOINTMENT),
        ("Kan ik een dag later komen?", CI.APPOINTMENT),
        ("Ik kan niet meer dinsdag", CI.APPOINTMENT),
        ("Ik wil mijn afspraak annuleren", CI.APPOINTMENT),
        ("Is het mogelijk om te verplaatsen naar volgende maand?", CI.APPOINTMENT),
        ("Ik moet helaas afzeggen", CI.APPOINTMENT),
        ("Kan mijn controle een week later?", CI.APPOINTMENT),
        ("Ik verzet mijn afspraak liever", CI.APPOINTMENT),
    ]:
        _test_intent(V, "Reschedule", u, e)

    # ── Complaints (8) ───────────────────────────────────────────
    for u, e in [
        ("Ik heb nog steeds pijn na de behandeling", CI.COMPLAINT),
        ("De vulling is er al uit gevallen", CI.COMPLAINT),
        ("Ik moest 40 minuten wachten", CI.COMPLAINT),
        ("De behandeling was erg pijnlijk", CI.COMPLAINT),
        ("Mijn tandvlees bloedt sinds het bezoek", CI.COMPLAINT),
        ("Het probleem is niet opgelost", CI.COMPLAINT),
        ("Ik ben niet tevreden over de behandeling", CI.COMPLAINT),
        ("Het doet meer pijn dan voor de afspraak", CI.COMPLAINT),
    ]:
        _test_intent(V, "Complaint", u, e)

    # ── Angry (6) ────────────────────────────────────────────────
    for u, e in [
        ("Jullie hebben mijn tand beschadigd!", CI.ANGER),
        ("Dit is onacceptabel, ik wil mijn geld terug", CI.ANGER),
        ("Ik ben woedend", CI.ANGER),
        ("Stelletje oplichters!", CI.ANGER),
        ("Verschrikkelijke service", CI.ANGER),
        ("Ik ga een klacht indienen bij de inspectie", CI.ANGER),
    ]:
        _test_intent(V, "Angry", u, e)

    # ── Confused (6) ─────────────────────────────────────────────
    for u, e in [
        ("Ik weet niet of ik naar de tandarts of mondhygiënist moet", CI.QUESTION),
        ("Wat is het verschil tussen een kroon en een brug?", CI.QUESTION),
        ("Hoe bedoel je dat?", CI.QUESTION),
        ("Ik snap niet wat er aan de hand is met mijn tand", CI.FRUSTRATION),
        ("Kun je dat in gewoon Nederlands uitleggen?", CI.QUESTION),
        ("Wat houdt die behandeling precies in?", CI.QUESTION),
    ]:
        _test_intent(V, "Confused", u, e)

    # ── Transfer (6) ─────────────────────────────────────────────
    for u in [
        "Kan ik de tandarts zelf spreken?",
        "Ik wil een medewerker spreken",
        "Verbind me door alsjeblieft",
        "Ik wil iemand anders aan de lijn",
        "Geef me een medewerker",
        "Kan ik de praktijkmanager spreken?",
    ]:
        _test_transfer_escalates(V, u)

    # ── Off-topic (6) ────────────────────────────────────────────
    for u in [
        "Kun je een recept voor appeltaart geven?",
        "Hoeveel calorieën heeft een appel?",
        "Schrijf een brief voor mij",
        "Wat is de postcode van Amsterdam?",
        "Bestel een taxi voor me",
        "Wat is er vanavond op tv?",
    ]:
        _test_offtopic_blocked(V, u)

    # ── Ambiguous / vague (8) ────────────────────────────────────
    for u, e in [
        ("Ergens deze week zou fijn zijn", CI.APPOINTMENT),
        ("Het liefst zo snel mogelijk", CI.APPOINTMENT),
        ("Maakt niet uit welke dag", CI.APPOINTMENT),
        ("Ik weet niet precies wat er mis is", CI.QUESTION),
        ("Er is iets niet goed", CI.QUESTION),
        ("Ik heb ergens last van", CI.QUESTION),
        ("Binnenkort graag", CI.APPOINTMENT),
        ("Overdag past het beste", CI.APPOINTMENT),
    ]:
        ctx = _BOOKING_CTX if e == CI.APPOINTMENT else None
        _test_intent(V, "Ambiguous", u, e, ctx)

    # ── Multi-turn flows (20) ────────────────────────────────────
    _test_flow(V, "Emergency+book", [
        ("Hallo", CI.GREETING),
        ("Ik heb vreselijke kiespijn", CI.COMPLAINT),
        ("Kan ik vandaag nog langskomen?", CI.APPOINTMENT),
        ("Ja graag, zo snel mogelijk", CI.CONFIRMATION),
        ("Mijn naam is Jansen", CI.QUESTION),
        ("Ja dat klopt", CI.CONFIRMATION),
        ("Bedankt!", CI.GRATITUDE),
        ("Dag", CI.GOODBYE),
    ])

    _test_flow(V, "Price+cancel", [
        ("Goedemorgen", CI.GREETING),
        ("Wat kost een controle?", CI.PRICING),
        ("En een gebitsreiniging?", CI.QUESTION),
        ("Hmm, dat is best duur", CI.QUESTION),
        ("Laat maar, ik hoef geen afspraak", CI.DENIAL),
        ("Ja ik weet het zeker", CI.CONFIRMATION),
        ("Tot ziens", CI.GOODBYE),
    ])

    _test_flow(V, "Complaint+escalate", [
        ("Hallo", CI.GREETING),
        ("Ik bel over mijn laatste behandeling", CI.QUESTION),
        ("De vulling is eruit gevallen", CI.COMPLAINT),
        ("Het is al de tweede keer", CI.COMPLAINT),
        ("Ik wil een medewerker spreken", CI.TRANSFER_REQUEST),
    ])


# ═══════════════════════════════════════════════════════════════════
#  3. CAR GARAGE / MECHANIC  (~100 scenarios)
# ═══════════════════════════════════════════════════════════════════

def test_car_garage():
    V = "Car garage"

    # ── Booking (20) ─────────────────────────────────────────────
    for u, e in [
        ("Ik wil een afspraak maken voor een APK keuring", CI.APPOINTMENT),
        ("Kunnen jullie morgen mijn auto nakijken?", CI.APPOINTMENT),
        ("Ik wil een afspraak voor een onderhoudsbeurt", CI.APPOINTMENT),
        ("Kan ik vandaag nog langskomen?", CI.APPOINTMENT),
        ("Mijn auto moet gekeurd worden", CI.QUESTION),
        ("Ik wil een afspraak voor bandenwisselen", CI.APPOINTMENT),
        ("Kan ik deze week nog terecht?", CI.APPOINTMENT),
        ("Hebben jullie morgenochtend plek?", CI.APPOINTMENT),
        ("Ik wil graag een grote beurt inplannen", CI.APPOINTMENT),
        ("Wanneer kan ik het snelst terecht?", CI.APPOINTMENT),
        ("Het motorlampje brandt", CI.QUESTION),
        ("Mijn auto maakt een raar geluid", CI.QUESTION),
        ("De remmen voelen raar aan", CI.QUESTION),
        ("Mijn auto start niet meer", CI.QUESTION),
        ("Er lekt olie onder mijn auto", CI.QUESTION),
        ("Kan ik een leenauto krijgen?", CI.QUESTION),
        ("Hoe lang duurt een kleine beurt?", CI.QUESTION),
        ("Zijn jullie ook op zaterdag open?", CI.QUESTION),
        ("Kan ik mijn auto brengen en ophalen?", CI.QUESTION),
        ("Doen jullie ook schadeherstel?", CI.QUESTION),
    ]:
        _test_intent(V, "Booking", u, e)

    # ── Pricing (12) ─────────────────────────────────────────────
    for u, e in [
        ("Wat kost een APK keuring?", CI.PRICING),
        ("Hoeveel kost een kleine beurt?", CI.PRICING),
        ("Wat zijn de kosten voor een grote beurt?", CI.PRICING),
        ("Wat kost bandenwisselen?", CI.PRICING),
        ("Hoeveel kost een reparatie gemiddeld?", CI.PRICING),
        ("Wat zijn jullie uurtarieven?", CI.PRICING),
        ("Is de diagnose gratis?", CI.PRICING),
        ("Hebben jullie een onderhoudsabonnement?", CI.PRICING),
        ("Wat kost een airco-recharge?", CI.PRICING),
        ("Kan ik in termijnen betalen?", CI.PRICING),
        ("Krijg ik korting als ik meerdere dingen laat doen?", CI.PRICING),
        ("Hoeveel kost een set winterbanden?", CI.PRICING),
    ]:
        _test_intent(V, "Pricing", u, e)

    # ── Reschedule / cancel (8) ──────────────────────────────────
    for u, e in [
        ("Ik wil mijn afspraak verzetten", CI.APPOINTMENT),
        ("Kan mijn beurt een dag later?", CI.APPOINTMENT),
        ("Ik moet mijn afspraak annuleren", CI.APPOINTMENT),
        ("Het komt niet uit morgen", CI.APPOINTMENT),
        ("Kan ik verplaatsen naar volgende week?", CI.APPOINTMENT),
        ("Ik wil mijn APK afspraak verplaatsen", CI.APPOINTMENT),
        ("Ik kan toch niet woensdag", CI.APPOINTMENT),
        ("Kan het ook een andere dag?", CI.APPOINTMENT),
    ]:
        _test_intent(V, "Reschedule", u, e)

    # ── Complaints (8) ───────────────────────────────────────────
    for u, e in [
        ("Het probleem is niet opgelost na de reparatie", CI.COMPLAINT),
        ("Mijn auto doet het nog steeds niet goed", CI.FRUSTRATION),
        ("De rekening was veel hoger dan de offerte", CI.COMPLAINT),
        ("Er zit een kras op mijn auto die er niet zat", CI.COMPLAINT),
        ("Jullie hebben het verkeerde onderdeel besteld", CI.COMPLAINT),
        ("Het duurde drie weken in plaats van twee dagen", CI.COMPLAINT),
        ("Na de beurt maakt hij nog steeds hetzelfde geluid", CI.COMPLAINT),
        ("Ik ben niet tevreden over de service", CI.COMPLAINT),
    ]:
        _test_intent(V, "Complaint", u, e)

    # ── Angry (6) ────────────────────────────────────────────────
    for u, e in [
        ("Jullie hebben mijn auto kapot gemaakt!", CI.COMPLAINT),
        ("Dit is oplichterij!", CI.ANGER),
        ("Ik wil mijn geld terug, nu!", CI.ANGER),
        ("Ongelofelijk slecht werk", CI.ANGER),
        ("Ik ben razend", CI.ANGER),
        ("Stelletje prutsers!", CI.ANGER),
    ]:
        _test_intent(V, "Angry", u, e)

    # ── Confused (6) ─────────────────────────────────────────────
    for u, e in [
        ("Ik weet niet wat er mis is met mijn auto", CI.QUESTION),
        ("Wat is het verschil tussen een kleine en grote beurt?", CI.QUESTION),
        ("Heb ik een APK of een onderhoudsbeurt nodig?", CI.QUESTION),
        ("Ik snap de offerte niet", CI.FRUSTRATION),
        ("Kun je uitleggen wat jullie gaan doen?", CI.QUESTION),
        ("Wat bedoel je met distributieriem?", CI.QUESTION),
    ]:
        _test_intent(V, "Confused", u, e)

    # ── Transfer (6) ─────────────────────────────────────────────
    for u in [
        "Kan ik de monteur spreken?",
        "Ik wil iemand anders spreken hierover",
        "Verbind me door met de werkplaats",
        "Geef me een medewerker",
        "Ik wil een echt persoon aan de lijn",
        "Kan ik de manager spreken?",
    ]:
        _test_transfer_escalates(V, u)

    # ── Off-topic (6) ────────────────────────────────────────────
    for u in [
        "Kun je een pizza bestellen voor me?",
        "Wat is de hoofdstad van Frankrijk?",
        "Schrijf een gedicht over auto's",
        "Hoeveel is 12 maal 15?",
        "Waar kan ik een vakantie boeken?",
        "Vertel een mop",
    ]:
        _test_offtopic_blocked(V, u)

    # ── Ambiguous / vague (8) ────────────────────────────────────
    for u, e in [
        ("Er is iets mis met mijn auto", CI.QUESTION),
        ("Ik denk dat er iets kapot is", CI.QUESTION),
        ("Het maakt een geluid", CI.QUESTION),
        ("Het liefst deze week nog", CI.APPOINTMENT),
        ("Als het kan zo snel mogelijk", CI.APPOINTMENT),
        ("Overdag ergens", CI.APPOINTMENT),
        ("Maakt niet uit wanneer", CI.APPOINTMENT),
        ("Ergens in de ochtend", CI.APPOINTMENT),
    ]:
        ctx = _BOOKING_CTX if e == CI.APPOINTMENT else None
        _test_intent(V, "Ambiguous", u, e, ctx)

    # ── Multi-turn flows (20) ────────────────────────────────────
    _test_flow(V, "Diagnose+book", [
        ("Hallo", CI.GREETING),
        ("Mijn auto maakt een raar geluid", CI.QUESTION),
        ("Bij het remmen voornamelijk", CI.QUESTION),
        ("Kan ik een afspraak maken?", CI.APPOINTMENT),
        ("Morgen als het kan", CI.APPOINTMENT),
        ("Ja om negen uur is prima", CI.CONFIRMATION),
        ("Mijn naam is Bakker", CI.QUESTION),
        ("Bedankt!", CI.GRATITUDE),
        ("Dag!", CI.GOODBYE),
    ])

    _test_flow(V, "Price+decide", [
        ("Goedemiddag", CI.GREETING),
        ("Wat kost een grote beurt?", CI.PRICING),
        ("En een APK erbij?", CI.QUESTION),
        ("Dat is goed, plan me maar in", CI.APPOINTMENT),
        ("Volgende week donderdag", CI.APPOINTMENT),
        ("Ja graag", CI.CONFIRMATION),
        ("Tot ziens", CI.GOODBYE),
    ])


# ═══════════════════════════════════════════════════════════════════
#  4. RESTAURANT / RESERVATIONS  (~100 scenarios)
# ═══════════════════════════════════════════════════════════════════

def test_restaurant():
    V = "Restaurant"

    # ── Booking (20) ─────────────────────────────────────────────
    for u, e in [
        ("Ik wil graag een tafel reserveren", CI.APPOINTMENT),
        ("Hebben jullie vanavond plek voor vier personen?", CI.APPOINTMENT),
        ("Is er nog plek om 20:00?", CI.APPOINTMENT),
        ("Kan ik een reservering maken voor zaterdag?", CI.APPOINTMENT),
        ("We willen graag met z'n zessen komen", CI.APPOINTMENT),
        ("Hebben jullie plek voor morgenavond?", CI.APPOINTMENT),
        ("Ik wil een tafel boeken voor twee", CI.APPOINTMENT),
        ("Kan ik vanavond nog terecht?", CI.APPOINTMENT),
        ("Hebben jullie nog plek om half acht?", CI.APPOINTMENT),
        ("Ik wil reserveren voor aanstaande vrijdag", CI.APPOINTMENT),
        ("Kunnen we buiten zitten?", CI.QUESTION),
        ("Hebben jullie een privéruimte?", CI.QUESTION),
        ("Tot hoe laat kan ik reserveren?", CI.QUESTION),
        ("Is er een kinderstoel beschikbaar?", CI.QUESTION),
        ("Zijn honden welkom?", CI.QUESTION),
        ("Hebben jullie vegetarische opties?", CI.QUESTION),
        ("Is er een dresscode?", CI.QUESTION),
        ("Zijn jullie open op eerste kerstdag?", CI.QUESTION),
        ("Moeten we van tevoren reserveren?", CI.QUESTION),
        ("Hoeveel personen passen er aan een tafel?", CI.QUESTION),
    ]:
        _test_intent(V, "Booking", u, e)

    # ── Pricing (10) ─────────────────────────────────────────────
    for u, e in [
        ("Hebben jullie een menukaart online?", CI.QUESTION),
        ("Wat kost een driegangenmenu?", CI.PRICING),
        ("Hoeveel kost het kindermenu?", CI.PRICING),
        ("Hebben jullie een lunchmenu?", CI.QUESTION),
        ("Wat zijn jullie prijzen?", CI.PRICING),
        ("Is er een dagmenu?", CI.QUESTION),
        ("Hoeveel kost een fles wijn?", CI.PRICING),
        ("Zijn er kosten voor annulering?", CI.PRICING),
        ("Moet ik een aanbetaling doen?", CI.PRICING),
        ("Kan ik met PIN betalen?", CI.PRICING),
    ]:
        _test_intent(V, "Pricing", u, e)

    # ── Reschedule / cancel (8) ──────────────────────────────────
    for u, e in [
        ("Ik wil mijn reservering verplaatsen", CI.APPOINTMENT),
        ("Kan ik omboeken naar zondag?", CI.APPOINTMENT),
        ("Ik wil mijn reservering annuleren", CI.APPOINTMENT),
        ("We komen toch niet vanavond", CI.APPOINTMENT),
        ("Kunnen we een uur later komen?", CI.APPOINTMENT),
        ("Ik wil mijn boeking wijzigen", CI.APPOINTMENT),
        ("We zijn met meer personen, kan dat?", CI.QUESTION),
        ("Ik moet annuleren voor vanavond", CI.APPOINTMENT),
    ]:
        _test_intent(V, "Reschedule", u, e)

    # ── Complaints (8) ───────────────────────────────────────────
    for u, e in [
        ("Het eten was koud toen het geserveerd werd", CI.COMPLAINT),
        ("We moesten een uur wachten op onze bestelling", CI.COMPLAINT),
        ("De bediening was erg onvriendelijk", CI.COMPLAINT),
        ("Er zat een haar in mijn eten", CI.COMPLAINT),
        ("De portie was veel te klein", CI.COMPLAINT),
        ("Het was helemaal niet wat we besteld hadden", CI.COMPLAINT),
        ("De rekening klopte niet", CI.COMPLAINT),
        ("Het was ontzettend lawaaierig", CI.COMPLAINT),
    ]:
        _test_intent(V, "Complaint", u, e)

    # ── Angry (6) ────────────────────────────────────────────────
    for u, e in [
        ("Dit is het slechtste restaurant waar ik ooit ben geweest!", CI.ANGER),
        ("Ik wil mijn geld terug!", CI.ANGER),
        ("Belachelijk, we zijn vergeten!", CI.ANGER),
        ("Schaam jullie!", CI.ANGER),
        ("Ik ben razend over deze ervaring", CI.ANGER),
        ("Oplichters!", CI.ANGER),
    ]:
        _test_intent(V, "Angry", u, e)

    # ── Confused (6) ─────────────────────────────────────────────
    for u, e in [
        ("Ik weet niet hoeveel personen we zijn", CI.QUESTION),
        ("Wat zit er in het dagmenu?", CI.QUESTION),
        ("Ik heb allergieën, kan dat?", CI.QUESTION),
        ("Wat raden jullie aan?", CI.QUESTION),
        ("Ik snap het menu niet helemaal", CI.FRUSTRATION),
        ("Kun je de specials uitleggen?", CI.QUESTION),
    ]:
        _test_intent(V, "Confused", u, e)

    # ── Transfer (6) ─────────────────────────────────────────────
    for u in [
        "Kan ik de chef spreken?",
        "Ik wil de manager spreken",
        "Verbind me met een medewerker",
        "Geef me iemand anders",
        "Ik wil een mens aan de telefoon",
        "Kan ik iemand van het restaurant spreken?",
    ]:
        _test_transfer_escalates(V, u)

    # ── Off-topic (6) ────────────────────────────────────────────
    for u in [
        "Kun je mijn huiswerk maken?",
        "Hoeveel is 100 gedeeld door 7?",
        "Schrijf een essay voor me",
        "Waar is het dichtstbijzijnde ziekenhuis?",
        "Wat is de hoofdstad van Japan?",
        "Vertel me een grap",
    ]:
        _test_offtopic_blocked(V, u)

    # ── Ambiguous / vague (6) ────────────────────────────────────
    for u, e in [
        ("Ergens rond etenstijd", CI.APPOINTMENT),
        ("Het liefst vanavond nog", CI.APPOINTMENT),
        ("Wanneer het kan", CI.APPOINTMENT),
        ("Ik twijfel nog", CI.QUESTION),
        ("Misschien met vier, misschien vijf", CI.QUESTION),
        ("Ik weet het nog niet zeker", CI.QUESTION),
    ]:
        ctx = _BOOKING_CTX if e == CI.APPOINTMENT else None
        _test_intent(V, "Ambiguous", u, e, ctx)

    # ── Multi-turn flows (20) ────────────────────────────────────
    _test_flow(V, "Reserve+change", [
        ("Hallo", CI.GREETING),
        ("Ik wil een tafel reserveren voor vanavond", CI.APPOINTMENT),
        ("Met vier personen", CI.QUESTION),
        ("Om acht uur", CI.APPOINTMENT),
        ("Wacht, maak er maar vijf van", CI.QUESTION),
        ("Ja dat klopt", CI.CONFIRMATION),
        ("Mijn naam is De Boer", CI.QUESTION),
        ("Dankjewel!", CI.GRATITUDE),
        ("Dag!", CI.GOODBYE),
    ])

    _test_flow(V, "Complaint+transfer", [
        ("Goedenavond", CI.GREETING),
        ("Ik bel over mijn bezoek gisteren", CI.QUESTION),
        ("Het eten was verschrikkelijk", CI.COMPLAINT),
        ("Er zat een haar in mijn soep", CI.COMPLAINT),
        ("Ik wil de manager spreken", CI.TRANSFER_REQUEST),
    ])


# ═══════════════════════════════════════════════════════════════════
#  5. SAAS / CUSTOMER SUPPORT  (~100 scenarios)
# ═══════════════════════════════════════════════════════════════════

def test_saas():
    V = "SaaS"

    # ── Booking / demo (12) ──────────────────────────────────────
    for u, e in [
        ("Ik wil een demo inplannen", CI.APPOINTMENT),
        ("Kan ik een afspraak maken voor een demonstratie?", CI.APPOINTMENT),
        ("Wanneer kan ik een demo krijgen?", CI.APPOINTMENT),
        ("Ik wil een gesprek plannen met sales", CI.APPOINTMENT),
        ("Kan ik deze week een demo zien?", CI.APPOINTMENT),
        ("Plan een onboarding-sessie in", CI.APPOINTMENT),
        ("Ik wil een afspraak voor een walkthrough", CI.APPOINTMENT),
        ("Wanneer kan iemand mij bellen?", CI.APPOINTMENT),
        ("Kan ik een call boeken?", CI.APPOINTMENT),
        ("Ik wil graag een kennismakingsgesprek", CI.APPOINTMENT),
        ("Is er een gratis proefperiode?", CI.PRICING),
        ("Kan ik het eerst uitproberen?", CI.QUESTION),
    ]:
        _test_intent(V, "Booking", u, e)

    # ── Pricing (18) ─────────────────────────────────────────────
    for u, e in [
        ("Hoeveel kost jullie abonnement?", CI.PRICING),
        ("Wat zijn jullie prijzen?", CI.PRICING),
        ("Hoeveel kost het starterspakket?", CI.PRICING),
        ("Wat is het verschil tussen de pakketten?", CI.PRICING),
        ("Ik wil mijn plan upgraden", CI.PRICING),
        ("Kan ik downgraden naar een goedkoper pakket?", CI.PRICING),
        ("Kan ik maandelijks opzeggen?", CI.PRICING),
        ("Wat kost een extra gebruiker?", CI.PRICING),
        ("Hebben jullie een jaarabonnement?", CI.PRICING),
        ("Is er korting voor non-profits?", CI.PRICING),
        ("Wat zijn de kosten na de proefperiode?", CI.PRICING),
        ("Hoeveel kost onbeperkt bellen?", CI.PRICING),
        ("Hebben jullie een staffelkorting?", CI.PRICING),
        ("Kan ik een offerte krijgen?", CI.PRICING),
        ("Wat kost de enterprise versie?", CI.PRICING),
        ("Zijn er opstartkosten?", CI.PRICING),
        ("Betaal ik per gebruiker of per bedrijf?", CI.PRICING),
        ("Hebben jullie een gratis versie?", CI.PRICING),
    ]:
        _test_intent(V, "Pricing", u, e)

    # ── Reschedule / cancel (8) ──────────────────────────────────
    for u, e in [
        ("Ik wil mijn abonnement opzeggen", CI.PRICING),
        ("Kan ik mijn demo verzetten?", CI.APPOINTMENT),
        ("Ik wil annuleren", CI.APPOINTMENT),
        ("Hoe zeg ik mijn account op?", CI.PRICING),
        ("Ik wil stoppen met jullie dienst", CI.PRICING),
        ("Kan ik mijn afspraak verplaatsen?", CI.APPOINTMENT),
        ("Ik wil mijn gesprek omboeken", CI.APPOINTMENT),
        ("Ik wil per direct opzeggen", CI.PRICING),
    ]:
        _test_intent(V, "Reschedule", u, e)

    # ── Complaints / technical (10) ──────────────────────────────
    for u, e in [
        ("Het werkt niet, wat moet ik doen?", CI.COMPLAINT),
        ("Ik kan niet inloggen", CI.COMPLAINT),
        ("De app crasht steeds", CI.COMPLAINT),
        ("Mijn data is verdwenen", CI.COMPLAINT),
        ("Het systeem is heel traag", CI.COMPLAINT),
        ("Ik krijg steeds een foutmelding", CI.COMPLAINT),
        ("De integratie werkt niet meer", CI.COMPLAINT),
        ("Mijn factuur klopt niet", CI.COMPLAINT),
        ("Ik word dubbel gefactureerd", CI.COMPLAINT),
        ("De functie die ik nodig heb werkt niet", CI.COMPLAINT),
    ]:
        _test_intent(V, "Complaint", u, e)

    # ── Angry (6) ────────────────────────────────────────────────
    for u, e in [
        ("Dit product is waardeloos!", CI.ANGER),
        ("Ik wil mijn geld terug, nu!", CI.ANGER),
        ("Jullie zijn oplichters", CI.ANGER),
        ("Dit is onacceptabel", CI.ANGER),
        ("Ik ben woedend over jullie service", CI.ANGER),
        ("Verschrikkelijk systeem", CI.ANGER),
    ]:
        _test_intent(V, "Angry", u, e)

    # ── Confused (8) ─────────────────────────────────────────────
    for u, e in [
        ("Ik snap niet hoe het werkt", CI.FRUSTRATION),
        ("Wat is het verschil met jullie concurrent?", CI.QUESTION),
        ("Kun je uitleggen wat AI-klantenservice inhoudt?", CI.QUESTION),
        ("Ik begrijp de factuur niet", CI.FRUSTRATION),
        ("Hoe bedoel je precies?", CI.QUESTION),
        ("Wat moet ik nu doen?", CI.QUESTION),
        ("Ik weet niet welk pakket ik nodig heb", CI.QUESTION),
        ("Kun je dat in simpele woorden uitleggen?", CI.QUESTION),
    ]:
        _test_intent(V, "Confused", u, e)

    # ── Transfer (8) ─────────────────────────────────────────────
    for u in [
        "Verbind me door met een medewerker",
        "Ik wil iemand spreken van de technische dienst",
        "Geef me een medewerker",
        "Ik wil een mens aan de lijn",
        "Kan ik de accountmanager spreken?",
        "Ik wil niet meer met een robot praten",
        "Verbind me met iemand",
        "Is er iemand anders die mij kan helpen?",
    ]:
        _test_transfer_escalates(V, u)

    # ── Off-topic (6) ────────────────────────────────────────────
    for u in [
        "Bestel een pizza voor me",
        "Hoeveel is 50 plus 30?",
        "Schrijf een samenvatting van een boek",
        "Wat is het weer morgen?",
        "Vertel me een mop",
        "Waar kan ik een vakantie boeken?",
    ]:
        _test_offtopic_blocked(V, u)

    # ── Ambiguous / vague (6) ────────────────────────────────────
    for u, e in [
        ("Ik wil meer informatie", CI.QUESTION),
        ("Ergens deze week een demo", CI.APPOINTMENT),
        ("Het werkt gewoon niet", CI.COMPLAINT),
        ("Wanneer kan het?", CI.APPOINTMENT),
        ("Ik twijfel nog", CI.QUESTION),
        ("Kan iemand mij bellen?", CI.APPOINTMENT),
    ]:
        ctx = _BOOKING_CTX if e == CI.APPOINTMENT else None
        _test_intent(V, "Ambiguous", u, e, ctx)

    # ── Multi-turn flows (18) ────────────────────────────────────
    _test_flow(V, "Price+demo", [
        ("Hallo", CI.GREETING),
        ("Ik heb interesse in jullie product", CI.QUESTION),
        ("Hoeveel kost het starterspakket?", CI.PRICING),
        ("En als ik meer gebruikers wil?", CI.QUESTION),
        ("Oké, ik wil een demo plannen", CI.APPOINTMENT),
        ("Volgende week woensdag", CI.APPOINTMENT),
        ("Ja om twee uur", CI.APPOINTMENT),
        ("Top, dank je", CI.GRATITUDE),
        ("Dag!", CI.GOODBYE),
    ])

    _test_flow(V, "Support+escalate", [
        ("Goedemiddag", CI.GREETING),
        ("Ik kan niet inloggen", CI.COMPLAINT),
        ("Ik heb al drie keer geprobeerd", CI.COMPLAINT),
        ("Het werkt echt niet", CI.FRUSTRATION),
        ("Ik wil een medewerker spreken", CI.TRANSFER_REQUEST),
    ])

    _test_flow(V, "Cancel-flow", [
        ("Hallo", CI.GREETING),
        ("Ik wil mijn abonnement opzeggen", CI.PRICING),
        ("Ja ik weet het zeker", CI.CONFIRMATION),
        ("Nee, ik heb geen vragen meer", CI.DENIAL),
        ("Dag", CI.GOODBYE),
    ])


# ═══════════════════════════════════════════════════════════════════
#  6. CROSS-INDUSTRY EDGE CASES (50 scenarios)
# ═══════════════════════════════════════════════════════════════════

def test_cross_industry_edges():
    V = "Cross-industry"

    # ── Vague scheduling (no explicit keyword) ───────────────────
    for u, e in [
        ("Kan ik ergens deze week?", CI.APPOINTMENT),
        ("Zo snel mogelijk graag", CI.APPOINTMENT),
        ("Het liefst morgenochtend", CI.APPOINTMENT),
        ("Als het kan vandaag nog", CI.APPOINTMENT),
        ("Binnenkort zou fijn zijn", CI.APPOINTMENT),
    ]:
        _test_intent(V, "Vague scheduling", u, e, _BOOKING_CTX)

    # ── Indirect transfer language ───────────────────────────────
    for u in [
        "Zijn er ook echte medewerkers?",
        "Ik praat liever met iemand",
        "Kan ik iemand van het team bellen?",
        "Is er een echt persoon beschikbaar?",
        "Ik wil niet meer met jou praten",
    ]:
        _test_transfer_escalates(V, u)

    # ── Users who change their mind ──────────────────────────────
    _test_flow(V, "Change-mind", [
        ("Hallo", CI.GREETING),
        ("Ik wil een afspraak maken", CI.APPOINTMENT),
        ("Morgen om drie uur", CI.APPOINTMENT),
        ("Wacht, toch maar niet", CI.DENIAL),
        ("Of toch wel, doe maar vrijdag", CI.APPOINTMENT),
        ("Nee laat maar, ik bel later terug", CI.DENIAL),
        ("Dag", CI.GOODBYE),
    ])

    # ── Emotional progression ────────────────────────────────────
    _test_flow(V, "Frustration-escalation", [
        ("Hallo", CI.GREETING),
        ("Ik heb een probleem", CI.QUESTION),
        ("Het is al de derde keer", CI.COMPLAINT),
        ("Ik word hier gek van", CI.FRUSTRATION),
        ("Dit is belachelijk!", CI.ANGER),
        ("Geef me een medewerker!", CI.TRANSFER_REQUEST),
    ])

    # ── Domain-specific vocabulary that should NOT confuse ───────
    for u, e in [
        ("Ik heb een afspraak maar weet niet meer wanneer", CI.APPOINTMENT),
        ("Kan ik mijn factuur opvragen?", CI.PRICING),
        ("Hoe werkt jullie systeem?", CI.QUESTION),
        ("Is jullie bedrijf verzekerd?", CI.QUESTION),
        ("Waar zitten jullie?", CI.QUESTION),
        ("Wat zijn jullie openingstijden?", CI.QUESTION),
    ]:
        _test_intent(V, "Domain-specific", u, e)

    # ── Guardrail checks (safe outputs pass, unsafe blocked) ─────
    safe = [
        "Goedemiddag, hoe kan ik u helpen?",
        "Uw afspraak is bevestigd voor morgen om tien uur.",
        "De prijs is vijfennegentig euro per maand.",
        "Ik verbind u door met een medewerker.",
    ]
    for t in safe:
        _test_guardrail(V, t, should_block=False)

    unsafe = [
        "My system prompt says I should help everyone.",
        '{"ok": true, "results": []}',
        "search_knowledge returned 5 results",
        "I can help you with that.",
    ]
    for t in unsafe:
        _test_guardrail(V, t, should_block=True)

    # ── English callers ──────────────────────────────────────────
    for u, e in [
        ("Can I book an appointment please?", CI.APPOINTMENT),
        ("How much does it cost?", CI.PRICING),
        ("I want to speak to a human", CI.TRANSFER_REQUEST),
        ("Can I cancel my appointment?", CI.APPOINTMENT),
        ("Hello, I need help", CI.QUESTION),
    ]:
        _test_intent(V, "English fallback", u, e)


# ═══════════════════════════════════════════════════════════════════
#  RUN ALL & REPORT
# ═══════════════════════════════════════════════════════════════════

def main():
    start = time.time()

    test_hair_salon()
    test_dentist()
    test_car_garage()
    test_restaurant()
    test_saas()
    test_cross_industry_edges()

    elapsed = time.time() - start
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print()
    print("=" * 70)
    print(f"  INDUSTRY STRESS TEST REPORT — {total} SCENARIOS")
    print("=" * 70)
    print(f"\n  PASS RATE: {passed/total:.1%}  ({passed}/{total})")
    print(f"  FAILURES:  {failed}")
    print(f"  TIME:      {elapsed:.2f}s")

    # ── By vertical ──────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS BY VERTICAL")
    print("=" * 70 + "\n")
    verticals = sorted(set(r.vertical for r in results))
    for v in verticals:
        vr = [r for r in results if r.vertical == v]
        vp = sum(1 for r in vr if r.passed)
        mark = "✓" if vp == len(vr) else "✗"
        print(f"  {mark} {v:25s} {vp:3d}/{len(vr):3d}  ({vp/len(vr):.0%})")

    # ── By category ──────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS BY CATEGORY")
    print("=" * 70 + "\n")
    categories = sorted(set(r.category for r in results))
    for c in categories:
        cr = [r for r in results if r.category == c]
        cp = sum(1 for r in cr if r.passed)
        mark = "✓" if cp == len(cr) else "✗"
        print(f"  {mark} {c:25s} {cp:3d}/{len(cr):3d}  ({cp/len(cr):.0%})")

    # ── By component ─────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  RESULTS BY COMPONENT")
    print("=" * 70 + "\n")
    components = sorted(set(r.component for r in results))
    for comp in components:
        cr = [r for r in results if r.component == comp]
        cp = sum(1 for r in cr if r.passed)
        mark = "✓" if cp == len(cr) else "✗"
        print(f"  {mark} {comp:25s} {cp:3d}/{len(cr):3d}  ({cp/len(cr):.0%})")

    # ── All failures ─────────────────────────────────────────────
    failures = [r for r in results if not r.passed]
    if failures:
        print("\n" + "=" * 70)
        print(f"  ALL FAILURES ({len(failures)})")
        print("=" * 70 + "\n")
        for r in failures:
            print(f"  ✗ [{r.vertical}] [{r.category}] [{r.component}] {r.scenario}")
            print(f"    expected={r.expected}  actual={r.actual}  {r.detail}")
            print()

    # ── Failure clusters ─────────────────────────────────────────
    if failures:
        print("=" * 70)
        print("  FAILURE CLUSTERS")
        print("=" * 70 + "\n")

        clusters: dict[str, list] = {
            "Vague scheduling (no keyword)": [],
            "Indirect transfer language": [],
            "Domain-specific vocabulary": [],
            "Multi-turn context loss": [],
            "Implicit complaints": [],
            "Confirmation/denial ambiguity": [],
            "Policy engine gap": [],
            "Other": [],
        }
        for r in failures:
            s = r.scenario.lower()
            if r.component == "policy" and r.category in ("Transfer",):
                clusters["Policy engine gap"].append(r)
            elif r.category in ("Ambiguous", "Vague scheduling"):
                clusters["Vague scheduling (no keyword)"].append(r)
            elif r.category == "Transfer":
                clusters["Indirect transfer language"].append(r)
            elif r.category == "Multi-turn":
                clusters["Multi-turn context loss"].append(r)
            elif r.category in ("Complaint", "Angry"):
                clusters["Implicit complaints"].append(r)
            elif r.expected in ("confirmation", "denial"):
                clusters["Confirmation/denial ambiguity"].append(r)
            elif r.category in ("Booking", "Pricing", "Domain-specific"):
                clusters["Domain-specific vocabulary"].append(r)
            else:
                clusters["Other"].append(r)

        for cluster, items in clusters.items():
            if items:
                print(f"  {cluster} ({len(items)})")
                for r in items[:5]:
                    print(f"    - [{r.vertical}] {r.scenario[:55]}")
                if len(items) > 5:
                    print(f"    ... and {len(items)-5} more")
                print()

    # ── Top 10 improvements ──────────────────────────────────────
    print("=" * 70)
    print("  TOP 10 IMPROVEMENTS FOR CROSS-INDUSTRY PERFORMANCE")
    print("=" * 70 + "\n")

    improvement_areas: dict[str, int] = {}
    for r in failures:
        key = f"[{r.component}] {r.category}"
        improvement_areas[key] = improvement_areas.get(key, 0) + 1
    sorted_areas = sorted(improvement_areas.items(), key=lambda x: -x[1])

    for i, (area, count) in enumerate(sorted_areas[:10], 1):
        examples = [r for r in failures if f"[{r.component}] {r.category}" == area]
        print(f"  {i:2d}. {area} — {count} failure(s)")
        for ex in examples[:3]:
            print(f"      - {ex.scenario[:55]}")
        print()

    print("=" * 70)
    print("  END OF REPORT")
    print("=" * 70)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
