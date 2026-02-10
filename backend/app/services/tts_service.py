"""
klantenservice.ai - TTS Service

Generates professional-sounding audio from text using OpenAI TTS API.
Caches generated audio files on disk to avoid repeated API calls for
identical messages.
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import openai

from app.core.config import settings
from app.core.voices import TTS_SUPPORTED_VOICES

logger = logging.getLogger(__name__)

# Directory for cached TTS audio files
TTS_CACHE_DIR = Path("/tmp/tts_cache")
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Default voice for system messages
DEFAULT_TTS_VOICE = "alloy"


def _cache_key(text: str, voice: str) -> str:
    """Generate a deterministic cache key from text + voice."""
    content = f"{voice}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _get_tts_voice(ai_worker_voice: Optional[str] = None) -> str:
    """
    Pick the best TTS voice. Uses the AI worker's voice if it supports TTS,
    otherwise falls back to the default.
    """
    if ai_worker_voice and ai_worker_voice in TTS_SUPPORTED_VOICES:
        return ai_worker_voice
    return DEFAULT_TTS_VOICE


def generate_tts_audio(text: str, voice: Optional[str] = None) -> Optional[str]:
    """
    Generate an MP3 audio file from text using OpenAI TTS.

    Returns the filename (relative to the cache dir) on success,
    or None if generation fails.

    Results are cached on disk — identical text+voice combinations
    are only generated once.
    """
    tts_voice = _get_tts_voice(voice)
    key = _cache_key(text, tts_voice)
    filename = f"{key}.mp3"
    filepath = TTS_CACHE_DIR / filename

    # Return cached file if it exists
    if filepath.exists() and filepath.stat().st_size > 0:
        logger.debug(f"TTS cache hit: {filename}")
        return filename

    # Generate via OpenAI TTS API
    if not settings.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured — cannot generate TTS audio")
        return None

    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.audio.speech.create(
            model="tts-1",
            voice=tts_voice,
            input=text,
            response_format="mp3",
        )

        # Write to disk
        filepath.write_bytes(response.content)
        logger.info(f"TTS generated: {filename} ({len(response.content)} bytes, voice={tts_voice})")
        return filename

    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return None


def get_tts_url(filename: str) -> str:
    """Return the public URL for a cached TTS file."""
    base = settings.WEBSOCKET_URL or ""
    # Derive the HTTP base URL from the WebSocket URL
    # wss://api.klantenservice.ai/ws/voice -> https://api.klantenservice.ai
    if base.startswith("wss://"):
        base = "https://" + base.split("//", 1)[1].split("/")[0]
    elif base.startswith("ws://"):
        base = "http://" + base.split("//", 1)[1].split("/")[0]
    else:
        # Fallback: use FRONTEND_URL's domain or localhost
        base = ""

    return f"{base}/static/tts/{filename}"
