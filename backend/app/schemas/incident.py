from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.parsed_log import ParsedLogEvent


class IncidentResponse(BaseModel):
    """Schema representing an incident formed by correlated parsed log events."""

    id: int
    incident_key: str
    title: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    event_count: int
    service_count: int
    correlation_reason: str
    correlation_confidence: Optional[float] = None
    resolved_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None
    resolved_by: Optional[str] = None
    root_cause_confirmed: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentDetailResponse(IncidentResponse):
    """Schema representing an incident with its constituent correlated events."""

    events: List[ParsedLogEvent] = Field(
        default_factory=list,
        description="Chronologically ordered constituent parsed events",
    )

    model_config = ConfigDict(from_attributes=True)


class IncidentListResponse(BaseModel):
    """Paginated list of incidents."""

    items: List[IncidentResponse]
    total: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)


class CorrelateIncidentsRequest(BaseModel):
    """Optional parameters for correlation run."""

    log_id: Optional[int] = Field(
        None,
        description="If provided, correlates parsed events belonging to this log file",
    )
    time_window_seconds: Optional[int] = Field(
        None,
        description="Override the default temporal correlation window (seconds)",
    )


class CorrelateIncidentsResponse(BaseModel):
    """Outcome of an incident correlation execution."""

    events_considered: int
    incidents_created: int
    incidents_existing: int
    incidents: List[IncidentResponse]

    model_config = ConfigDict(from_attributes=True)
