"""
klantenservice.ai - Security & Authentication
"""
from datetime import datetime, timedelta
from typing import Optional, Any
from jose import jwt, JWTError
import bcrypt
from cryptography.fernet import Fernet
import base64
import hashlib

from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Generate a password hash."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(
    subject: str,
    company_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": subject,
        "company_id": company_id,
        "role": role,
        "exp": expire,
        "type": "access"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(subject: str, company_id: str) -> str:
    """Create a JWT refresh token."""
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode = {
        "sub": subject,
        "company_id": company_id,
        "exp": expire,
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def get_encryption_key() -> bytes:
    """Get or generate encryption key for sensitive data."""
    if settings.ENCRYPTION_KEY:
        # Derive a proper Fernet key from the configured key
        key = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
        return base64.urlsafe_b64encode(key)
    raise ValueError("ENCRYPTION_KEY not configured")


def encrypt_value(value: str) -> str:
    """Encrypt a sensitive value (e.g., OAuth tokens)."""
    f = Fernet(get_encryption_key())
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a sensitive value."""
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_value.encode()).decode()
