"""
Event Model for Managing Conferences, Webinars, and Workshops
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    event_date = Column(Date, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="events")
    template = relationship("Template", back_populates="event", uselist=False, cascade="all, delete-orphan")
    batches = relationship("Batch", back_populates="event", cascade="all, delete-orphan")
    participants = relationship("Participant", back_populates="event", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="event", cascade="all, delete-orphan")
    papers = relationship("Paper", back_populates="event", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="event", cascade="all, delete-orphan")
