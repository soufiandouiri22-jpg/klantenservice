"""
klantenservice.ai - LangSmith Evaluation Service

Hybrid evaluation: GPT-4o-mini evaluator scores transcripts,
results are cached locally, traces + feedback are logged to LangSmith.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.call_log import CallLog, CallTranscript, CallStatus
from app.models.call_evaluation import CallEvaluation

logger = logging.getLogger(__name__)

_EVALUATOR_MODEL = "gpt-4o-mini"

_EVALUATOR_SYSTEM_PROMPT = """\
Je bent een kwaliteitsbeoordelaar voor AI-telefoongesprekken van een klantenservice-platform.

Analyseer het volgende gesprekstranscript en de gebruikte tools, en beoordeel de kwaliteit.

Beantwoord in exact dit JSON-formaat (geen markdown, geen extra tekst):

{
  "quality_score": <integer 0-100>,
  "hallucination_detected": <true|false>,
  "wrong_tool_detected": <true|false>,
  "customer_helped": <true|false>,
  "needs_review": <true|false>,
  "summary": "<korte samenvatting in het Nederlands, max 2 zinnen>",
  "issues": [
    {"type": "<hallucination|wrong_tool|off_topic|policy_violation|incomplete_answer>", "description": "<beschrijving>", "severity": "<low|medium|high>"}
  ]
}

Beoordelingscriteria:
- quality_score: 0-100 gebaseerd op correctheid, behulpzaamheid, professionaliteit, gesprekskwaliteit
- hallucination_detected: true als de AI informatie verzon die niet in de kennisbank zit
- wrong_tool_detected: true als de AI een verkeerde tool gebruikte of een onnodige tool aanriep
- customer_helped: true als het probleem van de klant is opgelost of de klant correct is doorverwezen
- needs_review: true als er een ernstig probleem is dat menselijke aandacht vereist
- issues: lijst van specifieke problemen (leeg als er geen zijn)

Wees streng maar eerlijk. Een normaal goed gesprek scoort 70-85. Perfecte gesprekken 85-100.
Korte gesprekken waar de klant snel geholpen is, zijn niet automatisch slecht."""


def is_configured() -> bool:
    return bool(settings.LANGSMITH_API_KEY)


def _get_langsmith_client():
    """Return a LangSmith Client or None if not configured."""
    if not settings.LANGSMITH_API_KEY:
        return None
    try:
        from langsmith import Client
        return Client(
            api_key=settings.LANGSMITH_API_KEY,
            api_url=settings.LANGSMITH_ENDPOINT,
        )
    except ImportError:
        logger.warning("[EVAL] langsmith package not installed — skipping LangSmith integration")
        return None
    except Exception as e:
        logger.warning("[EVAL] Failed to create LangSmith client: %s", e)
        return None


def _build_transcript_text(transcripts: List[CallTranscript]) -> str:
    lines = []
    for t in transcripts:
        label = "Klant" if t.speaker == "caller" else "AI"
        if t.message and t.message.strip():
            lines.append(f"{label}: {t.message.strip()}")
    return "\n".join(lines)


def _extract_tool_usage(transcripts: List[CallTranscript]) -> List[Dict[str, Any]]:
    tools = []
    for t in transcripts:
        if t.tool_calls and isinstance(t.tool_calls, list):
            for tc in t.tool_calls:
                tools.append(tc if isinstance(tc, dict) else {"tool": str(tc)})
    return tools


async def _run_gpt_evaluator(
    transcript_text: str,
    tool_calls: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Run GPT-4o-mini to evaluate a call transcript. Returns parsed JSON or None."""
    if not settings.OPENAI_API_KEY:
        logger.warning("[EVAL] OPENAI_API_KEY not set — skipping evaluation")
        return None

    if not transcript_text or not transcript_text.strip():
        return None

    user_content = f"TRANSCRIPT:\n{transcript_text}"
    if tool_calls:
        user_content += f"\n\nTOOLS GEBRUIKT:\n{json.dumps(tool_calls, default=str, ensure_ascii=False)}"

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model=_EVALUATOR_MODEL,
            temperature=0,
            max_tokens=500,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _EVALUATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )

        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)

        score = result.get("quality_score")
        if not isinstance(score, (int, float)) or not (0 <= score <= 100):
            logger.warning("[EVAL] Invalid quality_score: %s", score)
            return None

        result["quality_score"] = int(score)
        result.setdefault("hallucination_detected", False)
        result.setdefault("wrong_tool_detected", False)
        result.setdefault("customer_helped", True)
        result.setdefault("needs_review", False)
        result.setdefault("summary", "")
        result.setdefault("issues", [])

        return result

    except json.JSONDecodeError as e:
        logger.warning("[EVAL] GPT returned invalid JSON: %s", e)
        return None
    except Exception as e:
        logger.warning("[EVAL] GPT evaluator failed: %s", e)
        return None


def _log_to_langsmith(
    client,
    call_log: CallLog,
    transcript_text: str,
    tool_calls: List[Dict[str, Any]],
    eval_result: Dict[str, Any],
) -> Optional[str]:
    """Log trace + feedback to LangSmith. Returns run_id or None."""
    if not client:
        return None

    try:
        run_id = uuid4()
        client.create_run(
            id=run_id,
            project_name=settings.LANGSMITH_PROJECT,
            name=f"call-{call_log.id}",
            run_type="chain",
            inputs={
                "call_id": str(call_log.id),
                "caller_number": call_log.caller_number or "",
                "transcript": transcript_text[:5000],
                "tools_used": tool_calls,
            },
            outputs={
                "quality_score": eval_result.get("quality_score"),
                "summary": eval_result.get("summary", ""),
                "hallucination": eval_result.get("hallucination_detected", False),
                "wrong_tool": eval_result.get("wrong_tool_detected", False),
                "customer_helped": eval_result.get("customer_helped", True),
            },
            start_time=call_log.started_at or datetime.utcnow(),
            end_time=call_log.ended_at or datetime.utcnow(),
        )

        _feedback_keys = {
            "quality_score": ("quality_score", lambda v: v / 100.0),
            "hallucination": ("hallucination_detected", lambda v: 0.0 if v else 1.0),
            "wrong_tool": ("wrong_tool_detected", lambda v: 0.0 if v else 1.0),
            "customer_helped": ("customer_helped", lambda v: 1.0 if v else 0.0),
        }

        for fb_key, (result_key, transform) in _feedback_keys.items():
            try:
                val = eval_result.get(result_key)
                if val is not None:
                    client.create_feedback(
                        run_id=run_id,
                        key=fb_key,
                        score=transform(val),
                        comment=eval_result.get("summary", ""),
                    )
            except Exception as e:
                logger.debug("[EVAL] Failed to log feedback '%s': %s", fb_key, e)

        logger.info("[EVAL] Logged to LangSmith: run_id=%s call=%s", run_id, call_log.id)
        return str(run_id)

    except Exception as e:
        logger.warning("[EVAL] LangSmith logging failed (non-blocking): %s", e)
        return None


async def evaluate_call(db: Session, call_log: CallLog) -> Optional[CallEvaluation]:
    """
    Full evaluation pipeline for a single call.
    1. Build transcript text + extract tool usage
    2. Run GPT evaluator
    3. Log trace + feedback to LangSmith (non-blocking)
    4. Store CallEvaluation in DB
    """
    existing = db.query(CallEvaluation).filter(
        CallEvaluation.call_log_id == call_log.id
    ).first()
    if existing:
        logger.info("[EVAL] Evaluation already exists for call %s", call_log.id)
        return existing

    transcripts = db.query(CallTranscript).filter(
        CallTranscript.call_log_id == call_log.id
    ).order_by(CallTranscript.timestamp).all()

    if not transcripts:
        logger.info("[EVAL] No transcript records for call %s — skipping", call_log.id)
        return None

    transcript_text = _build_transcript_text(transcripts)
    if not transcript_text.strip():
        return None

    tool_calls = _extract_tool_usage(transcripts)

    eval_result = await _run_gpt_evaluator(transcript_text, tool_calls)
    if not eval_result:
        return None

    ls_client = _get_langsmith_client()
    run_id = _log_to_langsmith(ls_client, call_log, transcript_text, tool_calls, eval_result)

    evaluation = CallEvaluation(
        id=uuid4(),
        call_log_id=call_log.id,
        company_id=call_log.company_id,
        quality_score=eval_result["quality_score"],
        hallucination_detected=bool(eval_result.get("hallucination_detected", False)),
        wrong_tool_detected=bool(eval_result.get("wrong_tool_detected", False)),
        customer_helped=bool(eval_result.get("customer_helped", True)),
        needs_review=bool(eval_result.get("needs_review", False)),
        summary=eval_result.get("summary", ""),
        issues=eval_result.get("issues", []),
        tool_usage=tool_calls,
        langsmith_run_id=run_id,
        evaluator_model=_EVALUATOR_MODEL,
        evaluated_at=datetime.utcnow(),
    )

    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    logger.info(
        "[EVAL] Evaluated call %s: score=%d hallucination=%s wrong_tool=%s helped=%s review=%s",
        call_log.id, evaluation.quality_score, evaluation.hallucination_detected,
        evaluation.wrong_tool_detected, evaluation.customer_helped, evaluation.needs_review,
    )

    return evaluation


async def sync_evaluations(
    db: Session,
    company_id: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, int]:
    """
    Batch evaluate calls that don't have evaluations yet.
    Returns counts of evaluated and skipped calls.
    """
    from sqlalchemy import not_, exists

    query = db.query(CallLog).filter(
        CallLog.status == CallStatus.COMPLETED,
        CallLog.duration_seconds > 5,
        ~exists().where(CallEvaluation.call_log_id == CallLog.id),
    )

    if company_id:
        query = query.filter(CallLog.company_id == company_id)

    calls = query.order_by(CallLog.started_at.desc()).limit(limit).all()

    evaluated = 0
    skipped = 0

    for call_log in calls:
        try:
            result = await evaluate_call(db, call_log)
            if result:
                evaluated += 1
            else:
                skipped += 1
        except Exception as e:
            logger.warning("[EVAL] Sync failed for call %s: %s", call_log.id, e)
            skipped += 1

    logger.info("[EVAL] Sync complete: evaluated=%d skipped=%d total=%d", evaluated, skipped, len(calls))
    return {"evaluated": evaluated, "skipped": skipped, "total": len(calls)}
