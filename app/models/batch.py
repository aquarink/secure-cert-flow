"""
Batch Model for Tracking Bulk Import and Kafka Background Job Progress
"""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Batch(Base):
    __tablename__ = "batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    total_records = Column(Integer, default=0, nullable=False)
    processed_records = Column(Integer, default=0, nullable=False)
    success_records = Column(Integer, default=0, nullable=False)
    failed_records = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, processing, completed, failed
    error_log = Column(JSONB, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()"), nullable=False)

    # Relationships
    event = relationship("Event", back_populates="batches")
    participants = relationship("Participant", back_populates="batch")
    certificates = relationship("Certificate", back_populates="batch")

    @property
    def progress_percentage(self) -> float:
        if self.total_records == 0:
            return 0.0
        return round((self.processed_records / self.total_records) * 100, 2)
