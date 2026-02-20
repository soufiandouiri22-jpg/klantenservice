"""
klantenservice.ai - Services
"""
from app.services.openai_realtime_service import build_system_instructions
from app.services.question_detector import (
    QuestionDetectorService,
    analyze_call_transcript,
)

__all__ = [
    "build_system_instructions",
    "QuestionDetectorService",
    "analyze_call_transcript",
]
