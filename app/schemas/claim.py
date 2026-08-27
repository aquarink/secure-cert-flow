"""
Pydantic Schemas for Participant Claiming Flow
"""

from typing import Optional
from pydantic import BaseModel, Field


class ClaimRequest(BaseModel):
    claim_code: str = Field(..., min_length=4, max_length=16, description="8-character alphanumeric claim code")


class ClaimResponse(BaseModel):
    success: bool
    message: str
    is_cert_open: bool = False
    certificate_number: Optional[str] = None
    participant_name: Optional[str] = None
    event_name: Optional[str] = None
    event_date: Optional[str] = None
    image_url: Optional[str] = None
    download_url: Optional[str] = None
    checksum_sha256: Optional[str] = None
