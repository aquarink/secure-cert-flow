"""
Pydantic Schemas for Participant Management
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field


class ParticipantBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(..., min_length=2, max_length=100)
    paper_title: Optional[str] = None
    custom_data: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ParticipantCreate(ParticipantBase):
    pass


class ParticipantResponse(ParticipantBase):
    id: uuid.UUID
    event_id: uuid.UUID
    batch_id: Optional[uuid.UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True
