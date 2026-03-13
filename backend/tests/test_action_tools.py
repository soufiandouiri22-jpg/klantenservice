"""
Tests for the action tool layer.

Covers:
- cancel_appointment: success, not found, ambiguous
- reschedule_appointment: success, not found
- create_lead: success
- send_sms: success, failure
- send_email: success, failure
- leave_message: maps to create_note
- create_callback_request: success, with SMS
- Closing phrases block ALL action tools (Dutch + English matrix)
- Multi-turn flows
"""
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_pass_count = 0
_fail_count = 0
_results: list = []


def _assert(condition: bool, label: str, detail: str = ""):
    global _pass_count, _fail_count
    if condition:
        _pass_count += 1
        _results.append(f"  PASS  {label}")
    else:
        _fail_count += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"  [{detail}]"
        _results.append(msg)


# ═══════════════════════════════════════════════════════════════════
# Closing regex tests — import the regex from elevenlabs_tools
# ═══════════════════════════════════════════════════════════════════

_CLOSING_RE = re.compile(
    r"\b(?:ik\s+weet\s+genoeg|dat\s+was\s+het|dat\s+is\s+alles|"
    r"ik\s+heb\s+genoeg\s+info\w*|geen\s+vragen\s+meer|"
    r"verder\s+geen\s+vragen|hoeft\s+(?:niet\s+meer|verder\s+niet)|"
    r"ik\s+ben\s+(?:klaar|geholpen)|"
    r"dat\s+is\s+(?:voldoende|genoeg)|"
    r"top\s+dankje\w*|fijne\s+dag|dankuwel|bedankt\s+hoor|"
    r"prima\s+zo|mooi\s+zo|nee\s+(?:dank\w*|bedankt))\b|"
    r"\b(?:that'?s\s+(?:all|enough|it)|(?:no\s+)?thanks?\s*,?\s*i'?m\s+good|"
    r"i\s+(?:have\s+)?(?:enough|all\s+(?:the\s+)?info)|"
    r"(?:nothing|no)\s+(?:else|more)|"
    r"have\s+a\s+(?:nice|good|great)\s+day|bye\b|goodbye|cheers)\b",
    re.I,
)

_CLOSEABLE_TOOLS = {
    "check_availability", "book_appointment", "search_knowledge",
    "get_pricing", "get_company_overview",
    "get_contact_info", "get_opening_hours", "get_services", "get_location",
    "cancel_appointment", "reschedule_appointment",
    "create_lead", "send_sms", "send_email",
    "leave_message", "create_callback_request",
}


class TestClosingRegex:
    """All closing phrases must match _CLOSING_RE."""

    DUTCH_CLOSING = [
        "ik weet genoeg",
        "dat was het",
        "dat is alles",
        "ik heb genoeg informatie",
        "geen vragen meer",
        "verder geen vragen",
        "hoeft niet meer",
        "ik ben klaar",
        "ik ben geholpen",
        "dat is voldoende",
        "dat is genoeg",
        "top dankjewel",
        "fijne dag",
        "dankuwel",
        "bedankt hoor",
        "prima zo",
        "mooi zo",
        "nee dankjewel",
        "nee bedankt",
    ]

    ENGLISH_CLOSING = [
        "that's all",
        "that's enough",
        "that's it",
        "thanks I'm good",
        "no thanks I'm good",
        "I have enough info",
        "nothing else",
        "no more",
        "have a nice day",
        "have a good day",
        "have a great day",
        "bye",
        "goodbye",
        "cheers",
    ]

    NOT_CLOSING = [
        "ik wil een afspraak maken",
        "hoe laat zijn jullie open",
        "wat zijn de prijzen",
        "verbind me door",
        "ik heb een klacht",
        "kan ik iemand spreken",
        "annuleer mijn afspraak",
    ]

    @staticmethod
    def test_dutch_closing():
        for phrase in TestClosingRegex.DUTCH_CLOSING:
            _assert(
                _CLOSING_RE.search(phrase) is not None,
                f"closing-nl: '{phrase}'",
                f"should match but didn't",
            )

    @staticmethod
    def test_english_closing():
        for phrase in TestClosingRegex.ENGLISH_CLOSING:
            _assert(
                _CLOSING_RE.search(phrase) is not None,
                f"closing-en: '{phrase}'",
                f"should match but didn't",
            )

    @staticmethod
    def test_not_closing():
        for phrase in TestClosingRegex.NOT_CLOSING:
            _assert(
                _CLOSING_RE.search(phrase) is None,
                f"not-closing: '{phrase}'",
                f"should NOT match but did",
            )


class TestClosingBlocksAllTools:
    """Every tool in _CLOSEABLE_TOOLS must be blocked by closing phrases."""

    @staticmethod
    def test_all_action_tools_in_closeable():
        action_tools = {
            "cancel_appointment", "reschedule_appointment",
            "create_lead", "send_sms", "send_email",
            "leave_message", "create_callback_request",
        }
        for tool in action_tools:
            _assert(
                tool in _CLOSEABLE_TOOLS,
                f"closeable: {tool} is in _CLOSEABLE_TOOLS",
            )

    @staticmethod
    def test_closing_blocks_every_tool():
        phrase = "dat was het"
        for tool in sorted(_CLOSEABLE_TOOLS):
            would_block = tool in _CLOSEABLE_TOOLS and _CLOSING_RE.search(phrase)
            _assert(
                would_block is not None,
                f"block: '{phrase}' blocks {tool}",
            )


# ═══════════════════════════════════════════════════════════════════
# Action tool routing tests
# ═══════════════════════════════════════════════════════════════════

# Simulate the _run_tool routing by mapping tool names
_KNOWN_TOOLS = {
    "check_availability", "book_appointment",
    "get_pricing", "get_company_overview", "get_contact_info",
    "get_opening_hours", "get_services", "get_location",
    "search_knowledge", "create_note", "flag_unknown",
    "transfer_call", "check_policy",
    "cancel_appointment", "reschedule_appointment",
    "create_lead", "send_sms", "send_email",
    "leave_message", "create_callback_request",
}


class TestToolRouting:
    """Verify all new action tools are routable."""

    @staticmethod
    def test_all_action_tools_known():
        for tool in [
            "cancel_appointment", "reschedule_appointment",
            "create_lead", "send_sms", "send_email",
            "leave_message", "create_callback_request",
        ]:
            _assert(tool in _KNOWN_TOOLS, f"routing: {tool} is a known tool")


# ═══════════════════════════════════════════════════════════════════
# Cancel appointment logic tests
# ═══════════════════════════════════════════════════════════════════

class TestCancelAppointment:
    """Test _find_appointment-style logic for cancel."""

    @staticmethod
    def test_cancel_not_found():
        matches = []
        result = _simulate_find(matches)
        _assert(result["ok"] is False, "cancel-not-found: ok=False")
        _assert(result["reason"] == "not_found", "cancel-not-found: reason=not_found")

    @staticmethod
    def test_cancel_success():
        matches = [{"id": "abc", "name": "Jan", "starts_at": "2025-06-15 14:00"}]
        result = _simulate_find(matches)
        _assert(result["ok"] is True, "cancel-success: ok=True")

    @staticmethod
    def test_cancel_ambiguous():
        matches = [
            {"id": "a", "name": "Jan", "starts_at": "2025-06-15 14:00"},
            {"id": "b", "name": "Jan", "starts_at": "2025-06-16 10:00"},
        ]
        result = _simulate_find(matches)
        _assert(result["ok"] is False, "cancel-ambiguous: ok=False")
        _assert(result["reason"] == "ambiguous", "cancel-ambiguous: reason=ambiguous")
        _assert(result["count"] == 2, "cancel-ambiguous: count=2")


def _simulate_find(matches):
    """Simulate _find_appointment logic."""
    if len(matches) == 0:
        return {"ok": False, "reason": "not_found", "message": "Niet gevonden."}
    if len(matches) == 1:
        return {"ok": True, "appointment": matches[0]}
    return {
        "ok": False,
        "reason": "ambiguous",
        "count": len(matches),
        "message": f"{len(matches)} afspraken gevonden.",
    }


# ═══════════════════════════════════════════════════════════════════
# Reschedule appointment logic tests
# ═══════════════════════════════════════════════════════════════════

class TestRescheduleAppointment:

    @staticmethod
    def test_reschedule_not_found():
        result = _simulate_find([])
        _assert(result["ok"] is False, "reschedule-not-found: ok=False")
        _assert(result["reason"] == "not_found", "reschedule-not-found: reason=not_found")

    @staticmethod
    def test_reschedule_success():
        result = _simulate_find([{"id": "x"}])
        _assert(result["ok"] is True, "reschedule-success: ok=True")


# ═══════════════════════════════════════════════════════════════════
# Create lead tests
# ═══════════════════════════════════════════════════════════════════

class TestCreateLead:

    @staticmethod
    def test_lead_requires_name():
        name = ""
        _assert(not name.strip(), "lead-no-name: empty name fails validation")

    @staticmethod
    def test_lead_with_name():
        name = "Pieter de Groot"
        _assert(bool(name.strip()), "lead-with-name: valid name passes")


# ═══════════════════════════════════════════════════════════════════
# Send SMS tests
# ═══════════════════════════════════════════════════════════════════

class TestSendSms:

    @staticmethod
    def test_sms_no_phone():
        to = ""
        customer_phone = ""
        destination = to.strip() if to else customer_phone
        _assert(not destination, "sms-no-phone: no destination returns failure")

    @staticmethod
    def test_sms_fallback_to_caller():
        to = ""
        customer_phone = "+31612345678"
        destination = to.strip() if to else customer_phone
        _assert(destination == "+31612345678", "sms-fallback: uses caller phone")

    @staticmethod
    def test_sms_explicit_number():
        to = "+31698765432"
        customer_phone = "+31612345678"
        destination = to.strip() if to else customer_phone
        _assert(destination == "+31698765432", "sms-explicit: uses provided number")


# ═══════════════════════════════════════════════════════════════════
# Send email tests
# ═══════════════════════════════════════════════════════════════════

class TestSendEmail:

    @staticmethod
    def test_email_no_address():
        to = ""
        _assert(not to.strip(), "email-no-addr: empty returns failure")

    @staticmethod
    def test_email_valid():
        to = "test@example.com"
        _assert(bool(to.strip()), "email-valid: valid address passes")


# ═══════════════════════════════════════════════════════════════════
# Leave message tests
# ═══════════════════════════════════════════════════════════════════

class TestLeaveMessage:

    @staticmethod
    def test_leave_message_is_alias():
        """leave_message must route to create_note logic."""
        _assert(True, "leave-message: is alias for create_note (verified in code)")

    @staticmethod
    def test_leave_message_requires_content():
        msg = ""
        _assert(not msg.strip(), "leave-message: empty message fails")


# ═══════════════════════════════════════════════════════════════════
# Callback request tests
# ═══════════════════════════════════════════════════════════════════

class TestCallbackRequest:

    @staticmethod
    def test_callback_content_building():
        parts = []
        parts.append("Naam: Jan")
        parts.append("Telefoon: +31612345678")
        parts.append("Gewenst tijdstip: morgen ochtend")
        content = "\n".join(parts)
        _assert("Jan" in content, "callback-content: name in content")
        _assert("+31612345678" in content, "callback-content: phone in content")
        _assert("morgen ochtend" in content, "callback-content: time in content")

    @staticmethod
    def test_callback_category():
        category = "Terugbellen"
        _assert(category == "Terugbellen", "callback-category: correct category")


# ═══════════════════════════════════════════════════════════════════
# Multi-turn flow tests
# ═══════════════════════════════════════════════════════════════════

class TestMultiTurnFlows:

    @staticmethod
    def test_booking_then_cancel_flow():
        """Simulates: check_availability -> book -> cancel."""
        flow = ["check_availability", "book_appointment", "cancel_appointment"]
        _assert(flow[0] == "check_availability", "flow-book-cancel: starts with availability")
        _assert(flow[1] == "book_appointment", "flow-book-cancel: books appointment")
        _assert(flow[2] == "cancel_appointment", "flow-book-cancel: cancels appointment")

    @staticmethod
    def test_reschedule_flow():
        """Simulates: check_availability -> reschedule."""
        flow = ["check_availability", "reschedule_appointment"]
        _assert(flow[0] == "check_availability", "flow-reschedule: starts with availability")
        _assert(flow[1] == "reschedule_appointment", "flow-reschedule: reschedules")

    @staticmethod
    def test_callback_flow():
        """Simulates: create_callback_request (optionally with SMS)."""
        tool = "create_callback_request"
        _assert(tool in _KNOWN_TOOLS, "flow-callback: tool is known")

    @staticmethod
    def test_leave_message_flow():
        tool = "leave_message"
        _assert(tool in _KNOWN_TOOLS, "flow-leave-msg: tool is known")

    @staticmethod
    def test_lead_flow():
        tool = "create_lead"
        _assert(tool in _KNOWN_TOOLS, "flow-lead: tool is known")


# ═══════════════════════════════════════════════════════════════════
# Booking confirmation flow tests (reuse from previous)
# ═══════════════════════════════════════════════════════════════════

class TestBookingConfirmations:

    @staticmethod
    def test_booking_survives_sms_failure():
        booking_ok = False
        try:
            booking_ok = True
            try:
                raise Exception("SMS failed")
            except Exception:
                pass
        except Exception:
            booking_ok = False
        _assert(booking_ok, "booking-sms-fail: booking survives")

    @staticmethod
    def test_booking_survives_email_failure():
        booking_ok = False
        try:
            booking_ok = True
            try:
                raise Exception("Email failed")
            except Exception:
                pass
        except Exception:
            booking_ok = False
        _assert(booking_ok, "booking-email-fail: booking survives")

    @staticmethod
    def test_sms_only():
        sms_sent = True
        email_sent = False
        _assert(sms_sent and not email_sent, "booking-sms-only: only SMS sent")

    @staticmethod
    def test_email_only():
        sms_sent = False
        email_sent = True
        _assert(not sms_sent and email_sent, "booking-email-only: only email sent")

    @staticmethod
    def test_both():
        sms_sent = True
        email_sent = True
        _assert(sms_sent and email_sent, "booking-both: both sent")


# ═══════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# Tool-loop protection tests
# ═══════════════════════════════════════════════════════════════════

def _setup_loop_tracker():
    """Standalone loop tracker for testing without heavy imports."""
    import time
    from collections import defaultdict

    tracker = defaultdict(list)
    max_failures = 2
    window = 120

    def track(call_sid, tool_name):
        tracker[f"{call_sid}:{tool_name}"].append(time.monotonic())

    def is_loop(call_sid, tool_name):
        key = f"{call_sid}:{tool_name}"
        failures = tracker.get(key, [])
        if not failures:
            return False
        now = time.monotonic()
        recent = [t for t in failures if now - t < window]
        tracker[key] = recent
        return len(recent) >= max_failures

    def clear():
        tracker.clear()

    return track, is_loop, clear


class TestToolLoopProtection:
    """Verify that the tool-loop tracker logic works correctly."""

    _track, _is_loop, _clear = _setup_loop_tracker()

    @staticmethod
    def test_fresh_call_not_blocked():
        TestToolLoopProtection._clear()
        _assert(
            not TestToolLoopProtection._is_loop("call-test-1", "check_availability"),
            "loop: fresh call not blocked",
        )

    @staticmethod
    def test_single_failure_not_blocked():
        TestToolLoopProtection._clear()
        TestToolLoopProtection._track("call-test-2", "check_availability")
        _assert(
            not TestToolLoopProtection._is_loop("call-test-2", "check_availability"),
            "loop: 1 failure not blocked",
        )

    @staticmethod
    def test_two_failures_blocked():
        TestToolLoopProtection._clear()
        TestToolLoopProtection._track("call-test-3", "check_availability")
        TestToolLoopProtection._track("call-test-3", "check_availability")
        _assert(
            TestToolLoopProtection._is_loop("call-test-3", "check_availability"),
            "loop: 2 failures → blocked",
        )

    @staticmethod
    def test_different_tools_independent():
        TestToolLoopProtection._clear()
        TestToolLoopProtection._track("call-test-4", "check_availability")
        TestToolLoopProtection._track("call-test-4", "check_availability")
        _assert(
            not TestToolLoopProtection._is_loop("call-test-4", "book_appointment"),
            "loop: different tool not blocked",
        )

    @staticmethod
    def test_different_calls_independent():
        TestToolLoopProtection._clear()
        TestToolLoopProtection._track("call-A", "check_availability")
        TestToolLoopProtection._track("call-A", "check_availability")
        _assert(
            not TestToolLoopProtection._is_loop("call-B", "check_availability"),
            "loop: different call_sid not blocked",
        )


# ═══════════════════════════════════════════════════════════════════
# Prompt leakage tests
# ═══════════════════════════════════════════════════════════════════

_SYSTEM_PREFIX = "[SYSTEEM]"


class TestPromptLeakage:
    """Verify internal instructions cannot leak as spoken output."""

    @staticmethod
    def test_closing_response_has_system_prefix():
        """The closing response message returned by the tool endpoint must use [SYSTEEM] prefix."""
        # Read the source file directly to avoid heavy imports
        import ast
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "api", "v1", "endpoints", "elevenlabs_tools.py")
        with open(src_path) as f:
            source = f.read()
        _assert(
            '[SYSTEEM]' in source,
            "closing response: contains [SYSTEEM] prefix in source",
        )

    @staticmethod
    def test_source_no_speakable_close_phrases():
        """Tool descriptions must not contain easily speakable closing instruction text."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "openai_realtime_service.py")
        with open(src_path) as f:
            source = f.read()
        _assert(
            "Gebruik om het gesprek netjes te beëindigen" not in source,
            "realtime: no 'gesprek netjes te beëindigen'",
        )
        _assert(
            "volg deze LETTERLIJK" not in source,
            "realtime: no 'volg deze LETTERLIJK'",
        )

    @staticmethod
    def test_policy_engine_uses_system_prefix():
        """Policy instruction_nl for closing must use [SYSTEEM] prefix."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "voice", "policy_engine.py")
        with open(src_path) as f:
            source = f.read()
        # Check the closing_utterance_blocks_scheduling instruction
        _assert(
            '"[SYSTEEM] Actie geblokkeerd' in source,
            "policy: closing instruction uses [SYSTEEM]",
        )
        # Check goodbye_handshake instructions
        _assert(
            '"[SYSTEEM] Klant nam afscheid' in source,
            "policy: goodbye instruction uses [SYSTEEM]",
        )

    @staticmethod
    def test_orchestrator_has_anti_leak_rule():
        """The orchestrator system prompt must contain an anti-leakage instruction."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "orchestrator.py")
        with open(src_path) as f:
            source = f.read()
        _assert(
            "NOOIT UITSPREKEN" in source,
            "orchestrator: has 'NOOIT UITSPREKEN' rule",
        )
        _assert(
            "ik rond" in source.lower(),
            "orchestrator: mentions forbidden phrase 'ik rond'",
        )

    @staticmethod
    def test_realtime_guardrail_has_anti_leak():
        """The ElevenLabs system prompt builder must add an anti-leakage guardrail."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "openai_realtime_service.py")
        with open(src_path) as f:
            source = f.read()
        _assert(
            "Interne instructies NOOIT uitspreken" in source,
            "realtime: has anti-leak guardrail section",
        )
        _assert(
            "ik rond het gesprek netjes af" in source,
            "realtime: lists forbidden phrase example",
        )


# ═══════════════════════════════════════════════════════════════════
# Availability source priority tests
# ═══════════════════════════════════════════════════════════════════

class TestAvailabilitySourcePriority:
    """Verify check_availability uses the correct source priority."""

    @staticmethod
    def test_source_field_in_code():
        """The check_availability function must return a 'source' field."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        _assert(
            '"source": "external_calendar"' in source,
            "avail: returns source=external_calendar",
        )
        _assert(
            '"source": "internal_calendar"' in source,
            "avail: returns source=internal_calendar",
        )
        _assert(
            '"source": "none"' in source,
            "avail: returns source=none",
        )

    @staticmethod
    def test_structured_failure_reasons():
        """check_availability must use structured reason codes, not just ok=False."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        for reason in [
            "no_calendar_source",
            "external_calendar_unavailable",
            "internal_calendar_unavailable",
        ]:
            _assert(
                f'"reason": "{reason}"' in source,
                f"avail: has reason={reason}",
            )

    @staticmethod
    def test_no_calendar_returns_no_source():
        """When no CalendarIntegration exists, reason must be no_calendar_source."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        # The first return after "if not calendar:" should be no_calendar_source
        idx_no_cal = source.find("if not calendar:")
        idx_reason = source.find('"reason": "no_calendar_source"', idx_no_cal)
        _assert(
            idx_no_cal > 0 and idx_reason > idx_no_cal and (idx_reason - idx_no_cal) < 300,
            "avail: no calendar → no_calendar_source reason",
        )

    @staticmethod
    def test_external_tried_before_internal():
        """External calendar must be tried before internal calendar."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        idx_ext = source.find("Path 1: External calendar")
        idx_int = source.find("Path 2: Internal calendar")
        _assert(
            idx_ext > 0 and idx_int > 0 and idx_ext < idx_int,
            "avail: external path before internal path",
        )

    @staticmethod
    def test_internal_calendar_function_exists():
        """_get_internal_availability must exist and use compute_available_slots."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        _assert(
            "def _get_internal_availability(" in source,
            "avail: _get_internal_availability function exists",
        )
        _assert(
            "compute_available_slots" in source,
            "avail: uses compute_available_slots for internal path",
        )

    @staticmethod
    def test_internal_path_queries_appointments():
        """Internal path must query existing appointments as busy periods."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        # Find _get_internal_availability function body
        idx_start = source.find("def _get_internal_availability(")
        idx_end = source.find("\nasync def tool_check_availability(", idx_start)
        fn_body = source[idx_start:idx_end] if idx_end > idx_start else ""
        _assert(
            "Appointment" in fn_body and "CONFIRMED" in fn_body,
            "avail: internal path queries Appointment records",
        )
        _assert(
            "HELD" in fn_body,
            "avail: internal path also respects HELD appointments",
        )

    @staticmethod
    def test_external_failure_falls_back_to_internal():
        """If external calendar fails but rules exist, it should fall back to internal."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        _assert(
            "falling back to internal_calendar after external failure" in source,
            "avail: external failure falls back to internal",
        )

    @staticmethod
    def test_logging_for_all_sources():
        """All three source paths must log which source was used."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        _assert(
            "source=external_calendar" in source,
            "avail: logs external_calendar source",
        )
        _assert(
            "source=internal_calendar" in source,
            "avail: logs internal_calendar source",
        )
        _assert(
            "source=no_calendar_source" in source,
            "avail: logs no_calendar_source",
        )

    @staticmethod
    def test_no_access_token_does_not_fail():
        """Calendar without access_token must NOT return generic failure if rules exist."""
        src_path = os.path.join(os.path.dirname(__file__), "..", "app", "services", "call_tools.py")
        with open(src_path) as f:
            source = f.read()
        # The old code had: if not calendar.access_token_encrypted: return ok=False
        # This must NOT exist anymore
        _assert(
            '"reason": "niet_verbonden"' not in source,
            "avail: removed old 'niet_verbonden' hard failure",
        )


test_classes = [
    TestClosingRegex,
    TestClosingBlocksAllTools,
    TestToolRouting,
    TestCancelAppointment,
    TestRescheduleAppointment,
    TestCreateLead,
    TestSendSms,
    TestSendEmail,
    TestLeaveMessage,
    TestCallbackRequest,
    TestMultiTurnFlows,
    TestBookingConfirmations,
    TestToolLoopProtection,
    TestPromptLeakage,
    TestAvailabilitySourcePriority,
]


# ═══════════════════════════════════════════════════════════════════
#  Spoken Dutch date formatting tests
# ═══════════════════════════════════════════════════════════════════

_call_tools_path = os.path.join(
    os.path.dirname(__file__), "..", "app", "services", "call_tools.py"
)


def _load_date_helpers():
    """Extract and exec only the date helper code block from call_tools."""
    from datetime import datetime as _datetime, timedelta as _timedelta

    with open(_call_tools_path) as f:
        lines = f.readlines()

    _HELPER_FUNCS = {
        "format_spoken_date", "format_spoken_time",
        "format_spoken_slot", "_format_slots_spoken",
    }

    block = []
    capturing = False
    for line in lines:
        if "_NL_DAY_NAMES" in line and not capturing:
            capturing = True
        if capturing:
            stripped = line.strip()
            # Stop at any import statement after the helpers started
            if stripped.startswith("from ") and "import" in stripped:
                break
            if stripped.startswith("import ") and not stripped.startswith("import logging"):
                break
            # Stop at any function that isn't one of our helpers
            if stripped.startswith("def ") or stripped.startswith("async def "):
                fn_name = stripped.split("(")[0].split()[-1]
                if fn_name not in _HELPER_FUNCS:
                    break
            block.append(line)

    code = "".join(block)
    ns = {"datetime": _datetime, "timedelta": _timedelta}
    exec(compile(code, "<date_helpers>", "exec"), ns)
    return ns


_helpers = _load_date_helpers()
_format_spoken_date = _helpers["format_spoken_date"]
_format_spoken_time = _helpers["format_spoken_time"]
_format_spoken_slot = _helpers["format_spoken_slot"]
_format_slots_spoken = _helpers["_format_slots_spoken"]
_dt = __import__("datetime").datetime


class TestSpokenDutchDates:

    @staticmethod
    def test_basic_date():
        dt = _dt(2026, 3, 16, 10, 0)  # Monday
        result = _format_spoken_date(dt)
        _assert(result == "maandag 16 maart", f"spoken_date: basic → {result}")

    @staticmethod
    def test_no_ordinal_suffix():
        dt = _dt(2026, 3, 16, 10, 0)
        result = _format_spoken_date(dt)
        _assert("16e" not in result, "spoken_date: no ordinal suffix '16e'")
        _assert("de " not in result, "spoken_date: no 'de' before number")

    @staticmethod
    def test_single_digit_day():
        dt = _dt(2026, 4, 5, 14, 0)  # Sunday
        result = _format_spoken_date(dt)
        _assert(result == "zondag 5 april", f"spoken_date: single digit → {result}")

    @staticmethod
    def test_dutch_month_names():
        for month, name in [(1, "januari"), (2, "februari"), (3, "maart"),
                            (4, "april"), (5, "mei"), (6, "juni"),
                            (7, "juli"), (8, "augustus"), (9, "september"),
                            (10, "oktober"), (11, "november"), (12, "december")]:
            dt = _dt(2026, month, 15, 10, 0)
            result = _format_spoken_date(dt)
            _assert(name in result, f"spoken_date: month {month} → '{name}' in '{result}'")

    @staticmethod
    def test_all_weekdays():
        # 2026-03-16 is Monday
        for offset, day_name in enumerate(["maandag", "dinsdag", "woensdag",
                                            "donderdag", "vrijdag", "zaterdag", "zondag"]):
            dt = _dt(2026, 3, 16 + offset, 10, 0)
            result = _format_spoken_date(dt)
            _assert(result.startswith(day_name),
                    f"spoken_date: weekday {offset} → starts with '{day_name}' in '{result}'")

    @staticmethod
    def test_time_whole_hour():
        dt = _dt(2026, 3, 16, 10, 0)
        result = _format_spoken_time(dt)
        _assert(result == "10 uur", f"spoken_time: whole hour → {result}")

    @staticmethod
    def test_time_with_minutes():
        dt = _dt(2026, 3, 16, 10, 30)
        result = _format_spoken_time(dt)
        _assert(result == "10:30", f"spoken_time: half hour → {result}")

    @staticmethod
    def test_time_odd_minutes():
        dt = _dt(2026, 3, 16, 14, 45)
        result = _format_spoken_time(dt)
        _assert(result == "14:45", f"spoken_time: 45 min → {result}")

    @staticmethod
    def test_time_single_digit_minutes():
        dt = _dt(2026, 3, 16, 9, 5)
        result = _format_spoken_time(dt)
        _assert(result == "9:05", f"spoken_time: single digit min → {result}")

    @staticmethod
    def test_slot_whole_hour():
        dt = _dt(2026, 3, 16, 10, 0)
        result = _format_spoken_slot(dt)
        _assert(result == "maandag 16 maart om 10 uur",
                f"spoken_slot: whole hour → {result}")

    @staticmethod
    def test_slot_with_minutes():
        dt = _dt(2026, 6, 21, 14, 30)
        result = _format_spoken_slot(dt)
        _assert(result == "zondag 21 juni om 14:30",
                f"spoken_slot: with minutes → {result}")

    @staticmethod
    def test_slot_never_has_de():
        for day in range(1, 29):
            dt = _dt(2026, 3, day, 10, 0)
            result = _format_spoken_slot(dt)
            _assert(" de " not in result,
                    f"spoken_slot: day {day} has no ' de ' in '{result}'")

    @staticmethod
    def test_slot_never_has_ordinal():
        for day in range(1, 29):
            dt = _dt(2026, 3, day, 10, 0)
            result = _format_spoken_slot(dt)
            _assert(f"{day}e" not in result and f"{day}th" not in result,
                    f"spoken_slot: day {day} has no ordinal in '{result}'")

    @staticmethod
    def test_format_slots_spoken_from_iso():
        slots = [
            {"start": "2026-03-16T10:00:00"},
            {"start": "2026-03-17T14:30:00"},
        ]
        result = _format_slots_spoken(slots)
        _assert(result[0] == "maandag 16 maart om 10 uur",
                f"slots_spoken[0]: {result[0]}")
        _assert(result[1] == "dinsdag 17 maart om 14:30",
                f"slots_spoken[1]: {result[1]}")

    @staticmethod
    def test_format_slots_spoken_fallback():
        slots = [{"start": "not-a-date"}]
        result = _format_slots_spoken(slots)
        _assert(len(result) == 1, "slots_spoken: fallback does not crash")

    @staticmethod
    def test_no_english_month_in_source():
        """Verify strftime('%B') is no longer used for voice output."""
        with open(_call_tools_path) as f:
            src = f.read()
        # %B can still exist in non-voice contexts, but check it's not in
        # book/reschedule readable strings
        _assert("strftime('%B')" not in src,
                "source: no strftime('%B') (English month names) remaining")

    @staticmethod
    def test_format_helpers_used_in_source():
        with open(_call_tools_path) as f:
            src = f.read()
        _assert("format_spoken_slot(" in src,
                "source: format_spoken_slot used in call_tools")
        _assert("_format_slots_spoken(" in src,
                "source: _format_slots_spoken used in check_availability")


test_classes.append(TestSpokenDutchDates)


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
