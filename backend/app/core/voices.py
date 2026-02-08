"""
klantenservice.ai - Voice Constants

Shared voice metadata and TTS support info used by both admin and customer endpoints.
"""

# All OpenAI Realtime voices with metadata
OPENAI_VOICES = [
    {"id": "alloy", "name": "Alloy", "description": "Neutraal en veelzijdig", "gender": "neutral"},
    {"id": "ash", "name": "Ash", "description": "Warm en kalm", "gender": "male"},
    {"id": "ballad", "name": "Ballad", "description": "Zacht en expressief", "gender": "male"},
    {"id": "coral", "name": "Coral", "description": "Helder en vriendelijk", "gender": "female"},
    {"id": "echo", "name": "Echo", "description": "Diep en professioneel", "gender": "male"},
    {"id": "sage", "name": "Sage", "description": "Warm en autoritair", "gender": "female"},
    {"id": "shimmer", "name": "Shimmer", "description": "Licht en energiek", "gender": "female"},
    {"id": "verse", "name": "Verse", "description": "Dynamisch en levendig", "gender": "male"},
    {"id": "cedar", "name": "Cedar", "description": "Rustig en betrouwbaar", "gender": "male"},
    {"id": "marin", "name": "Marin", "description": "Helder en professioneel", "gender": "female"},
]

# Voices that support the TTS API for previews (others are Realtime-only)
TTS_SUPPORTED_VOICES = {"alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}

# Only voices customers can see and select (must be previewable)
CUSTOMER_VOICES = [v for v in OPENAI_VOICES if v["id"] in TTS_SUPPORTED_VOICES]

# Sample text for voice previews
VOICE_SAMPLE_TEXT = (
    "Goedemiddag, u spreekt met de klantenservice. "
    "Waarmee kan ik u vandaag helpen?"
)
