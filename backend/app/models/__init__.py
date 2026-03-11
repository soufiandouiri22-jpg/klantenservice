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
from app.models.global_config import GlobalConfig
from app.models.usage_log import UsageLog
from app.models.latency_log import LatencyLog
from app.models.context_log import ContextLog
from app.models.crm_integration import CRMIntegration
from app.models.notification import Notification
from app.services.indexing.models import (
    IdxSite, IdxCrawlJob, IdxPage, IdxChunk, IdxError, RtvEvent, RtvResult,
)

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
    "GlobalConfig",
    "UsageLog",
    "LatencyLog",
    "ContextLog",
    "CRMIntegration",
    "Notification",
    "IdxSite",
    "IdxCrawlJob",
    "IdxPage",
    "IdxChunk",
    "IdxError",
    "RtvEvent",
    "RtvResult",
]
