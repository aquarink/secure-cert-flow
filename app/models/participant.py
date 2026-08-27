"""
Participant Model for Event Attendees, Authors, and Presenters
"""

import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Participant(Base):
    __tablename__ = "participants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="SET NULL"), nullable=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)  # Author, Presenter, Attendee, etc.
    paper_title = Column(Text, nullable=True)
    custom_data = Column(JSONB, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    # Relationships
    event = relationship("Event", back_populates="participants")
    batch = relationship("Batch", back_populates="participants")
    certificate = relationship("Certificate", back_populates="participant", uselist=False, cascade="all, delete-orphan")
