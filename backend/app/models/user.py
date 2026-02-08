"""
klantenservice.ai - User Model
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base


class UserRole(str, Enum):
    owner = "owner"       # Full access, billing, can delete company
    admin = "admin"       # Full access except billing
    manager = "manager"   # Can manage AI workers, view logs
    viewer = "viewer"     # Read-only access


class OAuthProvider(str, Enum):
    email = "email"       # Traditional email/password login
    google = "google"     # Google OAuth


class User(Base):
    """
    User model - represents a user within a company.
    Users have roles that determine their access level.
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth-only accounts
    
    # OAuth
    oauth_provider = Column(SQLEnum(OAuthProvider), default=OAuthProvider.email, nullable=False)
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    
    # Profile
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    
    # Role & Permissions
    role = Column(SQLEnum(UserRole), default=UserRole.viewer, nullable=False)
    is_superadmin = Column(Boolean, default=False)  # klantenservice.ai platform admin
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Security
    last_login_at = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Email verification
    verification_token = Column(String(255), nullable=True)
    verification_sent_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    pending_email = Column(String(255), nullable=True)
    
    # Password reset
    reset_token = Column(String(255), nullable=True)
    reset_token_expires_at = Column(DateTime, nullable=True)
    
    # Invite system
    invite_token = Column(String(255), nullable=True, unique=True, index=True)
    invite_token_expires_at = Column(DateTime, nullable=True)
    invited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    invited_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="users")
    
    def __repr__(self):
        return f"<User {self.email}>"
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def can_manage_workers(self) -> bool:
        return self.role in [UserRole.owner, UserRole.admin, UserRole.manager]
    
    def can_manage_billing(self) -> bool:
        return self.role == UserRole.owner
    
    def can_manage_users(self) -> bool:
        return self.role in [UserRole.owner, UserRole.admin]


