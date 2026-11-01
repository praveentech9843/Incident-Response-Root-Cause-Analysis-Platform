from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class IncidentContextItemResponse(BaseModel):
    """Schema representing an individual operational context category enrichment."""

    id: int
    incident_id: int
    context_category: str
    status: str
    data: Dict[str, Any]
    source: str
    collected_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EnrichedIncidentContextResponse(BaseModel):
    """Schema representing the aggregate operational context for an incident."""

    incident_id: int
    incident_title: str
    total_categories: int = Field(default=6, description="Total context categories evaluated")
    contexts: Dict[str, IncidentContextItemResponse] = Field(
        default_factory=dict,
        description="Keyed by category (service, deployment, infrastructure, metrics, history, dependencies)",
    )
    collected_at: datetime

    model_config = ConfigDict(from_attributes=True)
