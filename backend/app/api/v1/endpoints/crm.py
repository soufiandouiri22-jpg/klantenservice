"""
klantenservice.ai - CRM Integration Endpoints

Handles CRM OAuth flow, contact lookup, and integration management.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import encrypt_value
from app.models.user import User
from app.models.company import Company
from app.models.ai_worker import AIWorker
from app.models.crm_integration import CRMIntegration, CRMProvider
from app.schemas.crm import (
    CRMIntegrationCreate,
    CRMIntegrationUpdate,
    CRMIntegrationResponse,
)
from app.api.deps import get_current_user, get_current_company, require_admin
from app.services import hubspot_service as hubspot
from app.services import salesdock_service as salesdock
from app.services import saleslane_service as saleslane

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


def _to_response(crm: CRMIntegration) -> dict:
    """Convert a CRMIntegration to a response dict with is_connected."""
    if crm.provider in (CRMProvider.SALESDOCK, CRMProvider.SALESLANE):
        is_connected = crm.api_key_encrypted is not None
    else:
        is_connected = crm.access_token_encrypted is not None

    return {
        "id": crm.id,
        "company_id": crm.company_id,
        "name": crm.name,
        "provider": crm.provider,
        "hubspot_portal_id": crm.hubspot_portal_id,
        "account_domain": crm.account_domain,
        "api_context_id": crm.api_context_id,
        "sync_contacts_on_call": crm.sync_contacts_on_call,
        "write_call_notes": crm.write_call_notes,
        "auto_create_contacts": crm.auto_create_contacts,
        "last_sync_at": crm.last_sync_at,
        "sync_error": crm.sync_error,
        "is_active": crm.is_active,
        "is_connected": is_connected,
        "created_at": crm.created_at,
        "updated_at": crm.updated_at,
    }


# ── OAuth Flow ──────────────────────────────────────────


@router.get("/oauth/{provider}/url")
async def get_oauth_url(
    provider: CRMProvider,
    crm_id: UUID = Query(..., description="CRM integration ID to connect"),
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get OAuth authorization URL for the CRM provider."""
    if provider in (CRMProvider.SALESDOCK, CRMProvider.SALESLANE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider.value.title()} gebruikt geen OAuth maar directe API-authenticatie.",
        )
    if provider != CRMProvider.HUBSPOT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alleen HubSpot ondersteunt OAuth. Salesdock en Saleslane gebruiken API-key authenticatie.",
        )

    crm = _get_crm_or_404(crm_id, company.id, db)

    code_verifier, code_challenge = hubspot.generate_pkce_pair()
    crm.pkce_code_verifier = code_verifier
    db.commit()

    state = json.dumps({"crm_id": str(crm.id), "company_id": str(company.id)})
    auth_url = hubspot.build_auth_url(state, code_challenge)
    return {"auth_url": auth_url, "provider": provider.value}


@router.get("/oauth/hubspot/callback")
async def hubspot_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    HubSpot OAuth callback. HubSpot redirects here after user consent.
    """
    try:
        state_data = json.loads(state)
        crm_id = UUID(state_data["crm_id"])
    except (json.JSONDecodeError, KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Ongeldige state parameter")

    crm = db.query(CRMIntegration).filter(CRMIntegration.id == crm_id).first()
    if not crm:
        raise HTTPException(status_code=404, detail="CRM-integratie niet gevonden")

    if not crm.pkce_code_verifier:
        raise HTTPException(status_code=400, detail="PKCE verifier ontbreekt — start de koppeling opnieuw")

    code_verifier = crm.pkce_code_verifier
    crm.pkce_code_verifier = None
    db.commit()

    try:
        token_data = await hubspot.exchange_code_for_tokens(code, code_verifier)
    except Exception as e:
        logger.error(f"HubSpot token exchange failed: {e}")
        raise HTTPException(
            status_code=400,
            detail="Kon geen toegang krijgen tot HubSpot",
        )

    crm.access_token_encrypted = encrypt_value(token_data["access_token"])
    crm.token_expires_at = datetime.utcnow() + timedelta(
        seconds=token_data.get("expires_in", 21600)
    )
    if "refresh_token" in token_data:
        crm.refresh_token_encrypted = encrypt_value(token_data["refresh_token"])

    try:
        account_info = await hubspot.get_account_info(token_data["access_token"])
        if account_info:
            crm.hubspot_portal_id = account_info.get("portal_id")
    except Exception as e:
        logger.warning(f"Could not fetch HubSpot account info: {e}")

    crm.last_sync_at = datetime.utcnow()
    crm.sync_error = None
    crm.is_active = True
    db.commit()

    logger.info(f"HubSpot connected for integration {crm.id}")

    frontend_url = settings.FRONTEND_URL
    return RedirectResponse(
        url=f"{frontend_url}/dashboard/integrations?connected=true&crm_id={crm.id}"
    )


# ── CRUD ──────────────────────────────────────────────────


@router.get("", response_model=List[CRMIntegrationResponse])
async def list_crm_integrations(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """List all CRM integrations for the current company."""
    integrations = (
        db.query(CRMIntegration)
        .filter(CRMIntegration.company_id == company.id)
        .all()
    )
    return [_to_response(i) for i in integrations]


@router.post("", response_model=CRMIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_crm_integration(
    data: CRMIntegrationCreate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Create a new CRM integration (pre-OAuth)."""
    ai_worker_count = db.query(AIWorker).filter(AIWorker.company_id == company.id).count()
    if ai_worker_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maak eerst een AI-medewerker aan voordat u een integratie kunt koppelen.",
        )
    existing = (
        db.query(CRMIntegration)
        .filter(
            CRMIntegration.company_id == company.id,
            CRMIntegration.provider == data.provider,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"U heeft al een {data.provider.value.title()} integratie ({existing.name}). Verwijder deze eerst.",
        )

    crm = CRMIntegration(
        id=uuid4(),
        company_id=company.id,
        name=data.name,
        provider=data.provider,
        is_active=True,
    )

    if data.provider == CRMProvider.SALESDOCK:
        if not data.api_key or not data.account_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Salesdock vereist een API key en account domein.",
            )
        crm.api_key_encrypted = encrypt_value(data.api_key)
        crm.account_domain = data.account_domain

    elif data.provider == CRMProvider.SALESLANE:
        if not data.api_key or not data.account_domain or not data.api_context_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Saleslane vereist een RSA private key, client prefix en API Context ID.",
            )
        crm.api_key_encrypted = encrypt_value(data.api_key)
        crm.account_domain = data.account_domain
        crm.api_context_id = data.api_context_id

    db.add(crm)
    db.commit()
    db.refresh(crm)
    return _to_response(crm)


@router.get("/{crm_id}", response_model=CRMIntegrationResponse)
async def get_crm_integration(
    crm_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Get a specific CRM integration."""
    crm = _get_crm_or_404(crm_id, company.id, db)
    return _to_response(crm)


@router.patch("/{crm_id}", response_model=CRMIntegrationResponse)
async def update_crm_integration(
    crm_id: UUID,
    data: CRMIntegrationUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Update CRM integration settings."""
    crm = _get_crm_or_404(crm_id, company.id, db)
    update_data = data.model_dump(exclude_unset=True)

    new_api_key = update_data.pop("api_key", None)
    if new_api_key and crm.provider in (CRMProvider.SALESDOCK, CRMProvider.SALESLANE):
        crm.api_key_encrypted = encrypt_value(new_api_key)

    for field, value in update_data.items():
        setattr(crm, field, value)

    db.commit()
    db.refresh(crm)
    return _to_response(crm)


@router.delete("/{crm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_crm_integration(
    crm_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Delete a CRM integration."""
    crm = _get_crm_or_404(crm_id, company.id, db)
    db.delete(crm)
    db.commit()


@router.post("/{crm_id}/test")
async def test_crm_connection(
    crm_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Test the CRM connection by fetching account info."""
    crm = _get_crm_or_404(crm_id, company.id, db)

    try:
        if crm.provider == CRMProvider.SALESDOCK:
            api_key, domain = salesdock.get_valid_credentials(crm, db)
            account_info = await salesdock.test_connection(api_key, domain)
        elif crm.provider == CRMProvider.SALESLANE:
            pk, ctx_id, prefix = saleslane.get_valid_credentials(crm, db)
            account_info = await saleslane.test_connection(pk, ctx_id, prefix)
        else:
            if not crm.access_token_encrypted:
                raise HTTPException(status_code=400, detail="CRM is nog niet gekoppeld.")
            access_token = await hubspot.get_valid_access_token(crm, db)
            account_info = await hubspot.get_account_info(access_token)

        crm.last_sync_at = datetime.utcnow()
        crm.sync_error = None
        db.commit()

        return {
            "message": "Verbinding succesvol",
            "crm_id": str(crm.id),
            "account_info": account_info,
            "last_sync_at": crm.last_sync_at.isoformat(),
        }
    except Exception as e:
        crm.sync_error = str(e)
        db.commit()
        logger.error(f"CRM connection test failed: {e}")
        raise HTTPException(status_code=502, detail=f"Verbinding mislukt: {e}")


# ── Helpers ───────────────────────────────────────────────


def _get_crm_or_404(
    crm_id: UUID, company_id: UUID, db: Session
) -> CRMIntegration:
    crm = (
        db.query(CRMIntegration)
        .filter(
            CRMIntegration.id == crm_id,
            CRMIntegration.company_id == company_id,
        )
        .first()
    )
    if not crm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CRM-integratie niet gevonden",
        )
    return crm
