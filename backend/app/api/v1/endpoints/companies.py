"""
klantenservice.ai - Company Endpoints
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.schemas.company import CompanyUpdate, CompanyResponse
from app.api.deps import get_current_user, get_current_company, require_owner, require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=CompanyResponse)
async def get_current_company_info(
    company: Company = Depends(get_current_company)
):
    """
    Get current company information.
    """
    return company


@router.patch("/me", response_model=CompanyResponse)
async def update_current_company(
    data: CompanyUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update current company information.
    Requires admin or owner role.
    """
    update_data = data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(company, field, value)
    
    # Sync BTW-nummer to Stripe when updated
    if "btw_number" in update_data and company.stripe_customer_id:
        from app.api.v1.endpoints.payments import _sync_tax_id_to_stripe
        btw = update_data["btw_number"]
        if btw:
            _sync_tax_id_to_stripe(company.stripe_customer_id, btw)

    # Sync address to Stripe when updated
    address_fields = {"address", "city", "postal_code"}
    if address_fields & update_data.keys() and company.stripe_customer_id:
        from app.api.v1.endpoints.payments import _sync_address_to_stripe
        _sync_address_to_stripe(company.stripe_customer_id, company)
    
    db.commit()
    db.refresh(company)
    
    return company


@router.get("/me/subscription")
async def get_subscription_info(
    company: Company = Depends(get_current_company)
):
    """
    Get subscription information.
    """
    return {
        "plan": company.subscription_plan.value,
        "status": company.subscription_status or "pending",
        "max_ai_workers": company.ai_worker_limit,
        "started_at": company.subscription_started_at,
        "ends_at": company.subscription_ends_at,
        "has_stripe": bool(company.stripe_customer_id),
        "stripe_subscription_id": company.stripe_subscription_id,
        "trial_used": company.trial_used or False,
    }


@router.post("/me/upgrade")
async def request_upgrade(
    plan: str,
    current_user: User = Depends(require_owner),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Request subscription upgrade.
    Requires owner role.
    """
    # In a real implementation, this would integrate with a payment provider
    # For now, we just return the available plans
    return {
        "message": "Neem contact op met sales@klantenservice.ai voor een upgrade",
        "current_plan": company.subscription_plan.value,
        "requested_plan": plan,
        "available_plans": [
            {
                "id": "starter",
                "name": "Starter",
                "ai_workers": 1,
                "price": "€99/maand",
            },
            {
                "id": "business",
                "name": "Business",
                "ai_workers": 5,
                "price": "€399/maand",
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "ai_workers": 7,
                "price": "Op aanvraag",
            },
        ]
    }


@router.get("/me/privacy-settings")
async def get_privacy_settings(
    company: Company = Depends(get_current_company)
):
    """
    Get privacy settings.
    """
    return {
        "data_retention_days": company.data_retention_days,
        "call_recording_enabled": company.call_recording_enabled,
        "call_recording_consent_required": company.call_recording_consent_required,
        "disclosure_message": company.disclosure_message,
    }


class PrivacySettingsUpdate(BaseModel):
    data_retention_days: Optional[int] = None
    call_recording_enabled: Optional[bool] = None
    call_recording_consent_required: Optional[bool] = None
    disclosure_message: Optional[str] = None


@router.patch("/me/privacy-settings")
async def update_privacy_settings(
    data: PrivacySettingsUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update privacy settings.
    Requires admin or owner role.
    """
    if data.data_retention_days is not None:
        if data.data_retention_days < 30 or data.data_retention_days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data retentie moet tussen 30 en 365 dagen zijn",
            )
        company.data_retention_days = data.data_retention_days
    
    if data.call_recording_enabled is not None:
        company.call_recording_enabled = data.call_recording_enabled
    
    if data.call_recording_consent_required is not None:
        company.call_recording_consent_required = data.call_recording_consent_required
    
    if data.disclosure_message is not None:
        company.disclosure_message = data.disclosure_message
    
    db.commit()
    
    return {
        "data_retention_days": company.data_retention_days,
        "call_recording_enabled": company.call_recording_enabled,
        "call_recording_consent_required": company.call_recording_consent_required,
        "disclosure_message": company.disclosure_message,
    }
