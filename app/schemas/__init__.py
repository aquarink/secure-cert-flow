"""
Pydantic Schemas Package Export
"""

from app.schemas.auth import UserRegister, UserLogin, Token, TokenData, UserResponse, VerifyEmailRequest
from app.schemas.event import EventCreate, EventUpdate, EventResponse, EventDetailResponse
from app.schemas.template import (
    TemplateFieldBase,
    TemplateFieldCreate,
    TemplateFieldResponse,
    TemplateSetupRequest,
    TemplateResponse,
)
from app.schemas.batch import BatchResponse, BatchProgressResponse
from app.schemas.participant import ParticipantCreate, ParticipantResponse
from app.schemas.certificate import CertificateResponse, CertificateVerificationResponse
from app.schemas.claim import ClaimRequest, ClaimResponse
from app.schemas.paper import PaperBase, PaperCreate, PaperUpdate, PaperResponse, PaperBulkCreate
from app.schemas.attendance import AttendanceCreate, AttendanceResponse, AttendanceCheckInResult

__all__ = [
    "UserRegister",
    "UserLogin",
    "Token",
    "TokenData",
    "UserResponse",
    "VerifyEmailRequest",
    "EventCreate",
    "EventUpdate",
    "EventResponse",
    "EventDetailResponse",
    "TemplateFieldBase",
    "TemplateFieldCreate",
    "TemplateFieldResponse",
    "TemplateSetupRequest",
    "TemplateResponse",
    "BatchResponse",
    "BatchProgressResponse",
    "ParticipantCreate",
    "ParticipantResponse",
    "CertificateResponse",
    "CertificateVerificationResponse",
    "ClaimRequest",
    "ClaimResponse",
    "PaperBase",
    "PaperCreate",
    "PaperUpdate",
    "PaperResponse",
    "PaperBulkCreate",
    "AttendanceCreate",
    "AttendanceResponse",
    "AttendanceCheckInResult",
]
