"""
Authentication and Cryptographic Security Services
Handles native bcrypt password hashing, JWT encoding/decoding, and verification tokens.
"""

import bcrypt
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from app.config import settings


def hash_password(password: str) -> str:
    """Hashes plain password using native bcrypt algorithm"""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against stored bcrypt hash string"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


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
