"""
klantenservice.ai - ElevenLabs Server Tool Endpoints

Webhook endpoints called by ElevenLabs Conversational AI when the agent
needs to execute a tool (search_knowledge, book_appointment, etc.).

ElevenLabs sends POST requests with tool parameters in the JSON body.
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


def _get_db() -> Session:
    """Create a database session for tool execution."""
    return SessionLocal()


def _extract_company_context(data: dict) -> Dict[str, Any]:
    """
    Extract company context from ElevenLabs dynamic variables.
    
    ElevenLabs passes dynamic_variables set during register_call.
    We use these to identify the company and AI worker for tool execution.
    """
    # Dynamic variables are passed in the request body
    dynamic_vars = data.get("dynamic_variables", {})
    
    return {
        "company_id": dynamic_vars.get("company_id", ""),
        "ai_worker_id": dynamic_vars.get("ai_worker_id"),
        "call_log_id": dynamic_vars.get("call_log_id"),
        "customer_phone": dynamic_vars.get("customer_phone"),
        "calendar_id": dynamic_vars.get("calendar_id"),
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
        logger.info(f"[ElevenLabs Tool] {tool_name} called with: {data}")

        # Extract context from dynamic variables
        ctx = _extract_company_context(data)
        
        # Build the tool context dict expected by _run_tool
        context = {
            "db": db,
            "company_id": ctx["company_id"],
            "ai_worker_id": ctx.get("ai_worker_id"),
            "call_log_id": ctx.get("call_log_id"),
            "customer_phone": ctx.get("customer_phone"),
            "calendar_id": ctx.get("calendar_id"),
        }

        # Extract tool-specific arguments (everything except dynamic_variables)
        arguments = {k: v for k, v in data.items() if k != "dynamic_variables"}

        # Execute the tool
        result = _run_tool(tool_name, arguments, context)
        
        logger.info(f"[ElevenLabs Tool] {tool_name} result: {str(result)[:200]}")
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
    """ElevenLabs server tool: Get price information."""
    return await _handle_tool(request, "get_prices")


@router.post("/create_note")
async def tool_create_note(request: Request):
    """ElevenLabs server tool: Create an internal note."""
    return await _handle_tool(request, "create_note")


@router.post("/flag_unknown")
async def tool_flag_unknown(request: Request):
    """ElevenLabs server tool: Flag an unanswered question."""
    return await _handle_tool(request, "flag_unknown")
