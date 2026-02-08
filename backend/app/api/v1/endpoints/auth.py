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
from app.models.global_config import GlobalConfig
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
    RegisterResponse,
    EmailVerifyCode,
    EmailResendCode,
    ProfileUpdate,
    ChangeEmailRequest,
    ChangeEmailVerify,
)
from app.schemas.company import CompanyCreate
from app.api.deps import get_current_user
from app.core.email import send_welcome_email, send_verification_code_email
import random

router = APIRouter()


def generate_verification_code() -> str:
    """Generate a random 6-digit verification code."""
    return str(random.randint(100000, 999999))

# Store OAuth state tokens temporarily (in production, use Redis)
oauth_states: dict[str, datetime] = {}


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from company name."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def get_platform_voice_defaults(db: Session) -> dict:
    """
    Get platform-wide voice defaults for new companies.
    These are stored in GlobalConfig and applied to admin_overrides.
    """
    defaults = {}
    
    # Get voice-related global configs
    voice_configs = db.query(GlobalConfig).filter(
        GlobalConfig.category == "voice"
    ).all()
    
    for config in voice_configs:
        if config.key == "voice_default_preset":
            defaults["voice_preset"] = config.value
        elif config.key == "voice_auto_respond":
            defaults["auto_respond"] = config.value
        elif config.key == "voice_vad_sensitivity":
            defaults["vad_sensitivity"] = config.value
        elif config.key == "voice_segment_ms":
            defaults["audio_segment_ms"] = config.value
    
    # Fallback defaults if GlobalConfig not seeded
    if "voice_preset" not in defaults:
        defaults["voice_preset"] = "NATF2.pt"
    if "auto_respond" not in defaults:
        defaults["auto_respond"] = True
    
    return defaults


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    company_data: CompanyCreate,
    user_data: UserCreate,
    terms_accepted: bool = False,
    marketing_consent: bool = False,
    db: Session = Depends(get_db)
):
    """
    Register a new company and owner account.
    
    terms_accepted must be True (user agreed to terms & privacy).
    marketing_consent is optional (opt-in for email marketing).
    Returns email address (no tokens). User must verify email before logging in.
    """
    if not terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="U dient akkoord te gaan met de algemene voorwaarden en het privacybeleid.",
        )
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
    
    # Get platform voice defaults for new company
    voice_defaults = get_platform_voice_defaults(db)
    
    # Create company with platform defaults
    # New accounts start with "pending" status - they need to complete checkout
    # to get "trialing" (14-day trial) or "active" status
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
        subscription_plan=SubscriptionPlan.starter,
        subscription_status="pending",  # Must complete checkout to activate
        max_ai_workers=1,
        admin_overrides=voice_defaults,  # Apply platform defaults
        terms_accepted_at=datetime.utcnow(),
        marketing_consent=marketing_consent,
    )
    db.add(company)
    db.flush()
    
    # Generate verification code
    verification_code = generate_verification_code()
    
    # Create owner user (unverified)
    user = User(
        id=uuid4(),
        company_id=company.id,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        role=UserRole.owner,
        is_active=True,
        is_verified=False,
        verification_token=verification_code,
        verification_sent_at=datetime.utcnow(),
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
    
    # Send verification email
    send_verification_code_email(
        to_email=user.email,
        first_name=user.first_name,
        code=verification_code,
    )
    
    # Return email only (no tokens - user must verify first)
    return RegisterResponse(
        message="Account aangemaakt. Controleer uw e-mail voor de verificatiecode.",
        email=user.email
    )


@router.post("/verify-code", response_model=Token)
async def verify_code(
    data: EmailVerifyCode,
    db: Session = Depends(get_db)
):
    """
    Verify email with 6-digit code (no authentication required).
    
    Returns tokens after successful verification.
    """
    # Find user by email
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gebruiker niet gevonden",
        )
    
    # Already verified
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail is al geverifieerd",
        )
    
    # Check if code is expired (10 minutes)
    if user.verification_sent_at:
        expires_at = user.verification_sent_at + timedelta(minutes=10)
        if datetime.utcnow() > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verificatiecode is verlopen. Vraag een nieuwe code aan.",
            )
    
    # Check code
    if user.verification_token != data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ongeldige verificatiecode",
        )
    
    # Mark as verified
    user.is_verified = True
    user.verified_at = datetime.utcnow()
    user.verification_token = None
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


@router.post("/resend-code")
async def resend_verification_code(
    data: EmailResendCode,
    db: Session = Depends(get_db)
):
    """
    Resend verification code email (no authentication required).
    """
    # Find user by email
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        # Don't reveal if email exists (security)
        return {"message": "Als dit e-mailadres bij ons bekend is, ontvangt u een nieuwe verificatiecode."}
    
    # Already verified
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail is al geverifieerd",
        )
    
    # Rate limit: minimum 60 seconds between resends
    if user.verification_sent_at:
        cooldown = user.verification_sent_at + timedelta(seconds=60)
        if datetime.utcnow() < cooldown:
            seconds_left = int((cooldown - datetime.utcnow()).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Wacht nog {seconds_left} seconden voordat u een nieuwe code aanvraagt",
            )
    
    # Generate new code
    new_code = generate_verification_code()
    user.verification_token = new_code
    user.verification_sent_at = datetime.utcnow()
    db.commit()
    
    # Send email
    send_verification_code_email(
        to_email=user.email,
        first_name=user.first_name,
        code=new_code,
    )
    
    return {"message": "Nieuwe verificatiecode verzonden"}


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


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update current user profile (first_name, last_name, phone).
    Email changes require verification via /change-email/request + /verify.
    """
    if data.first_name is not None:
        current_user.first_name = data.first_name
    if data.last_name is not None:
        current_user.last_name = data.last_name
    if data.phone is not None:
        current_user.phone = data.phone
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-email/request")
async def request_email_change(
    data: ChangeEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Request an email change. Sends a 6-digit verification code to the
    user's CURRENT email address to confirm the change.
    """
    new_email = data.new_email.lower().strip()

    # Same email
    if new_email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit is al uw huidige e-mailadres",
        )

    # Check if new email is already in use
    existing = db.query(User).filter(User.email == new_email, User.id != current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit e-mailadres is al in gebruik",
        )

    # Rate limit: 60 seconds between requests
    if current_user.verification_sent_at:
        cooldown = current_user.verification_sent_at + timedelta(seconds=60)
        if datetime.utcnow() < cooldown:
            seconds_left = int((cooldown - datetime.utcnow()).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Wacht nog {seconds_left} seconden voordat u een nieuwe code aanvraagt",
            )

    # Generate code and store pending email
    code = generate_verification_code()
    current_user.verification_token = code
    current_user.verification_sent_at = datetime.utcnow()
    current_user.pending_email = new_email
    db.commit()

    # Send code to CURRENT email
    send_verification_code_email(
        to_email=current_user.email,
        first_name=current_user.first_name,
        code=code,
    )

    return {"message": "Verificatiecode verzonden naar uw huidige e-mailadres"}


@router.post("/change-email/verify", response_model=UserResponse)
async def verify_email_change(
    data: ChangeEmailVerify,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verify email change with the 6-digit code sent to the current email.
    On success, updates the email to the pending_email.
    """
    # Check if there is a pending email change
    if not current_user.pending_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Er is geen e-mailwijziging in behandeling",
        )

    # Check if code is expired (10 minutes)
    if current_user.verification_sent_at:
        expires_at = current_user.verification_sent_at + timedelta(minutes=10)
        if datetime.utcnow() > expires_at:
            current_user.verification_token = None
            current_user.pending_email = None
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verificatiecode is verlopen. Vraag een nieuwe code aan.",
            )

    # Validate code
    if current_user.verification_token != data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ongeldige verificatiecode",
        )

    # Double-check new email is still available
    existing = db.query(User).filter(
        User.email == current_user.pending_email,
        User.id != current_user.id
    ).first()
    if existing:
        current_user.verification_token = None
        current_user.pending_email = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dit e-mailadres is inmiddels al in gebruik",
        )

    # Apply email change
    current_user.email = current_user.pending_email
    current_user.pending_email = None
    current_user.verification_token = None
    current_user.verification_sent_at = None
    db.commit()
    db.refresh(current_user)

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
            user.oauth_provider = OAuthProvider.google
            user.is_verified = True  # Google verified the email
            user.verified_at = datetime.utcnow()
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
            
            # Get platform voice defaults for new company
            voice_defaults = get_platform_voice_defaults(db)
            
            # Create company with platform defaults
            # New accounts start with "pending" status - they need to complete checkout
            # to get "trialing" (14-day trial) or "active" status
            company = Company(
                id=uuid4(),
                name=company_name,
                slug=slug,
                email=email,
                subscription_plan=SubscriptionPlan.starter,
                subscription_status="pending",  # Must complete checkout to activate
                max_ai_workers=1,
                admin_overrides=voice_defaults,  # Apply platform defaults
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
                oauth_provider=OAuthProvider.google,
                google_id=google_id,
                role=UserRole.owner,
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
