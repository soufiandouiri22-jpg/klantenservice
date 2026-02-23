"""
klantenservice.ai - API v1 Router
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    companies,
    users,
    ai_workers,
    phone_numbers,
    calendars,
    crm,
    websites,
    training,
    calls,
    appointments,
    notes,
    dashboard,
    webhooks,
    admin,
    payments,
    search,
    notifications,
    kvk,
    elevenlabs_tools,
)

api_router = APIRouter()

# Authentication
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authenticatie"]
)

# Dashboard
api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Dashboard"]
)

# Companies (Admin only)
api_router.include_router(
    companies.router,
    prefix="/companies",
    tags=["Bedrijven"]
)

# Users
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Gebruikers"]
)

# AI Workers
api_router.include_router(
    ai_workers.router,
    prefix="/ai-workers",
    tags=["AI-medewerkers"]
)

# Phone Numbers
api_router.include_router(
    phone_numbers.router,
    prefix="/phone-numbers",
    tags=["Telefoonnummers"]
)

# Calendar Integrations
api_router.include_router(
    calendars.router,
    prefix="/calendars",
    tags=["Agenda's"]
)

# CRM Integrations
api_router.include_router(
    crm.router,
    prefix="/crm",
    tags=["CRM"]
)

# Website Knowledge
api_router.include_router(
    websites.router,
    prefix="/websites",
    tags=["Website-kennis"]
)

# Training
api_router.include_router(
    training.router,
    prefix="/training",
    tags=["Training"]
)

# Call Logs
api_router.include_router(
    calls.router,
    prefix="/calls",
    tags=["Gesprekken"]
)

# Appointments
api_router.include_router(
    appointments.router,
    prefix="/appointments",
    tags=["Afspraken"]
)

# Internal Notes
api_router.include_router(
    notes.router,
    prefix="/notes",
    tags=["Notities"]
)

# Webhooks (for telephony, calendar sync, etc.)
api_router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["Webhooks"]
)

# Admin (Platform-wide settings, superadmin only)
api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"]
)

# Payments (Stripe)
api_router.include_router(
    payments.router,
    prefix="/payments",
    tags=["Betalingen"]
)

# Global Search
api_router.include_router(
    search.router,
    prefix="/search",
    tags=["Zoeken"]
)

# Notifications
api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notificaties"]
)

# KVK (Kamer van Koophandel) & BTW Validatie
api_router.include_router(
    kvk.router,
    prefix="/kvk",
    tags=["KVK"]
)

# ElevenLabs Server Tools (webhook endpoints for Conversational AI)
api_router.include_router(
    elevenlabs_tools.router,
    prefix="/elevenlabs/tools",
    tags=["ElevenLabs Tools"]
)
