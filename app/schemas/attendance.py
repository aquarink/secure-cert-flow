"""
Pydantic Schemas for Attendance Check-in and Management
"""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class AttendanceCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, example="Dr. Ahmad Farhan, S.Kom., M.T.")
    institution: str = Field(..., min_length=2, max_length=255, example="UIN Syarif Hidayatullah Jakarta")
    role: str = Field("Participant", example="Participant")  # Participant, Presenter, Author, Speaker, Guest, Committee
    paper_id: Optional[uuid.UUID] = None
    paper_title: Optional[str] = None
    photo_base64: str = Field(..., description="Live captured camera frame in base64 format")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_meters: Optional[float] = None


class AttendanceResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    paper_id: Optional[uuid.UUID] = None
    full_name: str
    institution: str
    role: str
    paper_title: Optional[str] = None
    photo_url: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_meters: Optional[float] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    claim_code: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceCheckInResult(BaseModel):
    success: bool
    check_in_id: uuid.UUID
    full_name: str
    event_name: str
    role: str
    claim_code: Optional[str] = None
    cert_url: Optional[str] = None
    timestamp: datetime
    message: str
