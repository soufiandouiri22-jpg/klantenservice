"""
klantenservice.ai - User Schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
from uuid import UUID

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, max_length=100)
    role: UserRole = UserRole.viewer
    
    @validator("password")
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Wachtwoord moet minimaal één hoofdletter bevatten")
        if not any(c.islower() for c in v):
            raise ValueError("Wachtwoord moet minimaal één kleine letter bevatten")
        if not any(c.isdigit() for c in v):
            raise ValueError("Wachtwoord moet minimaal één cijfer bevatten")
        return v


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID
    company_id: UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    is_superadmin: bool = False
    oauth_provider: str = "email"
    last_login_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for JWT tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for token refresh."""
    refresh_token: str


class ProfileUpdate(BaseModel):
    """Schema for current user profile update (first_name, last_name, email, phone)."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class PasswordChange(BaseModel):
    """Schema for password change."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator("new_password")
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Wachtwoord moet minimaal één hoofdletter bevatten")
        if not any(c.islower() for c in v):
            raise ValueError("Wachtwoord moet minimaal één kleine letter bevatten")
        if not any(c.isdigit() for c in v):
            raise ValueError("Wachtwoord moet minimaal één cijfer bevatten")
        return v


class PasswordReset(BaseModel):
    """Schema for password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class UserInvite(BaseModel):
    """Schema for inviting a new user."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None
    role: UserRole = UserRole.viewer


class AcceptInvite(BaseModel):
    """Schema for accepting an invitation."""
    token: str
    password: str = Field(..., min_length=8, max_length=100)
    
    @validator("password")
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Wachtwoord moet minimaal één hoofdletter bevatten")
        if not any(c.islower() for c in v):
            raise ValueError("Wachtwoord moet minimaal één kleine letter bevatten")
        if not any(c.isdigit() for c in v):
            raise ValueError("Wachtwoord moet minimaal één cijfer bevatten")
        return v


class InviteResponse(BaseModel):
    """Response after sending invite."""
    message: str
    user_id: UUID
    email: str


class RegisterResponse(BaseModel):
    """Response after registration (before email verification)."""
    message: str
    email: EmailStr


class EmailVerifyCode(BaseModel):
    """Schema for email verification with code (no auth required)."""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class EmailResendCode(BaseModel):
    """Schema for resending verification code (no auth required)."""
    email: EmailStr
