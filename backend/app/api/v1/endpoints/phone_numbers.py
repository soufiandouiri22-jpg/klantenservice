"""
klantenservice.ai - Phone Number Endpoints
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.phone_number import PhoneNumber
from app.schemas.phone_number import PhoneNumberCreate, PhoneNumberUpdate, PhoneNumberResponse
from app.api.deps import get_current_user, get_current_company, require_admin

router = APIRouter()


@router.get("/", response_model=List[PhoneNumberResponse])
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


@router.post("/", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
async def create_phone_number(
    data: PhoneNumberCreate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Add a new phone number.
    Requires admin or owner role.
    """
    # Check if number already exists
    existing = db.query(PhoneNumber).filter(PhoneNumber.number == data.number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit telefoonnummer is al in gebruik",
        )
    
    phone_number = PhoneNumber(
        id=uuid4(),
        company_id=company.id,
        number=data.number,
        friendly_name=data.friendly_name,
        is_active=True,
    )
    
    db.add(phone_number)
    db.commit()
    db.refresh(phone_number)
    
    return phone_number


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
