"""
Template and Dynamic Field Models for Certificate Layout Design
"""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Template(Base):
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), default="Template Utama", nullable=False)
    role_target = Column(String(100), default="ALL", nullable=False)  # ALL, Presenter, Participant, Author, Speaker, Committee
    is_default = Column(Boolean, default=True, nullable=False)
    background_image_url = Column(String(1024), nullable=False)
    width = Column(Integer, default=1920, nullable=False)
    height = Column(Integer, default=1080, nullable=False)
    
    # Signature Overlay
    signature_image_url = Column(String(1024), nullable=True)
    signature_x = Column(Integer, nullable=True)
    signature_y = Column(Integer, nullable=True)
    signature_width = Column(Integer, nullable=True)
    signature_height = Column(Integer, nullable=True)

    # QR Code Overlay
    qr_x = Column(Integer, nullable=True)
    qr_y = Column(Integer, nullable=True)
    qr_size = Column(Integer, default=150, nullable=False)
    qr_base_url = Column(String(500), default="/claim/", nullable=False)

    # Auto-numbering Display
    cert_number_prefix = Column(String(50), default="CERT", nullable=False)
    cert_number_x = Column(Integer, nullable=True)
    cert_number_y = Column(Integer, nullable=True)
    cert_number_font_size = Column(Integer, default=24, nullable=False)
    cert_number_color = Column(String(20), default="#1E293B", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()"), nullable=False)

    # Relationships
    event = relationship("Event", back_populates="templates")
    fields = relationship("TemplateField", back_populates="template", cascade="all, delete-orphan", order_by="TemplateField.pos_y")


class TemplateField(Base):
    __tablename__ = "template_fields"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True)
    field_key = Column(String(100), nullable=False)  # e.g., 'nama', 'judul_paper', 'peran'
    label = Column(String(100), nullable=False)
    pos_x = Column(Integer, nullable=False)
    pos_y = Column(Integer, nullable=False)
    font_family = Column(String(100), default="DejaVuSans-Bold.ttf", nullable=False)
    font_size = Column(Integer, default=36, nullable=False)
    font_color = Column(String(20), default="#1E293B", nullable=False)
    text_align = Column(String(20), default="center", nullable=False)  # 'left', 'center', 'right'
    max_width = Column(Integer, nullable=True)
    is_required = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("template_id", "field_key", name="uq_template_field_key"),
    )

    # Relationships
    template = relationship("Template", back_populates="fields")
