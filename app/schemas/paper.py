"""
Pydantic Schemas for Paper Submissions
"""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PaperBase(BaseModel):
    paper_code: Optional[str] = Field(None, example="ICST-001")
    title: str = Field(..., example="Deep Learning for Automated Certificate Integrity")
    authors: Optional[str] = Field(None, example="Dr. Ahmad Farhan, Siti Nurhaliza")
    presenter_name: Optional[str] = Field(None, example="Dr. Ahmad Farhan")


class PaperCreate(PaperBase):
    pass


class PaperUpdate(BaseModel):
    paper_code: Optional[str] = None
    title: Optional[str] = None
    authors: Optional[str] = None
    presenter_name: Optional[str] = None


class PaperResponse(PaperBase):
    id: uuid.UUID
    event_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class PaperBulkCreate(BaseModel):
    papers: List[PaperCreate]
