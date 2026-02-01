"""
klantenservice.ai - User Endpoints
"""
from datetime import datetime, timedelta
from typing import List
import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.database import get_db
from app.core.security import get_password_hash
from app.core.config import settings
from app.core.email import send_invite_email
from app.models.user import User, UserRole
from app.models.company import Company
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserInvite, InviteResponse
from app.api.deps import get_current_user, get_current_company, require_admin

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all users in the current company.
    """
    users = db.query(User).filter(User.company_id == company.id).all()
    return users


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Create a new user in the current company.
    Requires admin or owner role.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit e-mailadres is al in gebruik",
        )
    
    # Only owner can create other owners/admins
    if data.role in [UserRole.owner, UserRole.admin] and current_user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alleen de eigenaar kan admin-accounts aanmaken",
        )
    
    user = User(
        id=uuid4(),
        company_id=company.id,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        role=data.role,
        is_active=True,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    data: UserInvite,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Invite a new user to the company via email.
    The user will receive an email with a link to set their password.
    Requires admin or owner role.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit e-mailadres is al in gebruik",
        )
    
    # Only owner can invite other owners/admins
    if data.role in [UserRole.owner, UserRole.admin] and current_user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alleen de eigenaar kan admin-accounts aanmaken",
        )
    
    # Generate invite token
    invite_token = secrets.token_urlsafe(32)
    
    # Create user with pending status (no password yet)
    user = User(
        id=uuid4(),
        company_id=company.id,
        email=data.email,
        hashed_password=None,  # Will be set when invite is accepted
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        role=data.role,
        is_active=False,  # Not active until invite is accepted
        is_verified=False,
        invite_token=invite_token,
        invite_token_expires_at=datetime.utcnow() + timedelta(days=7),
        invited_by_id=current_user.id,
        invited_at=datetime.utcnow(),
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Send invite email
    invite_link = f"{settings.FRONTEND_URL}/invite/{invite_token}"
    email_sent = send_invite_email(
        to_email=data.email,
        first_name=data.first_name,
        company_name=company.name,
        inviter_name=current_user.full_name,
        invite_link=invite_link,
        role=data.role.value
    )
    
    if not email_sent:
        # If email fails, we still created the user, log the error
        print(f"Warning: Failed to send invite email to {data.email}")
    
    return InviteResponse(
        message="Uitnodiging verstuurd",
        user_id=user.id,
        email=user.email
    )


@router.post("/resend-invite/{user_id}", response_model=InviteResponse)
async def resend_invite(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Resend invitation email to a pending user.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == company.id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gebruiker niet gevonden",
        )
    
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deze gebruiker heeft de uitnodiging al geaccepteerd",
        )
    
    # Generate new invite token
    invite_token = secrets.token_urlsafe(32)
    user.invite_token = invite_token
    user.invite_token_expires_at = datetime.utcnow() + timedelta(days=7)
    user.invited_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    # Send invite email
    invite_link = f"{settings.FRONTEND_URL}/invite/{invite_token}"
    send_invite_email(
        to_email=user.email,
        first_name=user.first_name,
        company_name=company.name,
        inviter_name=current_user.full_name,
        invite_link=invite_link,
        role=user.role.value
    )
    
    return InviteResponse(
        message="Uitnodiging opnieuw verstuurd",
        user_id=user.id,
        email=user.email
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get a specific user.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == company.id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gebruiker niet gevonden",
        )
    
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update a user.
    Requires admin or owner role.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == company.id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gebruiker niet gevonden",
        )
    
    # Cannot demote owner
    if user.role == UserRole.owner and data.role and data.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="De eigenaar kan niet worden gedegradeerd",
        )
    
    # Only owner can change roles to admin/owner
    if data.role in [UserRole.owner, UserRole.admin] and current_user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alleen de eigenaar kan admin-rechten toekennen",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Delete a user.
    Requires admin or owner role.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.company_id == company.id
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gebruiker niet gevonden",
        )
    
    # Cannot delete self
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="U kunt uzelf niet verwijderen",
        )
    
    # Cannot delete owner
    if user.role == UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="De eigenaar kan niet worden verwijderd",
        )
    
    db.delete(user)
    db.commit()
