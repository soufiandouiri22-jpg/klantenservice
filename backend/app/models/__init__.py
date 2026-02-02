"""
klantenservice.ai - Database Models
"""
from app.models.company import Company
from app.models.user import User, OAuthProvider
from app.models.ai_worker import AIWorker
from app.models.phone_number import PhoneNumber
from app.models.calendar_integration import CalendarIntegration
from app.models.website_knowledge import WebsiteKnowledge, KnowledgeChunk
from app.models.training import TrainingRule, ExampleAnswer
from app.models.system_prompt import SystemPrompt
from app.models.call_log import CallLog, CallTranscript
from app.models.appointment import Appointment
from app.models.internal_note import InternalNote

__all__ = [
    "Company",
    "User",
    "OAuthProvider",
    "AIWorker",
    "PhoneNumber",
    "CalendarIntegration",
    "WebsiteKnowledge",
    "KnowledgeChunk",
    "TrainingRule",
    "ExampleAnswer",
    "SystemPrompt",
    "CallLog",
    "CallTranscript",
    "Appointment",
    "InternalNote",
]
