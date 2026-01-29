"""
klantenservice.ai - Pydantic Schemas
"""
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserLogin, Token
from app.schemas.ai_worker import AIWorkerCreate, AIWorkerUpdate, AIWorkerResponse
from app.schemas.phone_number import PhoneNumberCreate, PhoneNumberUpdate, PhoneNumberResponse
from app.schemas.calendar import CalendarIntegrationCreate, CalendarIntegrationResponse, AvailabilitySlot
from app.schemas.website import WebsiteKnowledgeCreate, WebsiteKnowledgeResponse, TestQuestionRequest
from app.schemas.training import TrainingRuleUpdate, ExampleAnswerCreate, ExampleAnswerResponse
from app.schemas.call_log import CallLogResponse, CallTranscriptResponse
from app.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.schemas.note import InternalNoteCreate, InternalNoteResponse

__all__ = [
    "CompanyCreate", "CompanyUpdate", "CompanyResponse",
    "UserCreate", "UserUpdate", "UserResponse", "UserLogin", "Token",
    "AIWorkerCreate", "AIWorkerUpdate", "AIWorkerResponse",
    "PhoneNumberCreate", "PhoneNumberUpdate", "PhoneNumberResponse",
    "CalendarIntegrationCreate", "CalendarIntegrationResponse", "AvailabilitySlot",
    "WebsiteKnowledgeCreate", "WebsiteKnowledgeResponse", "TestQuestionRequest",
    "TrainingRuleUpdate", "ExampleAnswerCreate", "ExampleAnswerResponse",
    "CallLogResponse", "CallTranscriptResponse",
    "AppointmentCreate", "AppointmentResponse",
    "InternalNoteCreate", "InternalNoteResponse",
]
