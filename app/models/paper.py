"""
Paper / Submission Model
Stores conference papers, titles, authors, and presenter mappings for each event.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    paper_code = Column(String(50), nullable=True, index=True)  # e.g., "ICST-001"
    title = Column(Text, nullable=False)
    authors = Column(Text, nullable=True)  # Comma-separated or authors string
    presenter_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    event = relationship("Event", back_populates="papers")
    attendances = relationship("Attendance", back_populates="paper")

    def __repr__(self):
        return f"<Paper {self.paper_code}: {self.title[:30]}>"
