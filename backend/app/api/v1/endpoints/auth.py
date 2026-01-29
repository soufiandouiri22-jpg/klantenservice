"""
klantenservice.ai - Authentication Endpoints
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import uuid4
import re
import secrets
import httpx

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.user import User, UserRole, OAuthProvider
from app.models.company import Company, SubscriptionPlan
from app.models.training import TrainingRule
from app.models.training import DEFAULT_TRAINING_RULES
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    TokenRefresh,
    PasswordChange,
    PasswordReset,
    PasswordResetConfirm,
    AcceptInvite,
)
from app.schemas.company import CompanyCreate
from app.api.deps import get_current_user
from app.core.email import send_welcome_email

router = APIRouter()

# Store OAuth state tokens temporarily (in production, use Redis)
oauth_states: dict[str, datetime] = {}


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from company name."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    company_data: CompanyCreate,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new company and owner account.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit e-mailadres is al in gebruik",
        )
    
    # Generate unique slug
    base_slug = generate_slug(company_data.name)
    slug = base_slug
    counter = 1
    while db.query(Company).filter(Company.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    # Create company
    company = Company(
        id=uuid4(),
        name=company_data.name,
        slug=slug,
        email=company_data.email,
        phone=company_data.phone,
        address=company_data.address,
        city=company_data.city,
        postal_code=company_data.postal_code,
        kvk_number=company_data.kvk_number,
        btw_number=company_data.btw_number,
        subscription_plan=SubscriptionPlan.STARTER,
        max_ai_workers=1,
    )
    db.add(company)
    db.flush()
    
    # Create owner user
    user = User(
        id=uuid4(),
        company_id=company.id,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        role=UserRole.OWNER,
        is_active=True,
    )
    db.add(user)
    
    # Create default training rules
    for rule_data in DEFAULT_TRAINING_RULES:
        rule = TrainingRule(
            id=uuid4(),
            company_id=company.id,
            **rule_data
        )
        db.add(rule)
    
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(
        subject=str(user.id),
        company_id=str(company.id),
        role=user.role.value,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        company_id=str(company.id),
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    """
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        # Increment failed attempts
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
            db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Onjuist e-mailadres of wachtwoord",
        )
    
    # Check if locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is tijdelijk vergrendeld. Probeer het later opnieuw.",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Uw account is gedeactiveerd",
        )
    
    # Reset failed attempts and update last login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        company_id=str(user.company_id),
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    """
    payload = decode_token(token_data.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ongeldige refresh token",
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gebruiker niet gevonden of inactief",
        )
    
    # Generate new tokens
    access_token = create_access_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )
    new_refresh_token = create_refresh_token(
        subject=str(user.id),
        company_id=str(user.company_id),
    )
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current user profile.
    """
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change current user's password.
    """
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Huidig wachtwoord is onjuist",
        )
    
    current_user.hashed_password = get_password_hash(password_data.new_password)
    current_user.password_changed_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Wachtwoord succesvol gewijzigd"}


@router.post("/forgot-password")
async def forgot_password(
    data: PasswordReset,
    db: Session = Depends(get_db)
):
    """
    Request password reset email.
    """
    user = db.query(User).filter(User.email == data.email).first()
    
    # Always return success to prevent email enumeration
    if user:
        # Generate reset token
        reset_token = str(uuid4())
        user.reset_token = reset_token
        user.reset_token_expires_at = datetime.utcnow() + timedelta(hours=1)
        db.commit()
        
        # TODO: Send email with reset link
        # send_password_reset_email(user.email, reset_token)
    
    return {"message": "Als dit e-mailadres bij ons bekend is, ontvangt u een e-mail met instructies."}


@router.post("/reset-password")
async def reset_password(
    data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password using reset token.
    """
    user = db.query(User).filter(
        User.reset_token == data.token,
        User.reset_token_expires_at > datetime.utcnow()
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ongeldige of verlopen reset link",
        )
    
    user.hashed_password = get_password_hash(data.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    user.password_changed_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Wachtwoord succesvol gereset"}


@router.post("/dev-login", response_model=Token)
async def dev_login(db: Session = Depends(get_db)):
    """
    Development login - creates or uses a dev admin account.
    WARNING: Only use in development environments!
    """
    DEV_EMAIL = "dev@klantenservice.ai"
    DEV_PASSWORD = "devpassword123"
    
    # Check if dev user exists
    user = db.query(User).filter(User.email == DEV_EMAIL).first()
    
    if not user:
        # Check if dev company exists
        company = db.query(Company).filter(Company.slug == "dev-company").first()
        
        if not company:
            # Create dev company
            company = Company(
                id=uuid4(),
                name="Dev Company",
                slug="dev-company",
                email="dev@klantenservice.ai",
                subscription_plan=SubscriptionPlan.PROFESSIONAL,
                max_ai_workers=10,
            )
            db.add(company)
            db.flush()
            
            # Create default training rules for dev company
            for rule_data in DEFAULT_TRAINING_RULES:
                rule = TrainingRule(
                    id=uuid4(),
                    company_id=company.id,
                    **rule_data
                )
                db.add(rule)
        
        # Create dev admin user
        user = User(
            id=uuid4(),
            company_id=company.id,
            email=DEV_EMAIL,
            hashed_password=get_password_hash(DEV_PASSWORD),
            first_name="Dev",
            last_name="Admin",
            role=UserRole.OWNER,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    # Generate tokens
    access_token = create_access_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        company_id=str(user.company_id),
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# =============================================================================
# Invite System Endpoints
# =============================================================================

@router.get("/invite/{token}")
async def get_invite_info(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Get information about an invitation.
    Used by the frontend to display the invite acceptance page.
    """
    user = db.query(User).filter(User.invite_token == token).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uitnodiging niet gevonden",
        )
    
    if user.invite_token_expires_at and user.invite_token_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deze uitnodiging is verlopen",
        )
    
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deze uitnodiging is al geaccepteerd",
        )
    
    # Get company info
    company = db.query(Company).filter(Company.id == user.company_id).first()
    
    return {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "company_name": company.name if company else "Onbekend bedrijf",
        "role": user.role.value,
    }


@router.post("/accept-invite", response_model=Token)
async def accept_invite(
    data: AcceptInvite,
    db: Session = Depends(get_db)
):
    """
    Accept an invitation and set password.
    Activates the user account and returns auth tokens.
    """
    user = db.query(User).filter(User.invite_token == data.token).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uitnodiging niet gevonden",
        )
    
    if user.invite_token_expires_at and user.invite_token_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deze uitnodiging is verlopen. Vraag een nieuwe aan bij je beheerder.",
        )
    
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deze uitnodiging is al geaccepteerd",
        )
    
    # Set password and activate user
    user.hashed_password = get_password_hash(data.password)
    user.is_active = True
    user.is_verified = True
    user.invite_token = None
    user.invite_token_expires_at = None
    user.last_login_at = datetime.utcnow()
    user.verified_at = datetime.utcnow()
    
    db.commit()
    
    # Get company for welcome email
    company = db.query(Company).filter(Company.id == user.company_id).first()
    
    # Send welcome email
    send_welcome_email(
        to_email=user.email,
        first_name=user.first_name,
        company_name=company.name if company else "het bedrijf"
    )
    
    # Generate tokens
    access_token = create_access_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        company_id=str(user.company_id),
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


# =============================================================================
# Google OAuth Endpoints
# =============================================================================

@router.get("/google/url")
async def get_google_oauth_url():
    """
    Generate Google OAuth authorization URL.
    Returns the URL to redirect the user to for Google login.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is niet geconfigureerd",
        )
    
    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)
    oauth_states[state] = datetime.utcnow() + timedelta(minutes=10)
    
    # Clean up expired states
    now = datetime.utcnow()
    expired = [k for k, v in oauth_states.items() if v < now]
    for k in expired:
        del oauth_states[k]
    
    # Build OAuth URL
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_AUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }
    
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"
    
    return {
        "auth_url": auth_url,
        "state": state,
    }


@router.get("/google/callback", response_model=Token)
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State token for CSRF protection"),
    db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback.
    Exchanges the authorization code for tokens and creates/finds the user.
    """
    # Verify state token
    if state not in oauth_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ongeldige of verlopen state token",
        )
    
    if oauth_states[state] < datetime.utcnow():
        del oauth_states[state]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State token is verlopen",
        )
    
    del oauth_states[state]
    
    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_AUTH_REDIRECT_URI,
            },
        )
        
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kon geen toegangstoken verkrijgen van Google",
            )
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        # Get user info from Google
        userinfo_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        
        if userinfo_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kon geen gebruikersinformatie verkrijgen van Google",
            )
        
        google_user = userinfo_response.json()
    
    google_id = google_user.get("id")
    email = google_user.get("email")
    given_name = google_user.get("given_name", "")
    family_name = google_user.get("family_name", "")
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kon geen e-mailadres verkrijgen van Google",
        )
    
    # Check if user exists by google_id
    user = db.query(User).filter(User.google_id == google_id).first()
    
    if not user:
        # Check if user exists by email
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            # Link existing account to Google
            user.google_id = google_id
            user.oauth_provider = OAuthProvider.GOOGLE
            db.commit()
        else:
            # Create new user and company
            # Generate company name from email domain or user name
            email_domain = email.split("@")[1].split(".")[0].title()
            company_name = f"{given_name}'s Bedrijf" if given_name else f"{email_domain} Bedrijf"
            
            # Generate unique slug
            base_slug = generate_slug(company_name)
            slug = base_slug
            counter = 1
            while db.query(Company).filter(Company.slug == slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Create company
            company = Company(
                id=uuid4(),
                name=company_name,
                slug=slug,
                email=email,
                subscription_plan=SubscriptionPlan.STARTER,
                max_ai_workers=1,
            )
            db.add(company)
            db.flush()
            
            # Create user
            user = User(
                id=uuid4(),
                company_id=company.id,
                email=email,
                hashed_password=None,  # OAuth-only account
                first_name=given_name or "Gebruiker",
                last_name=family_name or "",
                oauth_provider=OAuthProvider.GOOGLE,
                google_id=google_id,
                role=UserRole.OWNER,
                is_active=True,
                is_verified=True,  # Google already verified email
            )
            db.add(user)
            
            # Create default training rules
            for rule_data in DEFAULT_TRAINING_RULES:
                rule = TrainingRule(
                    id=uuid4(),
                    company_id=company.id,
                    **rule_data
                )
                db.add(rule)
            
            db.commit()
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Uw account is gedeactiveerd",
        )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    # Generate JWT tokens
    access_token = create_access_token(
        subject=str(user.id),
        company_id=str(user.company_id),
        role=user.role.value,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        company_id=str(user.company_id),
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )
