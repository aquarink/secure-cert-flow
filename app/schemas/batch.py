"""
Pydantic Schemas for Bulk Import Batches and Kafka Processing Progress
"""

import uuid
from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel


class BatchResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    filename: str
    total_records: int
    processed_records: int
    success_records: int
    failed_records: int
    status: str
    error_log: List[Any] = []
    created_at: datetime
    updated_at: datetime
    progress_percentage: float

    class Config:
        from_attributes = True


class BatchProgressResponse(BaseModel):
    batch_id: uuid.UUID
    event_id: uuid.UUID
    status: str
    total: int
    processed: int
    success: int
    failed: int
    percentage: float
    is_completed: bool
