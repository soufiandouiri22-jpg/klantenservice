"""
klantenservice.ai - ElevenLabs Server Tool Endpoints

Webhook endpoints called by ElevenLabs Conversational AI when the agent
needs to execute a tool (search_knowledge, book_appointment, etc.).

ElevenLabs sends POST requests with tool parameters in the JSON body.
Dynamic variables (company_id, ai_worker_id, etc.) are injected as
top-level fields in the body when configured with the `dynamic_variable`
property in each tool's parameter schema on the ElevenLabs dashboard.

Every tool invocation runs the policy engine's auto-checks (escalation,
off-topic, silence, repeated failure). If a policy blocks the action,
the override is returned instead of the normal tool result.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.orchestrator import _run_tool
from app.services.call_tools import run_auto_policies, apply_output_guardrails

logger = logging.getLogger(__name__)

router = APIRouter()

CONTEXT_FIELDS = {
    "company_id",
    "ai_worker_id",
    "call_log_id",
    "customer_phone",
    "company_name",
    "calendar_id",
    "call_sid",
}

# Tools that skip auto-policy (check_policy handles its own logic)
_SKIP_AUTO_POLICY = {"check_policy"}


def _get_db() -> Session:
    return SessionLocal()


def _extract_company_context(data: dict) -> Dict[str, Any]:
    """Extract company context from ElevenLabs tool request body."""
    company_id = data.get("company_id", "")
    ai_worker_id = data.get("ai_worker_id")
    call_log_id = data.get("call_log_id")
    customer_phone = data.get("customer_phone")
    calendar_id = data.get("calendar_id")
    call_sid = data.get("call_sid")

    if not company_id:
        dv = data.get("dynamic_variables", {})
        if isinstance(dv, dict):
            company_id = dv.get("company_id", company_id)
            ai_worker_id = ai_worker_id or dv.get("ai_worker_id")
            call_log_id = call_log_id or dv.get("call_log_id")
            customer_phone = customer_phone or dv.get("customer_phone")
            calendar_id = calendar_id or dv.get("calendar_id")
            call_sid = call_sid or dv.get("call_sid")

    return {
        "company_id": company_id,
        "ai_worker_id": ai_worker_id,
        "call_log_id": call_log_id,
        "customer_phone": customer_phone,
        "calendar_id": calendar_id,
        "call_sid": call_sid,
    }


async def _handle_tool(request: Request, tool_name: str) -> JSONResponse:
    """
    Generic handler for all ElevenLabs server tool calls.

    1. Extracts context + arguments
    2. Runs auto-policy checks (unless the tool is check_policy itself)
    3. If a policy blocks, returns the override immediately
    4. Otherwise executes the tool normally
    """
    db = _get_db()
    try:
        data = await request.json()
        logger.info("[ElevenLabs Tool] %s incoming keys=%s", tool_name, list(data.keys()))

        ctx = _extract_company_context(data)
        logger.info("[ElevenLabs Tool] %s company=%s call_sid=%s",
                     tool_name, ctx["company_id"], ctx.get("call_sid"))

        context = {
            "db": db,
            "company_id": ctx["company_id"],
            "ai_worker_id": ctx.get("ai_worker_id"),
            "call_log_id": ctx.get("call_log_id"),
            "customer_phone": ctx.get("customer_phone"),
            "calendar_id": ctx.get("calendar_id"),
            "call_sid": ctx.get("call_sid"),
        }

        arguments = {
            k: v
            for k, v in data.items()
            if k not in CONTEXT_FIELDS and k != "dynamic_variables"
        }

        customer_msg = arguments.get("query", "") or arguments.get("customer_message", "")

        # ── Auto-policy check on every tool call ──
        if tool_name not in _SKIP_AUTO_POLICY and ctx.get("call_sid"):
            override = run_auto_policies(
                db=db,
                company_id=ctx["company_id"],
                call_sid=ctx["call_sid"],
                call_log_id=ctx.get("call_log_id"),
                tool_name=tool_name,
                customer_message=customer_msg,
            )
            if override:
                logger.info("[ElevenLabs Tool] %s POLICY OVERRIDE: %s",
                            tool_name, override.get("reason_code"))
                return JSONResponse(content=override)

        # ── Normal tool execution ──
        result = await _run_tool(tool_name, arguments, context)

        # ── Post-retrieval low-confidence policy check ──
        top_score = result.get("top_retrieval_score")
        if (
            top_score is not None
            and ctx.get("call_sid")
            and tool_name in ("search_knowledge", "get_prices")
        ):
            lc_override = run_auto_policies(
                db=db,
                company_id=ctx["company_id"],
                call_sid=ctx["call_sid"],
                call_log_id=ctx.get("call_log_id"),
                tool_name=f"{tool_name}_confidence",
                customer_message=customer_msg,
                retrieval_confidence=float(top_score),
            )
            if lc_override:
                result["low_confidence_override"] = lc_override
                result["low_confidence_detected"] = True

        # ── Output guardrails ──
        result = apply_output_guardrails(
            db=db,
            call_sid=ctx.get("call_sid"),
            call_log_id=ctx.get("call_log_id"),
            company_id=ctx.get("company_id"),
            tool_result=result,
        )

        logger.info("[ElevenLabs Tool] %s ok=%s", tool_name, result.get("ok"))
        return JSONResponse(content=result)

    except Exception as e:
        logger.error("[ElevenLabs Tool] %s error: %s", tool_name, e, exc_info=True)
        return JSONResponse(
            content={"ok": False, "message": f"Tool error: {str(e)}"},
            status_code=500,
        )
    finally:
        db.close()


# ── Endpoints ──────────────────────────────────────────────────────

@router.post("/search_knowledge")
async def ep_search_knowledge(request: Request):
    return await _handle_tool(request, "search_knowledge")


@router.post("/check_availability")
async def ep_check_availability(request: Request):
    return await _handle_tool(request, "check_availability")


@router.post("/book_appointment")
async def ep_book_appointment(request: Request):
    return await _handle_tool(request, "book_appointment")


@router.post("/get_prices")
async def ep_get_prices(request: Request):
    return await _handle_tool(request, "search_knowledge")


@router.post("/create_note")
async def ep_create_note(request: Request):
    return await _handle_tool(request, "create_note")


@router.post("/flag_unknown")
async def ep_flag_unknown(request: Request):
    return await _handle_tool(request, "flag_unknown")


@router.post("/transfer_call")
async def ep_transfer_call(request: Request):
    return await _handle_tool(request, "transfer_call")


@router.post("/check_policy")
async def ep_check_policy(request: Request):
    """
    Policy engine tool — called by the AI before gated actions
    (ending call, escalation, etc.).
    """
    return await _handle_tool(request, "check_policy")
