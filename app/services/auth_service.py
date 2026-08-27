"""
Authentication and Cryptographic Security Services
Handles password hashing, JWT encoding/decoding, and verification tokens.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hashes plain password using bcrypt algorithm"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored bcrypt hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encodes JWT access token with user payload and expiration time"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and verifies a JWT token. Returns payload dict or None if invalid"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_claim_code(length: int = 8) -> str:
    """Generates an 8-character uppercase alphanumeric unique claim code"""
    alphabet = string.ascii_uppercase + string.digits
    # Exclude easily confused characters: O, 0, I, 1
    safe_alphabet = "".join([c for c in alphabet if c not in "O0I1"])
    return "".join(secrets.choice(safe_alphabet) for _ in range(length))


def generate_verification_token() -> str:
    """Generates a secure random 32-byte hex token for email verification"""
    return secrets.token_hex(16)
