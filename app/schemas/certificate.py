"""
Pydantic Schemas for Certificate Records and Verification
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CertificateResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    participant_id: uuid.UUID
    batch_id: Optional[uuid.UUID] = None
    certificate_number: str
    claim_code: str
    pdf_url: Optional[str] = None
    image_url: Optional[str] = None
    checksum_sha256: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    claimed_at: Optional[datetime] = None
    download_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CertificateVerificationResponse(BaseModel):
    is_valid: bool
    certificate_number: Optional[str] = None
    claim_code: Optional[str] = None
    participant_name: Optional[str] = None
    participant_role: Optional[str] = None
    paper_title: Optional[str] = None
    event_name: Optional[str] = None
    event_location: Optional[str] = None
    event_date: Optional[str] = None
    image_url: Optional[str] = None
    pdf_url: Optional[str] = None
    checksum_sha256: Optional[str] = None
    status: Optional[str] = None
    is_cert_open: bool = False
    message: str
