"""
Certificate Model for Storing Generated Certificate Records and Claim Codes
"""

import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("batches.id", ondelete="SET NULL"), nullable=True)
    
    certificate_number = Column(String(100), unique=True, nullable=False, index=True)
    claim_code = Column(String(16), unique=True, nullable=False, index=True)
    pdf_url = Column(String(1024), nullable=True)
    image_url = Column(String(1024), nullable=True)
    checksum_sha256 = Column(String(64), nullable=True)
    status = Column(String(50), default="PENDING", nullable=False, index=True)  # PENDING, PROCESSING, GENERATED, FAILED, CLAIMED
    error_message = Column(Text, nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    download_count = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()"), nullable=False)

    # Relationships
    event = relationship("Event", back_populates="certificates")
    participant = relationship("Participant", back_populates="certificate")
    batch = relationship("Batch", back_populates="certificates")
