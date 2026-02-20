"""
klantenservice.ai - Voice Constants

ElevenLabs voice metadata for both admin and customer endpoints.
All voices support TTS previews and Conversational AI.
"""

# ElevenLabs voices available for customers
# IDs marked as "PLACEHOLDER" need to be replaced with real ElevenLabs voice IDs
ELEVENLABS_VOICES = [
    {"id": "OlBRrVAItyi00MuGMbna", "name": "Emma", "description": "Vriendelijk en professioneel", "gender": "female"},
    {"id": "XWw6BayktH5jsnELw9Bc", "name": "Arjen", "description": "Kalm en betrouwbaar", "gender": "male"},
    {"id": "tvFp0BgJPrEXGoDhDIA4", "name": "Thomas", "description": "Natuurlijk en professioneel", "gender": "male"},
    {"id": "AVIlLDn2TVmdaDycgbo3", "name": "Eric", "description": "Natuurlijk en authentiek", "gender": "male"},
    {"id": "mNOlrB5V39qx4wQwSjG3", "name": "Marlies", "description": "Vriendelijk en warm", "gender": "female"},
    {"id": "94W4cf0CMSgymY1uoRiX", "name": "Noa", "description": "Jong en modern", "gender": "female"},
]

# All ElevenLabs voices support TTS — no filtering needed
TTS_SUPPORTED_VOICES = {v["id"] for v in ELEVENLABS_VOICES}

# Customer-visible voices (all of them — all support TTS previews)
CUSTOMER_VOICES = ELEVENLABS_VOICES

# Default voice ID (Emma)
DEFAULT_VOICE_ID = "OlBRrVAItyi00MuGMbna"

# Sample text for voice previews
VOICE_SAMPLE_TEXT = (
    "Goedemiddag, u spreekt met de klantenservice. "
    "Waarmee kan ik u vandaag helpen?"
)

# ── Legacy aliases for backward compatibility ──
# Some code may still reference OPENAI_VOICES
OPENAI_VOICES = ELEVENLABS_VOICES
