"""
klantenservice.ai - ElevenLabs Server Tool Endpoints

Webhook endpoints called by ElevenLabs Conversational AI when the agent
needs to execute a tool (search_knowledge, book_appointment, etc.).

ElevenLabs sends POST requests with tool parameters in the JSON body.
Dynamic variables (company_id, ai_worker_id, etc.) are injected as
top-level fields in the body when configured with the `dynamic_variable`
property in each tool's parameter schema on the ElevenLabs dashboard.

We execute the tool using the existing _run_tool infrastructure and
return the result as JSON.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.orchestrator import _run_tool

logger = logging.getLogger(__name__)

router = APIRouter()

# Field names that are context (dynamic variables), not tool arguments
CONTEXT_FIELDS = {
    "company_id",
    "ai_worker_id",
    "call_log_id",
    "customer_phone",
    "company_name",
    "calendar_id",
}


def _get_db() -> Session:
    """Create a database session for tool execution."""
    return SessionLocal()


def _extract_company_context(data: dict) -> Dict[str, Any]:
    """
    Extract company context from ElevenLabs tool request body.

    ElevenLabs injects dynamic variables as top-level fields in the
    request body when each tool parameter has `dynamic_variable` set
    in its JSON schema.  We also check the legacy `dynamic_variables`
    nested object as a fallback.
    """
    # Primary: top-level fields (set via dynamic_variable parameter property)
    company_id = data.get("company_id", "")
    ai_worker_id = data.get("ai_worker_id")
    call_log_id = data.get("call_log_id")
    customer_phone = data.get("customer_phone")
    calendar_id = data.get("calendar_id")

    # Fallback: legacy nested dynamic_variables object
    if not company_id:
        dv = data.get("dynamic_variables", {})
        if isinstance(dv, dict):
            company_id = dv.get("company_id", company_id)
            ai_worker_id = ai_worker_id or dv.get("ai_worker_id")
            call_log_id = call_log_id or dv.get("call_log_id")
            customer_phone = customer_phone or dv.get("customer_phone")
            calendar_id = calendar_id or dv.get("calendar_id")

    return {
        "company_id": company_id,
        "ai_worker_id": ai_worker_id,
        "call_log_id": call_log_id,
        "customer_phone": customer_phone,
        "calendar_id": calendar_id,
    }


async def _handle_tool(request: Request, tool_name: str) -> JSONResponse:
    """
    Generic handler for all ElevenLabs server tool calls.

    Extracts parameters from the request, builds context,
    executes the tool, and returns the result.
    """
    db = _get_db()
    try:
        data = await request.json()

        ctx = _extract_company_context(data)
        logger.debug(f"[ElevenLabs Tool] {tool_name} company={ctx['company_id']}")

        context = {
            "db": db,
            "company_id": ctx["company_id"],
            "ai_worker_id": ctx.get("ai_worker_id"),
            "call_log_id": ctx.get("call_log_id"),
            "customer_phone": ctx.get("customer_phone"),
            "calendar_id": ctx.get("calendar_id"),
        }

        arguments = {
            k: v
            for k, v in data.items()
            if k not in CONTEXT_FIELDS and k != "dynamic_variables"
        }

        result = _run_tool(tool_name, arguments, context)

        logger.info(f"[ElevenLabs Tool] {tool_name} ok={result.get('ok')}")
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"[ElevenLabs Tool] {tool_name} error: {e}", exc_info=True)
        return JSONResponse(
            content={"ok": False, "message": f"Tool error: {str(e)}"},
            status_code=500,
        )
    finally:
        db.close()


@router.post("/search_knowledge")
async def tool_search_knowledge(request: Request):
    """ElevenLabs server tool: Search company knowledge base."""
    return await _handle_tool(request, "search_knowledge")


@router.post("/check_availability")
async def tool_check_availability(request: Request):
    """ElevenLabs server tool: Check calendar availability."""
    return await _handle_tool(request, "check_availability")


@router.post("/book_appointment")
async def tool_book_appointment(request: Request):
    """ElevenLabs server tool: Book an appointment."""
    return await _handle_tool(request, "book_appointment")


@router.post("/get_prices")
async def tool_get_prices(request: Request):
    """Legacy endpoint — redirects to search_knowledge."""
    return await _handle_tool(request, "search_knowledge")


@router.post("/create_note")
async def tool_create_note(request: Request):
    """ElevenLabs server tool: Create an internal note."""
    return await _handle_tool(request, "create_note")


@router.post("/flag_unknown")
async def tool_flag_unknown(request: Request):
    """ElevenLabs server tool: Flag an unanswered question."""
    return await _handle_tool(request, "flag_unknown")
