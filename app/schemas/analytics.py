"""
Event Analytics and Statistics Schemas
Provides data contracts for comprehensive event reporting, role breakdown,
attendance statistics, claim rates, and institution analysis.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


class RoleMetric(BaseModel):
    role: str
    registered_count: int
    attendance_count: int
    certificate_count: int
    claimed_count: int
    unclaimed_count: int
    claim_rate_percentage: float


class InstitutionMetric(BaseModel):
    institution: str
    count: int
    percentage: float


class HourlyMetric(BaseModel):
    time_bucket: str
    count: int


class TemplateUsageMetric(BaseModel):
    template_id: Optional[str] = None
    template_name: str
    certificate_count: int
    claimed_count: int


class EventAnalyticsSummary(BaseModel):
    total_participants: int
    total_attendances: int
    total_certificates: int
    total_claimed: int
    total_unclaimed: int
    claim_rate_percentage: float
    total_downloads: int
    total_papers: int
    papers_with_presenter: int
    papers_without_presenter: int
    geotag_verified_count: int
    geotag_percentage: float


class EventAnalyticsResponse(BaseModel):
    event_id: str
    event_name: str
    is_cert_open: bool
    summary: EventAnalyticsSummary
    role_metrics: List[RoleMetric]
    top_institutions: List[InstitutionMetric]
    hourly_attendances: List[HourlyMetric]
    template_usage: List[TemplateUsageMetric]
    generated_at: datetime
