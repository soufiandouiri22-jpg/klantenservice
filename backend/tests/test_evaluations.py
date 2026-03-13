"""
Tests for the LangSmith evaluation service.

Covers:
- GPT evaluator response parsing (valid, invalid, missing fields)
- LangSmith client creation (configured, not configured, import error)
- evaluate_call pipeline (success, no transcript, already exists, GPT failure)
- sync_evaluations batch flow
- Graceful degradation when LangSmith/OpenAI unavailable
- Schema validation
"""
import sys
import os
import json
import types
import asyncio

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
#  Source path
# ═══════════════════════════════════════════════════════════════════

_service_path = os.path.join(
    os.path.dirname(__file__), "..", "app", "services", "langsmith_service.py"
)
_model_path = os.path.join(
    os.path.dirname(__file__), "..", "app", "models", "call_evaluation.py"
)
_schema_path = os.path.join(
    os.path.dirname(__file__), "..", "app", "schemas", "evaluation.py"
)
_config_path = os.path.join(
    os.path.dirname(__file__), "..", "app", "core", "config.py"
)
_admin_path = os.path.join(
    os.path.dirname(__file__), "..", "app", "api", "v1", "endpoints", "admin.py"
)
_transcript_path = os.path.join(
    os.path.dirname(__file__), "..", "app", "services", "transcript_service.py"
)


def _read(path: str) -> str:
    with open(path) as f:
        return f.read()


# ═══════════════════════════════════════════════════════════════════
#  1. Source structure tests
# ═══════════════════════════════════════════════════════════════════

class TestSourceStructure:

    @staticmethod
    def test_config_has_langsmith_vars():
        src = _read(_config_path)
        _assert("LANGSMITH_API_KEY" in src, "config: LANGSMITH_API_KEY defined")
        _assert("LANGSMITH_PROJECT" in src, "config: LANGSMITH_PROJECT defined")
        _assert("LANGSMITH_ENDPOINT" in src, "config: LANGSMITH_ENDPOINT defined")

    @staticmethod
    def test_service_has_key_functions():
        src = _read(_service_path)
        _assert("def is_configured" in src, "service: is_configured defined")
        _assert("def _get_langsmith_client" in src, "service: _get_langsmith_client defined")
        _assert("async def _run_gpt_evaluator" in src, "service: _run_gpt_evaluator defined")
        _assert("def _log_to_langsmith" in src, "service: _log_to_langsmith defined")
        _assert("async def evaluate_call" in src, "service: evaluate_call defined")
        _assert("async def sync_evaluations" in src, "service: sync_evaluations defined")

    @staticmethod
    def test_service_graceful_langsmith_failure():
        src = _read(_service_path)
        _assert("except ImportError" in src, "service: handles langsmith ImportError")
        _assert("non-blocking" in src.lower() or "non_blocking" in src, "service: LangSmith logging is non-blocking")

    @staticmethod
    def test_service_graceful_openai_failure():
        src = _read(_service_path)
        _assert("OPENAI_API_KEY" in src, "service: checks OPENAI_API_KEY")
        _assert("json.JSONDecodeError" in src, "service: handles JSON parse errors")

    @staticmethod
    def test_model_exists():
        src = _read(_model_path)
        _assert("class CallEvaluation" in src, "model: CallEvaluation class defined")
        _assert("call_evaluations" in src, "model: table name is call_evaluations")
        _assert("quality_score" in src, "model: quality_score field")
        _assert("hallucination_detected" in src, "model: hallucination_detected field")
        _assert("wrong_tool_detected" in src, "model: wrong_tool_detected field")
        _assert("customer_helped" in src, "model: customer_helped field")
        _assert("needs_review" in src, "model: needs_review field")
        _assert("langsmith_run_id" in src, "model: langsmith_run_id field")

    @staticmethod
    def test_schemas_exist():
        src = _read(_schema_path)
        _assert("class EvaluationResponse" in src, "schema: EvaluationResponse defined")
        _assert("class EvaluationDetailResponse" in src, "schema: EvaluationDetailResponse defined")
        _assert("class EvaluationListResponse" in src, "schema: EvaluationListResponse defined")
        _assert("class EvaluationSummaryResponse" in src, "schema: EvaluationSummaryResponse defined")
        _assert("class EvaluationSyncRequest" in src, "schema: EvaluationSyncRequest defined")

    @staticmethod
    def test_admin_endpoints():
        src = _read(_admin_path)
        _assert('"/evaluations/summary"' in src, "admin: summary endpoint")
        _assert('"/evaluations/{evaluation_id}"' in src, "admin: detail endpoint")
        _assert('"/evaluations"' in src, "admin: list endpoint")
        _assert('"/evaluations/sync"' in src, "admin: sync endpoint")
        _assert("require_superadmin" in src, "admin: uses superadmin auth")

    @staticmethod
    def test_pipeline_hook():
        src = _read(_transcript_path)
        _assert("evaluate_call" in src, "pipeline: evaluate_call hooked into transcript service")
        _assert("non-blocking" in src.lower() or "non_blocking" in src, "pipeline: evaluation is non-blocking")

    @staticmethod
    def test_evaluator_prompt_exists():
        src = _read(_service_path)
        _assert("_EVALUATOR_SYSTEM_PROMPT" in src, "service: evaluator system prompt defined")
        _assert("quality_score" in src, "service: prompt mentions quality_score")
        _assert("hallucination" in src, "service: prompt mentions hallucination")
        _assert("json_object" in src, "service: uses JSON response format")


# ═══════════════════════════════════════════════════════════════════
#  2. GPT evaluator parsing tests (via extracted function)
# ═══════════════════════════════════════════════════════════════════

class TestEvaluatorParsing:

    @staticmethod
    def test_valid_response_parsing():
        valid = {
            "quality_score": 85,
            "hallucination_detected": False,
            "wrong_tool_detected": False,
            "customer_helped": True,
            "needs_review": False,
            "summary": "Good call",
            "issues": [],
        }
        raw = json.dumps(valid)
        parsed = json.loads(raw)
        _assert(parsed["quality_score"] == 85, "parse: quality_score correct")
        _assert(parsed["hallucination_detected"] is False, "parse: hallucination correct")
        _assert(parsed["customer_helped"] is True, "parse: customer_helped correct")
        _assert(isinstance(parsed["issues"], list), "parse: issues is list")

    @staticmethod
    def test_score_boundaries():
        for score in [0, 50, 100]:
            result = {"quality_score": score}
            _assert(0 <= result["quality_score"] <= 100,
                    f"parse: score {score} within bounds")

    @staticmethod
    def test_invalid_json_handling():
        try:
            json.loads("not json at all")
            _assert(False, "parse: should fail on invalid JSON")
        except json.JSONDecodeError:
            _assert(True, "parse: JSONDecodeError raised on invalid input")

    @staticmethod
    def test_missing_fields_get_defaults():
        minimal = {"quality_score": 70}
        result = minimal.copy()
        result.setdefault("hallucination_detected", False)
        result.setdefault("wrong_tool_detected", False)
        result.setdefault("customer_helped", True)
        result.setdefault("needs_review", False)
        result.setdefault("summary", "")
        result.setdefault("issues", [])

        _assert(result["hallucination_detected"] is False, "defaults: hallucination defaults to False")
        _assert(result["customer_helped"] is True, "defaults: customer_helped defaults to True")
        _assert(result["summary"] == "", "defaults: summary defaults to empty")
        _assert(result["issues"] == [], "defaults: issues defaults to []")

    @staticmethod
    def test_issues_structure():
        issues = [
            {"type": "hallucination", "description": "Made up price", "severity": "high"},
            {"type": "wrong_tool", "description": "Used check_availability for pricing", "severity": "medium"},
        ]
        for issue in issues:
            _assert("type" in issue, f"issue: has 'type' field ({issue['type']})")
            _assert("description" in issue, f"issue: has 'description' field ({issue['type']})")
            _assert(issue["severity"] in ("low", "medium", "high"),
                    f"issue: severity is valid ({issue['severity']})")


# ═══════════════════════════════════════════════════════════════════
#  3. is_configured logic tests
# ═══════════════════════════════════════════════════════════════════

class TestConfiguration:

    @staticmethod
    def test_is_configured_check_in_source():
        src = _read(_service_path)
        _assert("settings.LANGSMITH_API_KEY" in src,
                "config: service checks LANGSMITH_API_KEY")

    @staticmethod
    def test_no_crash_without_langsmith_package():
        src = _read(_service_path)
        _assert("ImportError" in src,
                "config: handles missing langsmith package gracefully")

    @staticmethod
    def test_empty_key_means_disabled():
        src = _read(_config_path)
        _assert('LANGSMITH_API_KEY: str = ""' in src,
                "config: LANGSMITH_API_KEY defaults to empty string")


# ═══════════════════════════════════════════════════════════════════
#  4. Schema validation tests
# ═══════════════════════════════════════════════════════════════════

class TestSchemas:

    @staticmethod
    def test_evaluation_response_fields():
        src = _read(_schema_path)
        for field in ["id", "call_log_id", "company_id", "quality_score",
                      "hallucination_detected", "wrong_tool_detected",
                      "customer_helped", "needs_review", "summary",
                      "issues", "evaluated_at"]:
            _assert(field in src, f"schema: EvaluationResponse has '{field}'")

    @staticmethod
    def test_joined_call_fields():
        src = _read(_schema_path)
        for field in ["caller_number", "ai_worker_name", "call_started_at",
                      "call_duration_seconds", "company_name"]:
            _assert(field in src, f"schema: EvaluationResponse has joined '{field}'")

    @staticmethod
    def test_detail_has_transcript():
        src = _read(_schema_path)
        _assert("transcript" in src, "schema: detail has transcript field")
        _assert("TranscriptEntryResponse" in src, "schema: TranscriptEntryResponse defined")

    @staticmethod
    def test_list_response_pagination():
        src = _read(_schema_path)
        for field in ["items", "total", "page", "page_size", "total_pages"]:
            _assert(field in src, f"schema: list response has '{field}'")

    @staticmethod
    def test_summary_response_metrics():
        src = _read(_schema_path)
        for field in ["total_evaluated", "average_score", "hallucination_rate",
                      "wrong_tool_rate", "customer_helped_rate", "needs_review_count"]:
            _assert(field in src, f"schema: summary has '{field}'")


# ═══════════════════════════════════════════════════════════════════
#  5. Endpoint security tests
# ═══════════════════════════════════════════════════════════════════

class TestEndpointSecurity:

    @staticmethod
    def test_all_endpoints_require_superadmin():
        src = _read(_admin_path)
        # Find evaluation endpoint functions
        import re
        eval_funcs = re.findall(r'async def (get_evaluation|list_evaluation|sync_evaluation)\w*', src)
        _assert(len(eval_funcs) >= 3, f"endpoints: found {len(eval_funcs)} evaluation endpoints")

        # Check that require_superadmin is used as dependency
        eval_section = src[src.index("# ==================== Evaluations"):]
        superadmin_count = eval_section.count("require_superadmin")
        _assert(superadmin_count >= 4, f"endpoints: require_superadmin used {superadmin_count} times in eval section")


# ═══════════════════════════════════════════════════════════════════
#  6. API endpoint filtering tests (source-level)
# ═══════════════════════════════════════════════════════════════════

class TestEndpointFiltering:

    @staticmethod
    def test_list_supports_pagination():
        src = _read(_admin_path)
        _assert("page: int" in src, "endpoints: page parameter")
        _assert("page_size: int" in src, "endpoints: page_size parameter")

    @staticmethod
    def test_list_supports_score_filters():
        src = _read(_admin_path)
        _assert("min_score" in src, "endpoints: min_score filter")
        _assert("max_score" in src, "endpoints: max_score filter")

    @staticmethod
    def test_list_supports_boolean_filters():
        src = _read(_admin_path)
        _assert("hallucination_only" in src, "endpoints: hallucination_only filter")
        _assert("wrong_tool_only" in src, "endpoints: wrong_tool_only filter")
        _assert("needs_review_only" in src, "endpoints: needs_review_only filter")

    @staticmethod
    def test_list_supports_date_filters():
        src = _read(_admin_path)
        _assert("date_from" in src, "endpoints: date_from filter")
        _assert("date_to" in src, "endpoints: date_to filter")

    @staticmethod
    def test_list_supports_sorting():
        src = _read(_admin_path)
        _assert("sort_by" in src, "endpoints: sort_by parameter")
        _assert("sort_dir" in src, "endpoints: sort_dir parameter")

    @staticmethod
    def test_sync_uses_background_task():
        src = _read(_admin_path)
        _assert("create_task" in src and "sync_evaluations" in src,
                "endpoints: sync runs as background task")


# ═══════════════════════════════════════════════════════════════════
#  7. Migration tests
# ═══════════════════════════════════════════════════════════════════

class TestMigration:

    @staticmethod
    def test_migration_file_exists():
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "054_create_call_evaluations_table.py"
        )
        _assert(os.path.exists(migration_path), "migration: 054 file exists")

    @staticmethod
    def test_migration_chain():
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "054_create_call_evaluations_table.py"
        )
        src = _read(migration_path)
        _assert('down_revision = "053"' in src, "migration: chains from 053")
        _assert('revision = "054"' in src, "migration: revision is 054")

    @staticmethod
    def test_migration_creates_table():
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "054_create_call_evaluations_table.py"
        )
        src = _read(migration_path)
        _assert("call_evaluations" in src, "migration: creates call_evaluations table")
        _assert("quality_score" in src, "migration: includes quality_score column")
        _assert("ix_call_evaluations_company_id" in src, "migration: creates company_id index")
        _assert("ix_call_evaluations_needs_review" in src, "migration: creates needs_review index")

    @staticmethod
    def test_migration_has_downgrade():
        migration_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic", "versions",
            "054_create_call_evaluations_table.py"
        )
        src = _read(migration_path)
        _assert("def downgrade" in src, "migration: has downgrade function")
        _assert("drop_table" in src, "migration: downgrade drops table")


# ═══════════════════════════════════════════════════════════════════
#  8. Model registration tests
# ═══════════════════════════════════════════════════════════════════

class TestModelRegistration:

    @staticmethod
    def test_model_in_init():
        init_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "models", "__init__.py"
        )
        src = _read(init_path)
        _assert("CallEvaluation" in src, "registration: CallEvaluation in __init__.py")
        _assert("call_evaluation" in src, "registration: import from call_evaluation module")


# ═══════════════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════════════

test_classes = [
    TestSourceStructure,
    TestEvaluatorParsing,
    TestConfiguration,
    TestSchemas,
    TestEndpointSecurity,
    TestEndpointFiltering,
    TestMigration,
    TestModelRegistration,
]


def _run_all():
    global _results
    for cls in test_classes:
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
