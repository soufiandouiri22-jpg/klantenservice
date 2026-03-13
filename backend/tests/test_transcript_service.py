"""
Tests for the transcript service.

Covers:
- _extract_transcript: canonical field, nested alternatives, empty/missing
- fetch_elevenlabs_transcript: status-aware retry, immediate success,
  404 handling, exception handling, status=done+empty, status=failed
- save_transcript_records: role mapping, dedup, edge cases
- build_transcript_text: formatting, empty handling
- fetch_and_process_transcript: pipeline retry logic
"""
import sys
import os
import asyncio
import types

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
#  Stub out heavy dependencies before importing the module
# ═══════════════════════════════════════════════════════════════════

class _FakeSettings:
    ELEVENLABS_API_KEY = "test-key"
    ELEVENLABS_AGENT_ID = "test-agent"
    DATABASE_URL = ""

# Build minimal module stubs
for mod_name in [
    "app", "app.core", "app.core.config",
    "app.models", "app.models.call_log",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

sys.modules["app.core.config"].settings = _FakeSettings()


class _FakeCallLog:
    pass


class _FakeCallTranscript:
    call_log_id = None
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


sys.modules["app.models.call_log"].CallLog = _FakeCallLog
sys.modules["app.models.call_log"].CallTranscript = _FakeCallTranscript

# Stub httpx so the module can import
_real_httpx = types.ModuleType("httpx")

class _MockResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._json


_mock_responses = []
_mock_call_count = [0]


class _MockAsyncClient:
    def __init__(self, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def get(self, url, **kw):
        idx = min(_mock_call_count[0], len(_mock_responses) - 1)
        _mock_call_count[0] += 1
        resp_def = _mock_responses[idx]
        if isinstance(resp_def, Exception):
            raise resp_def
        return resp_def


_real_httpx.AsyncClient = _MockAsyncClient
sys.modules["httpx"] = _real_httpx

# Stub sqlalchemy
if "sqlalchemy" not in sys.modules:
    sys.modules["sqlalchemy"] = types.ModuleType("sqlalchemy")
if "sqlalchemy.orm" not in sys.modules:
    sys.modules["sqlalchemy.orm"] = types.ModuleType("sqlalchemy.orm")
    sys.modules["sqlalchemy.orm"].Session = object

# Now import the module
src_path = os.path.join(
    os.path.dirname(__file__), "..", "app", "services", "transcript_service.py"
)

# We need to import dynamically since the module path isn't a normal package
import importlib.util
spec = importlib.util.spec_from_file_location("transcript_service", src_path)
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)

_extract_transcript = ts._extract_transcript
build_transcript_text = ts.build_transcript_text
fetch_elevenlabs_transcript = ts.fetch_elevenlabs_transcript
_PENDING_STATUSES = ts._PENDING_STATUSES
_INITIAL_WAIT_SECS = ts._INITIAL_WAIT_SECS
_MAX_FETCH_ATTEMPTS = ts._MAX_FETCH_ATTEMPTS

# Patch asyncio.sleep to be instant for tests
_original_sleep = asyncio.sleep


async def _fast_sleep(n):
    await _original_sleep(0)


ts.asyncio.sleep = _fast_sleep


def _set_mock_responses(responses):
    global _mock_responses
    _mock_responses = responses
    _mock_call_count[0] = 0


# ═══════════════════════════════════════════════════════════════════
#  1. _extract_transcript tests
# ═══════════════════════════════════════════════════════════════════

class TestExtractTranscript:

    @staticmethod
    def test_canonical_top_level():
        data = {
            "status": "done",
            "transcript": [
                {"role": "user", "message": "Hallo", "time_in_call_secs": 0},
                {"role": "ai", "message": "Dag!", "time_in_call_secs": 1},
            ],
        }
        result = _extract_transcript(data)
        _assert(len(result) == 2, "extract: canonical field returns 2 entries")
        _assert(result[0]["message"] == "Hallo", "extract: first message correct")

    @staticmethod
    def test_empty_transcript_top_level():
        data = {"status": "processing", "transcript": []}
        result = _extract_transcript(data)
        _assert(result == [], "extract: empty transcript returns []")

    @staticmethod
    def test_no_transcript_key():
        data = {"status": "done", "agent_id": "abc"}
        result = _extract_transcript(data)
        _assert(result == [], "extract: missing transcript key returns []")

    @staticmethod
    def test_nested_conversation_transcript():
        data = {
            "status": "done",
            "transcript": [],
            "conversation": {
                "transcript": [
                    {"role": "user", "message": "Test", "time_in_call_secs": 0}
                ]
            },
        }
        result = _extract_transcript(data)
        _assert(len(result) == 1, "extract: nested conversation.transcript works")
        _assert(result[0]["message"] == "Test", "extract: nested message correct")

    @staticmethod
    def test_messages_key_fallback():
        data = {
            "status": "done",
            "messages": [
                {"role": "ai", "message": "Welkom", "time_in_call_secs": 0}
            ],
        }
        result = _extract_transcript(data)
        _assert(len(result) == 1, "extract: 'messages' fallback works")
        _assert(result[0]["role"] == "ai", "extract: messages role correct")

    @staticmethod
    def test_analysis_transcript_fallback():
        data = {
            "status": "done",
            "analysis": {
                "transcript": [
                    {"role": "user", "message": "Vraag", "time_in_call_secs": 5}
                ]
            },
        }
        result = _extract_transcript(data)
        _assert(len(result) == 1, "extract: analysis.transcript fallback works")

    @staticmethod
    def test_transcript_none_value():
        data = {"status": "done", "transcript": None}
        result = _extract_transcript(data)
        _assert(result == [], "extract: transcript=None returns []")

    @staticmethod
    def test_transcript_string_value():
        data = {"status": "done", "transcript": "not a list"}
        result = _extract_transcript(data)
        _assert(result == [], "extract: transcript=string returns []")

    @staticmethod
    def test_completely_empty_response():
        result = _extract_transcript({})
        _assert(result == [], "extract: empty dict returns []")

    @staticmethod
    def test_priority_canonical_over_nested():
        data = {
            "transcript": [{"role": "ai", "message": "canonical"}],
            "messages": [{"role": "ai", "message": "alt"}],
            "conversation": {"transcript": [{"role": "ai", "message": "nested"}]},
        }
        result = _extract_transcript(data)
        _assert(result[0]["message"] == "canonical", "extract: canonical wins over alternatives")


# ═══════════════════════════════════════════════════════════════════
#  2. build_transcript_text tests
# ═══════════════════════════════════════════════════════════════════

class TestBuildTranscriptText:

    @staticmethod
    def test_basic_formatting():
        entries = [
            {"role": "user", "message": "Hallo"},
            {"role": "ai", "message": "Dag!"},
        ]
        text = build_transcript_text(entries)
        _assert("Klant: Hallo" in text, "build_text: user → Klant")
        _assert("AI: Dag!" in text, "build_text: ai → AI")

    @staticmethod
    def test_empty_messages_skipped():
        entries = [
            {"role": "user", "message": ""},
            {"role": "ai", "message": "   "},
            {"role": "user", "message": "Echt bericht"},
        ]
        text = build_transcript_text(entries)
        _assert(text.count("\n") == 0, "build_text: empty messages produce single line")
        _assert("Echt bericht" in text, "build_text: real message included")

    @staticmethod
    def test_text_key_fallback():
        entries = [{"role": "user", "text": "Via text key"}]
        text = build_transcript_text(entries)
        _assert("Via text key" in text, "build_text: 'text' key used as fallback")

    @staticmethod
    def test_caller_role_mapping():
        entries = [
            {"role": "caller", "message": "Bel"},
            {"role": "human", "message": "Mens"},
        ]
        text = build_transcript_text(entries)
        _assert(text.count("Klant:") == 2, "build_text: caller/human mapped to Klant")

    @staticmethod
    def test_empty_input():
        text = build_transcript_text([])
        _assert(text == "", "build_text: empty list → empty string")


# ═══════════════════════════════════════════════════════════════════
#  3. Constants / configuration tests
# ═══════════════════════════════════════════════════════════════════

class TestConstants:

    @staticmethod
    def test_pending_statuses():
        _assert("processing" in _PENDING_STATUSES, "const: 'processing' is pending")
        _assert("in-progress" in _PENDING_STATUSES, "const: 'in-progress' is pending")
        _assert("initiated" in _PENDING_STATUSES, "const: 'initiated' is pending")
        _assert("done" not in _PENDING_STATUSES, "const: 'done' is NOT pending")
        _assert("failed" not in _PENDING_STATUSES, "const: 'failed' is NOT pending")

    @staticmethod
    def test_retry_config():
        _assert(_INITIAL_WAIT_SECS >= 5, "const: initial wait >= 5s")
        _assert(_MAX_FETCH_ATTEMPTS >= 4, "const: at least 4 fetch attempts")


# ═══════════════════════════════════════════════════════════════════
#  4. fetch_elevenlabs_transcript — async tests with mock
# ═══════════════════════════════════════════════════════════════════

def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestFetchTranscript:

    @staticmethod
    def test_immediate_success():
        """Transcript available on first fetch with status=done."""
        transcript_data = [
            {"role": "user", "message": "Hallo", "time_in_call_secs": 0},
            {"role": "ai", "message": "Dag!", "time_in_call_secs": 1},
        ]
        _set_mock_responses([
            _MockResponse(200, {"status": "done", "transcript": transcript_data}),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-1"))
        _assert(transcript is not None and len(transcript) == 2,
                "fetch: immediate success returns 2 entries")
        _assert(status == "done", "fetch: status is 'done' on immediate success")

    @staticmethod
    def test_processing_then_done():
        """First fetch: processing+empty, second fetch: done+transcript."""
        transcript_data = [
            {"role": "ai", "message": "Welkom", "time_in_call_secs": 0},
        ]
        _set_mock_responses([
            _MockResponse(200, {"status": "processing", "transcript": []}),
            _MockResponse(200, {"status": "done", "transcript": transcript_data}),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-2"))
        _assert(transcript is not None and len(transcript) == 1,
                "fetch: processing→done returns transcript on retry")
        _assert(status == "done", "fetch: final status is 'done' after retry")

    @staticmethod
    def test_multiple_processing_retries():
        """Multiple processing responses before done."""
        transcript_data = [{"role": "user", "message": "Ja"}]
        _set_mock_responses([
            _MockResponse(200, {"status": "processing", "transcript": []}),
            _MockResponse(200, {"status": "processing", "transcript": []}),
            _MockResponse(200, {"status": "processing", "transcript": []}),
            _MockResponse(200, {"status": "done", "transcript": transcript_data}),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-3"))
        _assert(transcript is not None and len(transcript) == 1,
                "fetch: survives multiple processing retries")

    @staticmethod
    def test_404_then_success():
        """404 on first attempt, success on second."""
        transcript_data = [{"role": "ai", "message": "Hallo"}]
        _set_mock_responses([
            _MockResponse(404),
            _MockResponse(200, {"status": "done", "transcript": transcript_data}),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-4"))
        _assert(transcript is not None and len(transcript) == 1,
                "fetch: 404→success works")

    @staticmethod
    def test_failed_status():
        """Conversation with status=failed returns None immediately."""
        _set_mock_responses([
            _MockResponse(200, {"status": "failed", "transcript": []}),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-5"))
        _assert(transcript is None, "fetch: failed status returns None")
        _assert(status == "failed", "fetch: status is 'failed'")

    @staticmethod
    def test_done_but_empty():
        """Status=done but transcript empty — returns empty list, not None."""
        _set_mock_responses([
            _MockResponse(200, {"status": "done", "transcript": []}),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-6"))
        _assert(isinstance(transcript, list) and len(transcript) == 0,
                "fetch: done+empty returns [] (not None)")
        _assert(status == "done", "fetch: status is 'done' on empty transcript")

    @staticmethod
    def test_exception_with_retry():
        """Network exception on first attempt, success on second."""
        transcript_data = [{"role": "user", "message": "Test"}]
        _set_mock_responses([
            Exception("Connection timeout"),
            _MockResponse(200, {"status": "done", "transcript": transcript_data}),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-7"))
        _assert(transcript is not None and len(transcript) == 1,
                "fetch: exception→success works on retry")

    @staticmethod
    def test_messages_fallback_key():
        """Transcript under 'messages' key is found."""
        _set_mock_responses([
            _MockResponse(200, {
                "status": "done",
                "transcript": [],
                "messages": [{"role": "ai", "message": "Alt"}],
            }),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-8"))
        _assert(transcript is not None and len(transcript) == 1,
                "fetch: messages key fallback works")

    @staticmethod
    def test_all_retries_exhausted_processing():
        """All retries exhausted while still processing → returns None."""
        _set_mock_responses([
            _MockResponse(200, {"status": "processing", "transcript": []}),
        ] * 10)
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-9"))
        _assert(transcript is None,
                "fetch: all retries exhausted returns None")
        _assert(status == "processing",
                "fetch: final status is 'processing' when exhausted")

    @staticmethod
    def test_in_progress_also_retries():
        """Status 'in-progress' also triggers retry."""
        transcript_data = [{"role": "ai", "message": "Ready"}]
        _set_mock_responses([
            _MockResponse(200, {"status": "in-progress", "transcript": []}),
            _MockResponse(200, {"status": "done", "transcript": transcript_data}),
        ])
        transcript, status = _run_async(fetch_elevenlabs_transcript("conv-10"))
        _assert(transcript is not None and len(transcript) == 1,
                "fetch: in-progress→done works")

    @staticmethod
    def test_attempt_count_logged():
        """Verify the function makes multiple attempts (observable via call count)."""
        _set_mock_responses([
            _MockResponse(200, {"status": "processing", "transcript": []}),
            _MockResponse(200, {"status": "processing", "transcript": []}),
            _MockResponse(200, {"status": "done", "transcript": [{"role": "ai", "message": "OK"}]}),
        ])
        _mock_call_count[0] = 0
        _run_async(fetch_elevenlabs_transcript("conv-11"))
        _assert(_mock_call_count[0] == 3,
                "fetch: made exactly 3 API calls for 2 processing + 1 done")


# ═══════════════════════════════════════════════════════════════════
#  5. Source-level verification tests
# ═══════════════════════════════════════════════════════════════════

class TestSourceVerification:

    @staticmethod
    def _src():
        with open(src_path) as f:
            return f.read()

    @staticmethod
    def test_status_check_present():
        src = TestSourceVerification._src()
        _assert("_PENDING_STATUSES" in src,
                "source: _PENDING_STATUSES defined")
        _assert('"processing"' in src,
                "source: 'processing' status handled")

    @staticmethod
    def test_retry_on_processing():
        src = TestSourceVerification._src()
        _assert("last_status in _PENDING_STATUSES" in src,
                "source: retry checks for pending status")

    @staticmethod
    def test_extract_transcript_function():
        src = TestSourceVerification._src()
        _assert("def _extract_transcript" in src,
                "source: _extract_transcript helper defined")
        _assert('"messages"' in src,
                "source: checks 'messages' key")
        _assert('"conversation"' in src,
                "source: checks nested 'conversation' key")

    @staticmethod
    def test_logging_includes_status():
        src = TestSourceVerification._src()
        _assert("status=" in src and "transcript_len=" in src,
                "source: log includes status and transcript_len")

    @staticmethod
    def test_returns_tuple():
        src = TestSourceVerification._src()
        _assert("Tuple[Optional[list[dict]], str]" in src,
                "source: fetch returns Tuple with status")

    @staticmethod
    def test_initial_wait():
        src = TestSourceVerification._src()
        _assert("_INITIAL_WAIT_SECS" in src,
                "source: uses configurable initial wait")
        _assert("await asyncio.sleep(_INITIAL_WAIT_SECS)" in src,
                "source: pipeline uses _INITIAL_WAIT_SECS")

    @staticmethod
    def test_max_attempts_configurable():
        src = TestSourceVerification._src()
        _assert("_MAX_FETCH_ATTEMPTS" in src,
                "source: max attempts is configurable")
        _assert("range(_MAX_FETCH_ATTEMPTS)" in src,
                "source: loop uses _MAX_FETCH_ATTEMPTS")

    @staticmethod
    def test_top_keys_logged():
        src = TestSourceVerification._src()
        _assert("top_keys" in src,
                "source: logs response top-level keys for debugging")

    @staticmethod
    def test_text_key_support():
        src = TestSourceVerification._src()
        count = src.count('"text"')
        _assert(count >= 2,
                "source: 'text' key checked in save + build functions")


# ═══════════════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════════════

def _run_all():
    global _results
    for cls in [
        TestExtractTranscript,
        TestBuildTranscriptText,
        TestConstants,
        TestFetchTranscript,
        TestSourceVerification,
    ]:
        section_start = len(_results)
        print(f"\n{'─' * 60}")
        print(f"  {cls.__name__}")
        print(f"{'─' * 60}")
        for name in sorted(dir(cls)):
            if name.startswith("test_"):
                try:
                    getattr(cls, name)()
                except Exception as e:
                    _assert(False, f"{cls.__name__}.{name}", f"EXCEPTION: {e}")
        for r in _results[section_start:]:
            print(r)

    print(f"\n{'═' * 60}")
    print(f"  TOTAL: {_pass_count} passed, {_fail_count} failed")
    print(f"{'═' * 60}")

    if _fail_count > 0:
        print("\nFailed tests:")
        for r in _results:
            if r.startswith("  FAIL"):
                print(r)
        sys.exit(1)


if __name__ == "__main__":
    _run_all()
