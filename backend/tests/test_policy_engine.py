"""
Controlled end-to-end tests for the policy engine.

Tests cover 5 reliability areas:
1. Off-topic blocking
2. Dutch-only / language guardrails
3. Output guardrails (prompt/tool/JSON/HTML leakage)
4. Low-confidence handling
5. Repeated-failure / loop detection
Plus existing: goodbye handshake, escalation, pricing flow

Run: python3 tests/test_policy_engine.py
"""
import importlib.util
import os
import sys
from uuid import uuid4
from datetime import datetime
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from enum import Enum

_root = os.path.join(os.path.dirname(__file__), "..")

# ── Direct-load modules without importing the full app ─────────────

def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

# 1. Intent classifier
intent_mod = _load(
    "intent_classifier",
    os.path.join(_root, "app/services/voice/intent_classifier.py"),
)
classify_intent = intent_mod.classify_intent
CallerIntent = intent_mod.CallerIntent
is_off_topic = intent_mod.is_off_topic

# 2. Output guardrails (no external deps)
guardrails_mod = _load(
    "output_guardrails",
    os.path.join(_root, "app/services/voice/output_guardrails.py"),
)
validate_output = guardrails_mod.validate_output
ViolationType = guardrails_mod.ViolationType


# ── Stubs ─────────────────────────────────────────────────────────

@dataclass
class FakeSession:
    id: str = ""
    call_sid: str = ""
    call_log_id: str = ""
    company_id: str = ""
    phase: str = "greeting"
    turn_count: int = 0
    last_customer_intent: str = None
    last_customer_utterance: str = None
    goodbye_said_by_agent: bool = False
    goodbye_said_by_customer: bool = False
    escalation_requested: bool = False
    transfer_executed: bool = False
    low_confidence_count: int = 0
    repeat_topic_count: int = 0
    frustration_count: int = 0
    off_topic_block_count: int = 0
    output_guardrail_block_count: int = 0
    language_violation_count: int = 0
    retrieval_count: int = 0
    retrieval_skip_count: int = 0
    end_call_attempts: int = 0
    goodbye_handshake_ok: bool = None
    hangup_reason: str = None
    ended_by: str = None
    last_retrieval_score: float = None


@dataclass
class PolicyResult:
    allowed: bool
    policy_name: str
    required_action: str
    reason_code: str
    instruction_nl: str = ""
    phase_after: str = ""

    def to_dict(self):
        return {
            "allowed": self.allowed,
            "policy_name": self.policy_name,
            "required_action": self.required_action,
            "reason_code": self.reason_code,
            "instruction_nl": self.instruction_nl,
        }


# ── Policy functions (copied for isolated testing) ────────────────

def policy_goodbye_handshake(session, intent):
    customer_goodbye = session.goodbye_said_by_customer or intent == CallerIntent.GOODBYE
    if customer_goodbye:
        return PolicyResult(True, "goodbye_handshake", "proceed",
                            "customer_said_goodbye",
                            "De klant heeft afscheid genomen.",
                            "ended")
    attempts = (session.end_call_attempts or 0) + 1
    if attempts >= 3:
        return PolicyResult(True, "goodbye_handshake", "proceed",
                            "max_attempts_reached",
                            "Max attempts reached.",
                            "ended")
    if session.goodbye_said_by_agent:
        return PolicyResult(False, "goodbye_handshake", "wait",
                            "customer_not_goodbye",
                            "Wacht tot de klant reageert.",
                            "waiting_goodbye")
    return PolicyResult(False, "goodbye_handshake", "wait",
                        "agent_not_goodbye",
                        "Neem eerst afscheid.",
                        "closing")


def policy_escalation(session, intent):
    if intent == CallerIntent.TRANSFER_REQUEST:
        return PolicyResult(True, "escalation", "escalate",
                            "customer_requested_human",
                            "De klant wil een medewerker.",
                            "escalating")
    if intent == CallerIntent.ANGER:
        low_conf = (session.low_confidence_count or 0) >= 1
        repeat = (session.repeat_topic_count or 0) >= 1
        if low_conf or repeat:
            return PolicyResult(True, "escalation", "escalate",
                                "anger_plus_failure",
                                "Gefrustreerd + eerdere mislukkingen.",
                                "escalating")
        return PolicyResult(False, "escalation", "clarify",
                            "anger_detected",
                            "Toon begrip.")
    if (session.low_confidence_count or 0) >= 3:
        return PolicyResult(True, "escalation", "escalate",
                            "repeated_low_confidence",
                            "Meerdere keren geen antwoord.",
                            "escalating")
    return PolicyResult(False, "escalation", "proceed", "no_escalation_needed")


_OFF_TOPIC_RESPONSE = (
    "Daar kan ik u niet mee helpen. Ik kan alleen helpen met vragen "
    "over ons bedrijf, onze diensten en onze klantenservice."
)

def policy_off_topic(session, intent, utterance=""):
    if intent == CallerIntent.OFF_TOPIC:
        return PolicyResult(False, "scope_guard", "block", "off_topic_intent",
                            _OFF_TOPIC_RESPONSE)
    if utterance and is_off_topic(utterance):
        return PolicyResult(False, "scope_guard", "block", "off_topic_utterance",
                            _OFF_TOPIC_RESPONSE)
    return PolicyResult(True, "scope_guard", "proceed", "on_topic")


def policy_low_confidence(session, intent, retrieval_confidence):
    if retrieval_confidence >= 0.4:
        return PolicyResult(True, "low_confidence", "proceed", "confidence_ok")
    if retrieval_confidence >= 0.2:
        return PolicyResult(True, "low_confidence", "proceed", "confidence_marginal",
                            "Je bent niet helemaal zeker.")
    return PolicyResult(False, "low_confidence", "clarify", "confidence_too_low",
                        "VERZIN NIETS. Zeg eerlijk dat je het antwoord niet hebt.")


def policy_repeated_failure(session, intent):
    repeats = session.repeat_topic_count or 0
    frustration = session.frustration_count or 0
    effective = repeats + frustration

    if intent == CallerIntent.FRUSTRATION:
        if effective >= 2:
            return PolicyResult(True, "repeated_failure", "escalate",
                                "frustration_plus_repeats",
                                "Klant gefrustreerd + herhaald probleem.",
                                "escalating")
        return PolicyResult(False, "repeated_failure", "clarify",
                            "frustration_detected",
                            "Vraag specifiek wat de klant wil weten.")

    if effective < 2:
        return PolicyResult(True, "repeated_failure", "proceed", "within_threshold")
    if effective < 4:
        return PolicyResult(False, "repeated_failure", "clarify", "topic_repeated",
                            "Probeer anders te benaderen.")
    return PolicyResult(True, "repeated_failure", "escalate", "topic_loop_detected",
                        "Bied collega terugbellen aan.", "escalating")


def policy_silence(session, intent):
    if intent != CallerIntent.SILENCE:
        return PolicyResult(True, "silence_handler", "proceed", "not_silent")
    turn = session.turn_count or 0
    if turn <= 1:
        return PolicyResult(False, "silence_handler", "reprompt",
                            "initial_silence",
                            "Hallo, bent u daar?")
    return PolicyResult(False, "silence_handler", "reprompt",
                        "mid_call_silence",
                        "Ik hoorde u even niet.")


def evaluate_auto_policies(session, intent, utterance="", retrieval_confidence=1.0):
    esc = policy_escalation(session, intent)
    if esc.required_action == "escalate":
        return esc
    ot = policy_off_topic(session, intent, utterance)
    if not ot.allowed:
        return ot
    sil = policy_silence(session, intent)
    if not sil.allowed:
        return sil
    rf = policy_repeated_failure(session, intent)
    if not rf.allowed or rf.required_action == "escalate":
        return rf
    lc = policy_low_confidence(session, intent, retrieval_confidence)
    if not lc.allowed:
        return lc
    return None


import re
_FRUSTRATION_RE = re.compile(
    r"\b("
    r"(?:dat\s+)?bedoel\s+ik\s+niet|dat\s+is\s+niet\s+wat\s+ik|"
    r"je\s+begrijpt\s+(?:me|mij)\s+niet|nog\s+steeds\s+niet|"
    r"dat\s+heb\s+ik\s+al|luister\s+(?:je|u)\s+(?:wel|eigenlijk)|"
    r"dat\s+zei\s+ik|dat\s+(?:klopt|helpt)\s+(?:niet|helemaal\s+niet)|"
    r"we\s+draaien\s+in\s+(?:rondjes|cirkels)"
    r")\b",
    re.I,
)


def update_state(session, intent, tool_name, utterance=""):
    prev_intent = session.last_customer_intent
    session.turn_count = (session.turn_count or 0) + 1
    session.last_customer_intent = intent.value
    session.last_customer_utterance = utterance

    if intent == CallerIntent.GOODBYE:
        session.goodbye_said_by_customer = True
    if intent in (CallerIntent.ANGER, CallerIntent.TRANSFER_REQUEST):
        session.escalation_requested = True
    if tool_name == "search_knowledge":
        session.retrieval_count = (session.retrieval_count or 0) + 1

    # Frustration tracking
    if intent == CallerIntent.FRUSTRATION:
        session.frustration_count = (session.frustration_count or 0) + 1
        session.repeat_topic_count = (session.repeat_topic_count or 0) + 1
    elif utterance and _FRUSTRATION_RE.search(utterance):
        session.frustration_count = (session.frustration_count or 0) + 1
        session.repeat_topic_count = (session.repeat_topic_count or 0) + 1

    # Same-topic repetition
    if (
        prev_intent
        and intent.value == prev_intent
        and intent in (CallerIntent.QUESTION, CallerIntent.PRICING)
        and tool_name in ("search_knowledge", "get_prices")
    ):
        session.repeat_topic_count = (session.repeat_topic_count or 0) + 1

    # Phase transitions
    current = session.phase
    if current == "greeting":
        if intent in (CallerIntent.QUESTION, CallerIntent.PRICING,
                       CallerIntent.APPOINTMENT, CallerIntent.COMPLAINT):
            session.phase = "discovery"
        elif intent == CallerIntent.GOODBYE:
            session.phase = "closing"
    elif current == "discovery":
        if tool_name == "search_knowledge":
            session.phase = "answering"
        elif intent == CallerIntent.GOODBYE:
            session.phase = "closing"
    elif current in ("answering", "clarifying"):
        if intent == CallerIntent.GOODBYE:
            session.phase = "closing"
    elif current == "closing":
        if intent == CallerIntent.GOODBYE:
            session.goodbye_said_by_customer = True

    if intent in (CallerIntent.ANGER, CallerIntent.TRANSFER_REQUEST):
        if current not in ("ended", "escalating"):
            session.phase = "escalating"
    if intent == CallerIntent.FRUSTRATION:
        if current in ("answering", "discovery"):
            session.phase = "clarifying"


# ── Helpers ────────────────────────────────────────────────────────

def print_divider(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def print_intent(utterance, intent, confidence):
    print(f"  Utterance: \"{utterance}\"")
    print(f"  Intent:    {intent.value} ({confidence:.0%})")

def print_state(s):
    print(f"  Phase:          {s.phase}")
    print(f"  Turn:           {s.turn_count}")
    print(f"  Frustration:    {s.frustration_count}")
    print(f"  Repeat topic:   {s.repeat_topic_count}")
    print(f"  Low conf:       {s.low_confidence_count}")

def print_policy(r):
    print(f"  Policy:         {r.policy_name}")
    print(f"  Allowed:        {r.allowed}")
    print(f"  Action:         {r.required_action}")
    print(f"  Reason:         {r.reason_code}")
    if r.instruction_nl:
        print(f"  Instruction:    {r.instruction_nl[:80]}{'...' if len(r.instruction_nl) > 80 else ''}")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 1: Goodbye Denied
# ══════════════════════════════════════════════════════════════════

def test_goodbye_denied():
    print_divider("SCENARIO 1: Goodbye Denied")
    s = FakeSession(phase="answering", turn_count=5, goodbye_said_by_agent=True)
    msg = "Wacht, ik heb nog een vraag"
    intent, conf = classify_intent(msg)
    print_intent(msg, intent, conf)
    result = policy_goodbye_handshake(s, intent)
    print_policy(result)
    assert not result.allowed
    assert result.required_action == "wait"
    print("  ✓ PASS: end_call DENIED")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 2: Goodbye Allowed
# ══════════════════════════════════════════════════════════════════

def test_goodbye_allowed():
    print_divider("SCENARIO 2: Goodbye Allowed")
    s = FakeSession(phase="closing", turn_count=8, goodbye_said_by_agent=True)
    msg = "Doei!"
    intent, conf = classify_intent(msg)
    assert intent == CallerIntent.GOODBYE
    result = policy_goodbye_handshake(s, intent)
    assert result.allowed
    assert result.reason_code == "customer_said_goodbye"
    print("  ✓ PASS: end_call ALLOWED")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 3: Pricing Question
# ══════════════════════════════════════════════════════════════════

def test_pricing_question():
    print_divider("SCENARIO 3: Pricing Question")
    s = FakeSession(phase="greeting", turn_count=1)
    msg = "Wat zijn jullie prijzen?"
    intent, conf = classify_intent(msg)
    assert intent == CallerIntent.PRICING
    override = evaluate_auto_policies(s, intent)
    assert override is None
    print("  ✓ PASS: pricing flows through")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 4: Anger + Escalation
# ══════════════════════════════════════════════════════════════════

def test_anger_escalation():
    print_divider("SCENARIO 4: Anger + Escalation")
    s = FakeSession(phase="answering", turn_count=6,
                    low_confidence_count=2, repeat_topic_count=1)
    msg = "Dit is belachelijk! Ik wil iemand anders spreken!"
    intent, conf = classify_intent(msg)
    update_state(s, intent, "search_knowledge", msg)
    override = evaluate_auto_policies(s, intent, msg)
    assert override is not None
    assert override.required_action == "escalate"
    print("  ✓ PASS: anger triggers escalation")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 5: Off-Topic (5 required cases)
# ══════════════════════════════════════════════════════════════════

def test_off_topic():
    print_divider("SCENARIO 5: Off-Topic (5 cases)")
    cases = [
        "Kun je een pizza voor me bestellen?",
        "Wat is de hoofdstad van Frankrijk?",
        "Kun je het weer voor morgen zeggen?",
        "Kan je mij helpen met mijn huiswerk?",
        "Vertel een mop",
    ]
    all_pass = True
    for msg in cases:
        s = FakeSession(phase="answering", turn_count=3)
        intent, conf = classify_intent(msg)
        override = evaluate_auto_policies(s, intent, msg)
        blocked = (override is not None and not override.allowed
                   and override.policy_name == "scope_guard")
        status = "✓" if blocked else "✗"
        if not blocked:
            all_pass = False
        print(f"  {status} \"{msg}\" → {intent.value} ({conf:.0%})")

    assert all_pass, "Not all off-topic cases blocked"
    print("  ✓ ALL 5 off-topic cases BLOCKED")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 6: Output Guardrails — Language Violations
# ══════════════════════════════════════════════════════════════════

def test_output_guardrails_language():
    print_divider("SCENARIO 6: Output Guardrails — Language")
    cases = [
        ("Goedemiddag, waarmee kan ik u helpen?", True, "Dutch OK"),
        ("Good afternoon, how can I help you today?", False, "English detected"),
        ("I hear you, that sounds like a problem.", False, "English sentence"),
        ("De prijs is honderdvijftig euro per maand.", True, "Dutch pricing OK"),
        ("Uw afspraak is ingepland voor morgen.", True, "Dutch confirmation OK"),
    ]
    all_pass = True
    for text, should_pass, label in cases:
        result = validate_output(text)
        ok = result.passed == should_pass
        status = "✓" if ok else "✗"
        if not ok:
            all_pass = False
        print(f"  {status} [{label}] passed={result.passed} (expected={should_pass})")
        if not ok:
            print(f"      violations={[v.value for v in result.violations]}")

    assert all_pass, "Language guardrail tests failed"
    print("  ✓ ALL language tests PASSED")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 7: Output Guardrails — Prompt/Tool/JSON Leakage
# ══════════════════════════════════════════════════════════════════

def test_output_guardrails_leakage():
    print_divider("SCENARIO 7: Output Guardrails — Leakage Detection")
    cases = [
        # (text, should_pass, expected_violation_type, label)
        ("Ik ben uw klantenservice medewerker.", True, None, "Normal Dutch"),
        ("As an AI language model, I cannot help with that.", False,
         ViolationType.LANGUAGE_VIOLATION, "AI identity + English"),
        ('{"ok": true, "results": []}', False,
         ViolationType.JSON_LEAKAGE, "JSON object"),
        ("search_knowledge returned 3 results from kennisbank", False,
         ViolationType.TOOL_LEAKAGE, "Tool name leakage"),
        ("```python\nprint('hello')\n```", False,
         ViolationType.JSON_LEAKAGE, "Code fence"),
        ("<script>alert('xss')</script>", False,
         ViolationType.HTML_OR_SCRIPT, "Script tag"),
        ("SYSTEM: You are a helpful assistant", False,
         ViolationType.PROMPT_LEAKAGE, "System prompt leakage"),
        ("", False, ViolationType.MALFORMED_OUTPUT, "Empty output"),
        ("   ", False, ViolationType.MALFORMED_OUTPUT, "Whitespace only"),
        ("None", False, ViolationType.MALFORMED_OUTPUT, "None string"),
    ]
    all_pass = True
    for text, should_pass, expected_vtype, label in cases:
        result = validate_output(text)
        ok = result.passed == should_pass
        if not ok:
            all_pass = False
        if expected_vtype and not result.passed:
            has_expected = expected_vtype in result.violations
            if not has_expected:
                ok = False
                all_pass = False

        status = "✓" if ok else "✗"
        vtypes = [v.value for v in result.violations] if result.violations else []
        print(f"  {status} [{label}] passed={result.passed} violations={vtypes}")

    assert all_pass, "Leakage guardrail tests failed"
    print("  ✓ ALL leakage tests PASSED")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 8: Low-Confidence Handling
# ══════════════════════════════════════════════════════════════════

def test_low_confidence():
    print_divider("SCENARIO 8: Low-Confidence Handling")

    cases = [
        (0.6, True, "confidence_ok", "High confidence — proceed normally"),
        (0.3, True, "confidence_marginal", "Marginal confidence — proceed with caution"),
        (0.1, False, "confidence_too_low", "Low confidence — block + clarify"),
        (0.0, False, "confidence_too_low", "Zero confidence — block + clarify"),
    ]

    all_pass = True
    for score, should_allow, expected_code, label in cases:
        s = FakeSession(phase="answering", turn_count=3)
        intent = CallerIntent.QUESTION
        result = policy_low_confidence(s, intent, score)
        ok = (result.allowed == should_allow and result.reason_code == expected_code)
        if not ok:
            all_pass = False
        status = "✓" if ok else "✗"
        print(f"  {status} [{label}] score={score} allowed={result.allowed} code={result.reason_code}")

    # Test via auto-policies
    s2 = FakeSession(phase="answering", turn_count=4)
    override = evaluate_auto_policies(s2, CallerIntent.QUESTION, "", retrieval_confidence=0.05)
    assert override is not None and not override.allowed
    print(f"  ✓ Auto-policy catches low confidence (score=0.05)")

    assert all_pass, "Low confidence tests failed"
    print("  ✓ ALL low-confidence tests PASSED")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 9: Repeated Failure / Loop Detection
# ══════════════════════════════════════════════════════════════════

def test_repeated_failure():
    print_divider("SCENARIO 9: Repeated Failure / Loop Detection")

    # Case 1: Customer repeats pricing 3 times
    print("\n  Case 1: Customer repeats pricing 3 times")
    s = FakeSession(phase="answering", turn_count=3)
    for i in range(3):
        update_state(s, CallerIntent.PRICING, "search_knowledge", "Wat zijn jullie prijzen?")
    print(f"    repeat_topic_count={s.repeat_topic_count}")
    result = policy_repeated_failure(s, CallerIntent.PRICING)
    assert not result.allowed or result.required_action == "escalate"
    print(f"    ✓ Policy triggers: {result.required_action} ({result.reason_code})")

    # Case 2: Customer says "nee dat bedoel ik niet"
    print("\n  Case 2: Frustration signal — 'dat bedoel ik niet'")
    s2 = FakeSession(phase="answering", turn_count=3)
    msg = "Nee dat bedoel ik niet"
    intent, conf = classify_intent(msg)
    print(f"    Intent: {intent.value} ({conf:.0%})")
    update_state(s2, intent, "search_knowledge", msg)
    print(f"    frustration_count={s2.frustration_count}, repeat_topic_count={s2.repeat_topic_count}")
    result2 = policy_repeated_failure(s2, intent)
    assert result2.reason_code in ("frustration_detected", "frustration_plus_repeats")
    print(f"    ✓ Frustration detected: {result2.reason_code}")

    # Case 3: Customer repeats then expresses frustration → escalate
    print("\n  Case 3: Repeat + frustration → escalation")
    s3 = FakeSession(phase="answering", turn_count=3)
    update_state(s3, CallerIntent.PRICING, "search_knowledge", "Wat zijn jullie prijzen?")
    update_state(s3, CallerIntent.PRICING, "search_knowledge", "Wat zijn jullie prijzen?")
    update_state(s3, CallerIntent.FRUSTRATION, "search_knowledge", "Je begrijpt me niet!")
    print(f"    repeat_topic_count={s3.repeat_topic_count}, frustration_count={s3.frustration_count}")
    result3 = policy_repeated_failure(s3, CallerIntent.FRUSTRATION)
    assert result3.required_action == "escalate"
    print(f"    ✓ Escalation triggered: {result3.reason_code}")

    # Case 4: "je begrijpt me niet" detected as frustration
    print("\n  Case 4: 'je begrijpt me niet' classified as frustration")
    msg4 = "Je begrijpt me niet"
    intent4, conf4 = classify_intent(msg4)
    assert intent4 == CallerIntent.FRUSTRATION, f"Expected FRUSTRATION, got {intent4.value}"
    print(f"    ✓ Intent: {intent4.value} ({conf4:.0%})")

    # Case 5: "nog steeds niet" detected as frustration
    print("\n  Case 5: 'nog steeds niet' classified as frustration")
    msg5 = "Nog steeds niet het goede antwoord"
    intent5, conf5 = classify_intent(msg5)
    assert intent5 == CallerIntent.FRUSTRATION, f"Expected FRUSTRATION, got {intent5.value}"
    print(f"    ✓ Intent: {intent5.value} ({conf5:.0%})")

    # Case 6: Loop detection via auto-policies
    print("\n  Case 6: Loop detection triggers escalation via auto-policy")
    s4 = FakeSession(phase="answering", turn_count=8, repeat_topic_count=3, frustration_count=2)
    override = evaluate_auto_policies(s4, CallerIntent.PRICING, "Wat zijn de prijzen?")
    assert override is not None
    assert override.required_action in ("escalate", "clarify")
    print(f"    ✓ Auto-policy override: {override.required_action} ({override.reason_code})")

    print("\n  ✓ ALL repeated-failure tests PASSED")


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 10: English Filler Stripping
# ══════════════════════════════════════════════════════════════════

def test_english_filler_stripping():
    print_divider("SCENARIO 10: English Filler Stripping")

    cases = [
        # (input, expected_safe_text_contains, expected_safe_text_not_contains, label)
        (
            "I hear you. Ik ga dat even voor u opzoeken.",
            "Ik ga dat even voor u opzoeken",
            "I hear you",
            "Strips 'I hear you' prefix",
        ),
        (
            "I understand. Uw afspraak is morgen om 10 uur.",
            "Uw afspraak is morgen om 10 uur",
            "I understand",
            "Strips 'I understand' prefix",
        ),
        (
            "Got it. Even kijken in de agenda.",
            "Even kijken in de agenda",
            "Got it",
            "Strips 'Got it' prefix",
        ),
        (
            "Right. Ik zoek dat voor u op.",
            "Ik zoek dat voor u op",
            "Right",
            "Strips 'Right' prefix",
        ),
        (
            "Okay. Ik ga dat regelen.",
            "Ik ga dat regelen",
            "Okay",
            "Strips 'Okay' prefix",
        ),
        (
            "Goedemiddag, waarmee kan ik u helpen?",
            "Goedemiddag, waarmee kan ik u helpen?",
            None,
            "Clean Dutch unchanged",
        ),
        (
            "Top, even kijken in de agenda!",
            "Top, even kijken in de agenda!",
            None,
            "Dutch fillers pass through",
        ),
        (
            "I hear you",
            "Even kijken...",
            None,
            "Filler-only input replaced with Dutch fallback",
        ),
    ]

    all_pass = True
    for text, must_contain, must_not_contain, label in cases:
        result = validate_output(text)
        safe = result.safe_text

        ok = must_contain in safe
        if must_not_contain and must_not_contain in safe:
            ok = False

        if not ok:
            all_pass = False
        status = "✓" if ok else "✗"
        print(f"  {status} [{label}] safe_text={safe!r}")

    assert all_pass, "English filler stripping tests failed"
    print("  ✓ ALL filler stripping tests PASSED")


# ══════════════════════════════════════════════════════════════════
#  BONUS: Full Intent Classifier Coverage
# ══════════════════════════════════════════════════════════════════

def test_intent_coverage():
    print_divider("BONUS: Intent Classifier Coverage")

    cases = [
        ("Hallo!", CallerIntent.GREETING),
        ("Goedemorgen", CallerIntent.GREETING),
        ("Tot ziens!", CallerIntent.GOODBYE),
        ("Doei!", CallerIntent.GOODBYE),
        ("Fijne dag!", CallerIntent.GOODBYE),
        ("Dag!", CallerIntent.GOODBYE),
        ("Ja graag", CallerIntent.CONFIRMATION),
        ("Nee bedankt", CallerIntent.DENIAL),
        ("Bedankt!", CallerIntent.GRATITUDE),
        ("Wat zijn jullie prijzen?", CallerIntent.PRICING),
        ("Hoeveel kost het per maand?", CallerIntent.PRICING),
        ("Ik wil een afspraak maken", CallerIntent.APPOINTMENT),
        ("Ik wil een echte medewerker spreken", CallerIntent.TRANSFER_REQUEST),
        ("Verbind me door met een mens", CallerIntent.TRANSFER_REQUEST),
        ("Dit is belachelijk!", CallerIntent.ANGER),
        ("Jullie zijn oplichters!", CallerIntent.ANGER),
        ("Het werkt niet", CallerIntent.COMPLAINT),
        ("Ik ben niet tevreden", CallerIntent.COMPLAINT),
        ("", CallerIntent.SILENCE),
        # Frustration
        ("Dat bedoel ik niet", CallerIntent.FRUSTRATION),
        ("Je begrijpt me niet", CallerIntent.FRUSTRATION),
        ("Nog steeds niet het goede antwoord", CallerIntent.FRUSTRATION),
        ("Dat heb ik al gezegd", CallerIntent.FRUSTRATION),
        ("We draaien in rondjes", CallerIntent.FRUSTRATION),
        # Off-topic
        ("Kun je een pizza voor me bestellen?", CallerIntent.OFF_TOPIC),
        ("Wat is de hoofdstad van Frankrijk?", CallerIntent.OFF_TOPIC),
        ("Kun je het weer voor morgen zeggen?", CallerIntent.OFF_TOPIC),
        ("Kan je mij helpen met mijn huiswerk?", CallerIntent.OFF_TOPIC),
        ("Vertel een mop", CallerIntent.OFF_TOPIC),
        ("Wie wint de Champions League?", CallerIntent.OFF_TOPIC),
        ("Kun je een gedicht schrijven?", CallerIntent.OFF_TOPIC),
    ]

    passed = failed = 0
    for utt, expected in cases:
        actual, conf = classify_intent(utt)
        ok = actual == expected
        status = "✓" if ok else "✗"
        if ok:
            passed += 1
        else:
            failed += 1
        line = f"  {status} \"{utt}\" → {actual.value}"
        if not ok:
            line += f"  (expected {expected.value})"
        line += f"  [{conf:.0%}]"
        print(line)

    print(f"\n  Results: {passed}/{passed + failed} passed")
    assert failed == 0, f"{failed} intent classification failures"
    print("  ✓ ALL intents correct")


# ══════════════════════════════════════════════════════════════════
#  RUN ALL
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_goodbye_denied()
    test_goodbye_allowed()
    test_pricing_question()
    test_anger_escalation()
    test_off_topic()
    test_output_guardrails_language()
    test_output_guardrails_leakage()
    test_low_confidence()
    test_repeated_failure()
    test_english_filler_stripping()
    test_intent_coverage()

    print_divider("ALL SCENARIOS COMPLETE — 10 SCENARIOS + INTENT COVERAGE")
    print()
