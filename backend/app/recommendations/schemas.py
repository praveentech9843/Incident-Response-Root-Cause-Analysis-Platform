from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RecommendationType(str, Enum):
    INVESTIGATION = "INVESTIGATION"
    DIAGNOSTIC_VERIFICATION = "DIAGNOSTIC_VERIFICATION"
    FIX = "FIX"
    PREVENTION = "PREVENTION"
    VERIFICATION = "VERIFICATION"


class RecommendationConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class RecommendationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DISMISSED = "DISMISSED"


class RecommendationGenerationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    FAILED = "FAILED"


class RecommendationItem(BaseModel):
    """Structured operational recommendation derived strictly from validated RCA evidence."""

    recommendation_id: str = Field(description="Unique recommendation ID (e.g. rec-abc12345)")
    type: RecommendationType
    title: str
    description: str
    rationale: str
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="List of verified evidence IDs (e.g. ['EVT-101', 'EXC-101'])",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: RecommendationConfidenceLevel
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    expected_impact: str
    prerequisites: List[str] = Field(default_factory=list)
    verification_steps: List[str] = Field(default_factory=list)
    status: RecommendationStatus = Field(default=RecommendationStatus.PROPOSED)


class RecommendationResult(BaseModel):
    """Complete recommendation generation result from provider or generator."""

    status: RecommendationGenerationStatus
    analysis_id: str
    summary: str
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    provider: str
    model: str


class IncidentRecommendationResponse(BaseModel):
    """API response model for an individual recommendation record."""

    id: int
    recommendation_id: str
    incident_id: int
    rca_analysis_id: int
    type: str
    title: str
    description: str
    rationale: str
    supporting_evidence: List[str] = Field(default_factory=list)
    confidence: float
    confidence_level: str
    risk_level: str
    expected_impact: str
    prerequisites: List[str] = Field(default_factory=list)
    verification_steps: List[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentRecommendationListResponse(BaseModel):
    """API response model for current recommendations for an incident."""

    incident_id: int
    rca_analysis_id: int
    status: str
    total_recommendations: int
    recommendations: List[IncidentRecommendationResponse] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    provider: str
    model: str
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendationRunHistoryItem(BaseModel):
    """Summary of a past recommendation generation run."""

    rca_analysis_id: int
    run_timestamp: datetime
    recommendations_count: int
    recommendations: List[IncidentRecommendationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class IncidentRecommendationHistoryResponse(BaseModel):
    """API response model for historical recommendation runs."""

    incident_id: int
    total_recommendations: int
    items: List[IncidentRecommendationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
