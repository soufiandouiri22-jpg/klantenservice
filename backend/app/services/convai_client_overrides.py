"""
ElevenLabs Conversational AI — shared conversation_config_override payloads.

- Twilio register-call uses snake_case (first_message).
- @elevenlabs/react startSession expects camelCase for some fields (firstMessage).

Enable matching fields on the agent in ElevenLabs (Security → overrides) or the
API may reject unknown overrides.
"""
from __future__ import annotations

import copy
from typing import Any, Dict

from app.core.config import get_settings


def build_conversation_config_override(
    *,
    voice_id: str,
    prompt_text: str,
    first_message: str,
) -> Dict[str, Any]:
    """
    Build conversation_config_override for /v1/convai/twilio/register-call.
    Does not set TTS model (v3 conversational stays from dashboard).
    """
    settings = get_settings()

    prompt_obj: Dict[str, Any] = {"prompt": prompt_text}
    llm = (settings.ELEVENLABS_CONVAI_PROMPT_LLM or "").strip()
    if llm:
        prompt_obj["llm"] = llm

    agent: Dict[str, Any] = {
        "prompt": prompt_obj,
        "first_message": first_message,
        "language": settings.ELEVENLABS_CONVAI_LANGUAGE or "nl",
    }

    return {
        "agent": agent,
        "tts": {"voice_id": voice_id},
    }


def conversation_overrides_for_react_sdk(rest_overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Map snake_case agent fields for @elevenlabs/react (first_message → firstMessage)."""
    out = copy.deepcopy(rest_overrides)
    agent = out.get("agent")
    if isinstance(agent, dict) and "first_message" in agent:
        agent["firstMessage"] = agent.pop("first_message")
    return out
