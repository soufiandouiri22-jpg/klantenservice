"""
klantenservice.ai - Public Contact Form Endpoint
"""
import logging
from pydantic import BaseModel, EmailStr
from typing import Optional
from fastapi import APIRouter, HTTPException

from app.core.email import send_contact_form_email

logger = logging.getLogger(__name__)
router = APIRouter()


class ContactFormRequest(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    phone: Optional[str] = None
    subject: str = "Algemene vraag"
    message: str


@router.post("/submit")
async def submit_contact_form(data: ContactFormRequest):
    """
    Public endpoint for the contact form. Sends an email to the team.
    No authentication required.
    """
    success = send_contact_form_email(
        sender_name=data.name,
        sender_email=data.email,
        company=data.company,
        phone=data.phone,
        subject=data.subject,
        message=data.message,
    )

    if not success:
        raise HTTPException(status_code=500, detail="Kon bericht niet verzenden")

    return {"ok": True, "message": "Bericht verzonden"}
