"""
Authentication Endpoints: Register, Login, Email Verification, and Profile
"""

import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    UserResponse,
    VerifyEmailRequest
)
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    generate_verification_token
)
from app.api.deps import get_current_user
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Registers a new organizer/user account.
    Generates a dummy verification token printed to console for email verification.
    """
    existing = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah terdaftar. Silakan gunakan email lain atau login.",
        )

    verification_token = generate_verification_token()
    user = User(
        email=user_data.email.lower(),
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        is_active=True,
        is_verified=True,  # Set active for seamless MVP test
        verification_token=verification_token
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Log dummy verification link to server console
    verification_link = f"{settings.APP_BASE_URL}/verify-email?email={user.email}&token={verification_token}"
    logger.info("=" * 60)
    logger.info("[DUMMY EMAIL SERVICE] Verifikasi Akun Baru:")
    logger.info(f"Penerima : {user.email}")
    logger.info(f"Nama     : {user.full_name}")
    logger.info(f"Link     : {verification_link}")
    logger.info("=" * 60)

    return user


@router.post("/login", response_model=Token)
def login_user(user_data: UserLogin, response: Response, db: Session = Depends(get_db)):
    """
    Authenticates user credentials and returns a JWT access token.
    Also sets an HTTP-only cookie for browser frontend sessions.
    """
    user = db.query(User).filter(User.email == user_data.email.lower()).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password yang Anda masukkan salah.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun ini telah dinonaktifkan.",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "name": user.full_name},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Set cookie for TailAdmin frontend
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Returns currently authenticated user profile"""
    return current_user


@router.post("/verify-email")
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verifies dummy email token and activates user account"""
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")

    if user.verification_token != data.token:
        raise HTTPException(status_code=400, detail="Token verifikasi salah atau kedaluwarsa.")

    user.is_verified = True
    user.verification_token = None
    db.commit()

    return {"message": "Email berhasil diverifikasi. Akun Anda telah aktif!"}
