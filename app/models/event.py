"""
Event Model for Managing Conferences, Webinars, Workshops, Competitions, and General Events
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    event_type = Column(String(50), default="general", nullable=False)  # general, webinar, workshop, conference, competition
    location = Column(String(255), nullable=False)
    event_date = Column(Date, nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    is_cert_open = Column(Boolean, default=False, nullable=False)  # Panitia toggle to release certificate download
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="events")
    templates = relationship("Template", back_populates="event", cascade="all, delete-orphan", order_by="Template.created_at")
    batches = relationship("Batch", back_populates="event", cascade="all, delete-orphan")
    participants = relationship("Participant", back_populates="event", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="event", cascade="all, delete-orphan")
    papers = relationship("Paper", back_populates="event", cascade="all, delete-orphan")
    attendances = relationship("Attendance", back_populates="event", cascade="all, delete-orphan")

    @property
    def template(self):
        """Returns the default template or first template for backwards compatibility"""
        if self.templates:
            for t in self.templates:
                if t.is_default:
                    return t
            return self.templates[0]
        return None
