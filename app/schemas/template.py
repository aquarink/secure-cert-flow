"""
Pydantic Schemas for Template Design, Dynamic Coordinates, and Placement Setup
"""

import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class TemplateFieldBase(BaseModel):
    field_key: str = Field(..., description="Unique key matching Excel column, e.g. nama, judul_paper, peran")
    label: str = Field(..., description="Human readable label")
    pos_x: int = Field(..., description="X coordinate in pixels")
    pos_y: int = Field(..., description="Y coordinate in pixels")
    font_family: str = Field(default="DejaVuSans-Bold.ttf")
    font_size: int = Field(default=36, ge=8, le=200)
    font_color: str = Field(default="#1E293B")
    text_align: str = Field(default="center", description="'left', 'center', or 'right'")
    max_width: Optional[int] = None
    is_required: bool = True


class TemplateFieldCreate(TemplateFieldBase):
    pass


class TemplateFieldResponse(TemplateFieldBase):
    id: uuid.UUID
    template_id: uuid.UUID

    class Config:
        from_attributes = True


class TemplateSetupRequest(BaseModel):
    width: Optional[int] = 1920
    height: Optional[int] = 1080
    signature_x: Optional[int] = None
    signature_y: Optional[int] = None
    signature_width: Optional[int] = None
    signature_height: Optional[int] = None
    qr_x: Optional[int] = None
    qr_y: Optional[int] = None
    qr_size: int = Field(default=150, ge=50, le=500)
    qr_base_url: str = Field(default="/claim/")
    cert_number_prefix: str = Field(default="CERT")
    cert_number_x: Optional[int] = None
    cert_number_y: Optional[int] = None
    cert_number_font_size: int = Field(default=24, ge=8, le=100)
    cert_number_color: str = Field(default="#1E293B")
    fields: Optional[List[TemplateFieldCreate]] = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    background_image_url: str
    width: int
    height: int
    signature_image_url: Optional[str] = None
    signature_x: Optional[int] = None
    signature_y: Optional[int] = None
    signature_width: Optional[int] = None
    signature_height: Optional[int] = None
    qr_x: Optional[int] = None
    qr_y: Optional[int] = None
    qr_size: int
    qr_base_url: str
    cert_number_prefix: str
    cert_number_x: Optional[int] = None
    cert_number_y: Optional[int] = None
    cert_number_font_size: int
    cert_number_color: str
    fields: List[TemplateFieldResponse] = []

    class Config:
        from_attributes = True
