"""
klantenservice.ai - Voice Constants

ElevenLabs voice metadata for both admin and customer endpoints.
All voices support TTS previews and Conversational AI.
"""

# ElevenLabs voices available for customers
# IDs marked as "PLACEHOLDER" need to be replaced with real ElevenLabs voice IDs
ELEVENLABS_VOICES = [
    {"id": "eWptEH99Zco26MHjMz5g", "name": "Bella", "description": "Vriendelijk en professioneel", "gender": "female"},
    {"id": "PLACEHOLDER_ARJEN", "name": "Arjen", "description": "Kalm en betrouwbaar", "gender": "male"},
    {"id": "PLACEHOLDER_THOMAS", "name": "Thomas", "description": "Natuurlijk en professioneel", "gender": "male"},
    {"id": "PLACEHOLDER_ERIC", "name": "Eric", "description": "Natuurlijk en authentiek", "gender": "male"},
    {"id": "PLACEHOLDER_MARLIES", "name": "Marlies", "description": "Vriendelijk en warm", "gender": "female"},
    {"id": "PLACEHOLDER_NOA", "name": "Noa", "description": "Jong en modern", "gender": "female"},
]

# All ElevenLabs voices support TTS — no filtering needed
TTS_SUPPORTED_VOICES = {v["id"] for v in ELEVENLABS_VOICES}

# Customer-visible voices (all of them — all support TTS previews)
CUSTOMER_VOICES = ELEVENLABS_VOICES

# Default voice ID (Bella)
DEFAULT_VOICE_ID = "eWptEH99Zco26MHjMz5g"

# Sample text for voice previews
VOICE_SAMPLE_TEXT = (
    "Goedemiddag, u spreekt met de klantenservice. "
    "Waarmee kan ik u vandaag helpen?"
)

# ── Legacy aliases for backward compatibility ──
# Some code may still reference OPENAI_VOICES
OPENAI_VOICES = ELEVENLABS_VOICES
