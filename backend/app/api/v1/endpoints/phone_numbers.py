"""
klantenservice.ai - Phone Number Endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException, TwilioException

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.company import Company
from app.models.phone_number import PhoneNumber
from app.models.ai_worker import AIWorker
from app.schemas.phone_number import (
    PhoneNumberCreate, 
    PhoneNumberUpdate, 
    PhoneNumberResponse,
    AvailableNumber,
    AvailableNumbersResponse,
    PurchaseNumberRequest,
    PurchaseNumberResponse,
)
from app.api.deps import get_current_user, get_current_company, get_current_company_with_subscription, require_admin

router = APIRouter()


def get_twilio_client() -> TwilioClient:
    """Get configured Twilio client."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio is niet geconfigureerd",
        )
    return TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


@router.get("", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all phone numbers for the current company.
    """
    numbers = db.query(PhoneNumber).filter(PhoneNumber.company_id == company.id).all()
    return numbers


@router.post("", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
async def create_phone_number(
    data: PhoneNumberCreate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company_with_subscription),  # Requires active subscription
    db: Session = Depends(get_db)
):
    """
    Start the phone setup wizard.
    User provides their business phone number, system automatically assigns an AI number.
    Requires admin or owner role.
    Requires active subscription or trial.
    """
    # Check phone number limit based on subscription plan (same as AI workers limit)
    current_count = db.query(PhoneNumber).filter(
        PhoneNumber.company_id == company.id
    ).count()
    
    if current_count >= company.ai_worker_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"U heeft het maximum aantal telefoonnummers ({company.ai_worker_limit}) bereikt. Upgrade uw abonnement voor meer nummers.",
        )
    
    # Check if business number already exists for this company
    existing = db.query(PhoneNumber).filter(
        PhoneNumber.business_number == data.business_number,
        PhoneNumber.company_id == company.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit bedrijfsnummer is al gekoppeld",
        )
    
    # Validate ai_worker_id if provided
    if data.ai_worker_id:
        ai_worker = db.query(AIWorker).filter(
            AIWorker.id == data.ai_worker_id,
            AIWorker.company_id == company.id
        ).first()
        if not ai_worker:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI-medewerker niet gevonden",
            )
    
    # Automatically purchase an AI number from Twilio
    client = get_twilio_client()
    
    try:
        # Search for available numbers
        available = []
        try:
            available = client.available_phone_numbers("NL").mobile.list(limit=1)
        except (TwilioRestException, TwilioException):
            pass
        
        if not available:
            try:
                available = client.available_phone_numbers("NL").local.list(limit=1)
            except (TwilioRestException, TwilioException):
                pass
        
        if not available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Er zijn momenteel geen telefoonnummers beschikbaar. Probeer het later opnieuw.",
            )
        
        ai_number = available[0].phone_number
        
        # Build webhook URL for voice calls
        webhook_base = settings.WEBSOCKET_URL.replace("wss://", "https://").replace("/ws/voice", "")
        if not webhook_base:
            webhook_base = "https://api.klantenservice.ai"
        voice_webhook_url = f"{webhook_base}/api/v1/webhooks/twilio/voice"
        
        # Purchase the AI number from Twilio
        # Use the central klantenservice.ai address for regulatory compliance
        purchase_params = {
            "phone_number": ai_number,
            "friendly_name": data.friendly_name or f"klantenservice.ai - {company.name}",
            "voice_url": voice_webhook_url,
            "voice_method": "POST",
            "status_callback": f"{webhook_base}/api/v1/webhooks/twilio/status",
            "status_callback_method": "POST",
        }
        
        # Add AddressSid if configured (required for NL numbers)
        if settings.TWILIO_ADDRESS_SID:
            purchase_params["address_sid"] = settings.TWILIO_ADDRESS_SID
        
        purchased = client.incoming_phone_numbers.create(**purchase_params)
        
        phone_number = PhoneNumber(
            id=uuid4(),
            company_id=company.id,
            ai_worker_id=data.ai_worker_id,
            number=ai_number,  # AI/Twilio number
            business_number=data.business_number,  # Customer's actual number
            friendly_name=data.friendly_name,
            twilio_sid=purchased.sid,
            setup_completed=False,
            forwarding_verified=False,
            is_active=True,
        )
        
        db.add(phone_number)
        db.commit()
        db.refresh(phone_number)
        
        return phone_number
        
    except TwilioRestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kon AI-nummer niet aanmaken: {str(e)}",
        )


@router.get("/{phone_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get a specific phone number.
    """
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_id,
        PhoneNumber.company_id == company.id
    ).first()
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telefoonnummer niet gevonden",
        )
    
    return phone


@router.patch("/{phone_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    phone_id: UUID,
    data: PhoneNumberUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update a phone number.
    Requires admin or owner role.
    """
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_id,
        PhoneNumber.company_id == company.id
    ).first()
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telefoonnummer niet gevonden",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    
    # Validate ai_worker_id if being updated
    if "ai_worker_id" in update_data and update_data["ai_worker_id"]:
        ai_worker = db.query(AIWorker).filter(
            AIWorker.id == update_data["ai_worker_id"],
            AIWorker.company_id == company.id
        ).first()
        if not ai_worker:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI-medewerker niet gevonden",
            )
    
    # Handle business_hours separately
    if "business_hours" in update_data and update_data["business_hours"]:
        update_data["business_hours"] = update_data["business_hours"].model_dump() if hasattr(update_data["business_hours"], 'model_dump') else update_data["business_hours"]
    
    for field, value in update_data.items():
        setattr(phone, field, value)
    
    db.commit()
    db.refresh(phone)
    
    return phone


@router.delete("/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone_number(
    phone_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Delete a phone number.
    Requires admin or owner role.
    """
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_id,
        PhoneNumber.company_id == company.id
    ).first()
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telefoonnummer niet gevonden",
        )
    
    db.delete(phone)
    db.commit()


# =============================================================================
# Twilio Number Purchase Endpoints
# =============================================================================

@router.get("/available/search", response_model=AvailableNumbersResponse)
async def search_available_numbers(
    country: str = Query("NL", description="Land code (bijv. NL, BE, DE)"),
    area_code: Optional[str] = Query(None, description="Netnummer (bijv. 020 voor Amsterdam)"),
    contains: Optional[str] = Query(None, description="Nummer moet deze cijfers bevatten"),
    limit: int = Query(10, ge=1, le=30, description="Maximum aantal resultaten"),
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
):
    """
    Search for available phone numbers to purchase.
    Returns a list of available numbers in the specified country.
    """
    client = get_twilio_client()
    
    try:
        # Build search parameters
        search_params = {"limit": limit}
        if area_code:
            search_params["area_code"] = area_code
        if contains:
            search_params["contains"] = contains
        
        available = []
        
        # Try mobile numbers first (NL only has mobile)
        try:
            available = client.available_phone_numbers(country).mobile.list(**search_params)
        except (TwilioRestException, TwilioException):
            pass
        
        # If no mobile numbers, try local numbers
        if not available:
            try:
                available = client.available_phone_numbers(country).local.list(**search_params)
            except (TwilioRestException, TwilioException):
                pass
        
        numbers = []
        for num in available:
            numbers.append(AvailableNumber(
                phone_number=num.phone_number,
                friendly_name=num.friendly_name,
                locality=getattr(num, 'locality', None),
                region=getattr(num, 'region', None),
                capabilities={
                    "voice": getattr(num.capabilities, 'voice', False),
                    "sms": getattr(num.capabilities, 'sms', False),
                    "mms": getattr(num.capabilities, 'mms', False),
                },
                monthly_cost="€1.00",  # Twilio NL numbers are approximately €1/month
            ))
        
        return AvailableNumbersResponse(numbers=numbers, country=country)
        
    except (TwilioRestException, TwilioException) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kon geen nummers vinden: {str(e)}",
        )


@router.post("/purchase", response_model=PurchaseNumberResponse)
async def purchase_phone_number(
    data: PurchaseNumberRequest,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company_with_subscription),  # Requires active subscription
    db: Session = Depends(get_db)
):
    """
    Purchase a phone number from Twilio and add it to the company.
    The webhook is automatically configured for AI voice handling.
    Requires admin or owner role.
    Requires active subscription or trial.
    """
    # Check phone number limit based on subscription plan (same as AI workers limit)
    current_count = db.query(PhoneNumber).filter(
        PhoneNumber.company_id == company.id
    ).count()
    
    if current_count >= company.ai_worker_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"U heeft het maximum aantal telefoonnummers ({company.ai_worker_limit}) bereikt. Upgrade uw abonnement voor meer nummers.",
        )
    
    client = get_twilio_client()
    
    # Check if number already exists in our system
    existing = db.query(PhoneNumber).filter(PhoneNumber.number == data.phone_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit telefoonnummer is al in gebruik",
        )
    
    # Validate ai_worker_id if provided
    if data.ai_worker_id:
        ai_worker = db.query(AIWorker).filter(
            AIWorker.id == data.ai_worker_id,
            AIWorker.company_id == company.id
        ).first()
        if not ai_worker:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI-medewerker niet gevonden",
            )
    
    try:
        # Build webhook URL for voice calls
        # In production, this should be your actual API domain
        webhook_base = settings.WEBSOCKET_URL.replace("wss://", "https://").replace("/ws/voice", "")
        if not webhook_base:
            webhook_base = "https://api.klantenservice.ai"
        voice_webhook_url = f"{webhook_base}/api/v1/webhooks/twilio/voice"
        
        # Purchase the number from Twilio
        purchased = client.incoming_phone_numbers.create(
            phone_number=data.phone_number,
            friendly_name=data.friendly_name or f"klantenservice.ai - {company.name}",
            voice_url=voice_webhook_url,
            voice_method="POST",
            # Status callback for call events
            status_callback=f"{webhook_base}/api/v1/webhooks/twilio/status",
            status_callback_method="POST",
        )
        
        # Create the phone number in our database
        phone_number = PhoneNumber(
            id=uuid4(),
            company_id=company.id,
            ai_worker_id=data.ai_worker_id,
            number=data.phone_number,
            friendly_name=data.friendly_name or purchased.friendly_name,
            is_active=True,
        )
        
        db.add(phone_number)
        db.commit()
        db.refresh(phone_number)
        
        return PurchaseNumberResponse(
            success=True,
            phone_number=phone_number,
            twilio_sid=purchased.sid,
            message=f"Telefoonnummer {data.phone_number} is succesvol aangemaakt en geconfigureerd!",
        )
        
    except TwilioRestException as e:
        # Handle specific Twilio errors
        error_message = str(e)
        if "21422" in error_message:
            detail = "Dit nummer is niet beschikbaar. Probeer een ander nummer."
        elif "21215" in error_message:
            detail = "Ongeldig telefoonnummer formaat."
        elif "20003" in error_message:
            detail = "Authenticatie mislukt. Controleer de Twilio credentials."
        else:
            detail = f"Kon nummer niet aanschaffen: {error_message}"
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


@router.delete("/{phone_id}/release", status_code=status.HTTP_200_OK)
async def release_phone_number(
    phone_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Release a phone number back to Twilio and remove it from the company.
    This will stop billing for the number.
    Requires admin or owner role.
    """
    phone = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_id,
        PhoneNumber.company_id == company.id
    ).first()
    
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telefoonnummer niet gevonden",
        )
    
    client = get_twilio_client()
    
    try:
        # Find and delete the number from Twilio
        twilio_numbers = client.incoming_phone_numbers.list(phone_number=phone.number)
        for twilio_num in twilio_numbers:
            twilio_num.delete()
    except TwilioRestException as e:
        # Log the error but continue with local deletion
        # The number might have been manually deleted from Twilio
        pass
    
    # Delete from our database
    db.delete(phone)
    db.commit()
    
    return {"message": f"Telefoonnummer {phone.number} is vrijgegeven"}
