"""
Pydantic Schemas for Event Management
"""

import uuid
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.schemas.template import TemplateResponse


class EventBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    event_type: Optional[str] = Field("general", description="Event category: general, webinar, workshop, conference, competition")
    location: str = Field(..., min_length=2, max_length=255)
    event_date: date
    description: Optional[str] = None
    is_cert_open: Optional[bool] = False


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    event_type: Optional[str] = None
    location: Optional[str] = Field(None, min_length=2, max_length=255)
    event_date: Optional[date] = None
    description: Optional[str] = None
    status: Optional[str] = None
    is_cert_open: Optional[bool] = None


class EventResponse(EventBase):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    is_cert_open: bool = False
    created_at: datetime
    updated_at: datetime
    participant_count: Optional[int] = 0
    certificate_count: Optional[int] = 0

    class Config:
        from_attributes = True


class EventDetailResponse(EventResponse):
    template: Optional[TemplateResponse] = None
