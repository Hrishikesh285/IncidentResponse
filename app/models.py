"""Pydantic models for request/response validation and the MongoDB incident document."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# MongoDB incident document shape
# ---------------------------------------------------------------------------

class Incident(BaseModel):
    """Represents a single production incident stored in MongoDB."""

    incident_id: str = Field(..., description="Unique ID, format INC-0001")
    title: str = Field(..., description="Short summary of the incident")
    service: str = Field(..., description="Affected service name")
    severity: str = Field(..., description="SEV1, SEV2, or SEV3")
    error_log: str = Field(..., description="Raw log lines or stack trace")
    symptoms: str = Field(..., description="What the on-call engineer observed")
    root_cause: str = Field(default="", description="Filled when resolved")
    fix_steps: List[str] = Field(default_factory=list, description="Ordered fix steps")
    resolution_minutes: int = Field(default=0, description="Time to resolve in minutes")
    status: str = Field(default="open", description="open or resolved")
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: Optional[datetime] = Field(default=None)


# ---------------------------------------------------------------------------
# API request / response bodies
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Body for POST /api/incidents/analyze."""

    title: str
    service: str
    severity: str
    error_log: str
    symptoms: str
    use_memory: bool = True


class ResolveRequest(BaseModel):
    """Body for POST /api/incidents/{incident_id}/resolve."""

    root_cause: str
    fix_steps: List[str]
    resolution_minutes: int


class AnalysisResult(BaseModel):
    """Full response returned by the analyze endpoint."""

    incident_id: str
    diagnosis: str
    likely_root_cause: str
    recommended_steps: List[str]
    confidence: str
    matched_incident_id: Optional[str] = None
    match_reason: str = ""
    recalled_incidents: List[dict] = Field(default_factory=list)
    memory_used: bool = False
    latency_ms: float = 0.0
