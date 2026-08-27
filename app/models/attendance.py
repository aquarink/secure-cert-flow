"""
Attendance Record Model
Captures strict participant check-ins with live camera capture, geolocation, and IP tracking.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    paper_id = Column(UUID(as_uuid=True), ForeignKey("papers.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone_number = Column(String(50), nullable=True)
    institution = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)  # Presenter, Author, Attendee, Guest, Committee
    paper_title = Column(Text, nullable=True)
    photo_url = Column(String(1024), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy_meters = Column(Float, nullable=True)
    ip_address = Column(String(100), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    event = relationship("Event", back_populates="attendances")
    paper = relationship("Paper", back_populates="attendances")

    def __repr__(self):
        return f"<Attendance {self.full_name} ({self.role}) - Event {self.event_id}>"
