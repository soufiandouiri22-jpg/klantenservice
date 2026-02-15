"""
klantenservice.ai - TTS Service

Generates professional-sounding audio from text using ElevenLabs TTS API.
Caches generated audio files on disk to avoid repeated API calls for
identical messages.
"""
import hashlib
import logging
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import settings
from app.core.voices import DEFAULT_VOICE_ID

logger = logging.getLogger(__name__)

# Directory for cached TTS audio files
TTS_CACHE_DIR = Path("/tmp/tts_cache")
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ElevenLabs TTS API endpoint
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


def _cache_key(text: str, voice: str) -> str:
    """Generate a deterministic cache key from text + voice."""
    content = f"{voice}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def generate_tts_audio(text: str, voice: Optional[str] = None) -> Optional[str]:
    """
    Generate an MP3 audio file from text using ElevenLabs TTS.

    Returns the filename (relative to the cache dir) on success,
    or None if generation fails.

    Results are cached on disk — identical text+voice combinations
    are only generated once.
    """
    tts_voice = voice or DEFAULT_VOICE_ID
    key = _cache_key(text, tts_voice)
    filename = f"{key}.mp3"
    filepath = TTS_CACHE_DIR / filename

    # Return cached file if it exists
    if filepath.exists() and filepath.stat().st_size > 0:
        logger.debug(f"TTS cache hit: {filename}")
        return filename

    # Generate via ElevenLabs TTS API
    if not settings.ELEVENLABS_API_KEY:
        logger.error("ELEVENLABS_API_KEY not configured — cannot generate TTS audio")
        return None

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{ELEVENLABS_TTS_URL}/{tts_voice}",
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": "eleven_turbo_v2_5",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                    },
                },
            )
            response.raise_for_status()

            # Write to disk
            filepath.write_bytes(response.content)
            logger.info(f"TTS generated: {filename} ({len(response.content)} bytes, voice={tts_voice})")
            return filename

    except Exception as e:
        logger.error(f"ElevenLabs TTS generation failed: {e}")
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
        base = ""

    return f"{base}/static/tts/{filename}"
