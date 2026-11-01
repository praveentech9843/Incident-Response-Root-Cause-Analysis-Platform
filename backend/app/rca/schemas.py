from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AnalysisStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    FAILED = "FAILED"


class CausalStatus(str, Enum):
    HYPOTHESIS = "HYPOTHESIS"
    SUPPORTED = "SUPPORTED"
    CONFIRMED = "CONFIRMED"
    UNVERIFIED = "UNVERIFIED"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RoleClassification(str, Enum):
    ROOT_CAUSE_CANDIDATE = "ROOT_CAUSE_CANDIDATE"
    CONTRIBUTING_FACTOR = "CONTRIBUTING_FACTOR"
    SYMPTOM = "SYMPTOM"
    UNKNOWN = "UNKNOWN"


class EvidenceType(str, Enum):
    LOG_EVENT = "LOG_EVENT"
    STACK_TRACE = "STACK_TRACE"
    EXCEPTION = "EXCEPTION"
    SERVICE_CONTEXT = "SERVICE_CONTEXT"
    DEPLOYMENT_CONTEXT = "DEPLOYMENT_CONTEXT"
    INFRASTRUCTURE_CONTEXT = "INFRASTRUCTURE_CONTEXT"
    METRIC = "METRIC"
    HISTORY = "HISTORY"
    DEPENDENCY_OBSERVATION = "DEPENDENCY_OBSERVATION"


class RCAEvidenceItem(BaseModel):
    """Normalized evidence item with a stable identifier and traceable database reference."""

    evidence_id: str = Field(description="Stable evidence identifier (e.g. EVT-101, EXC-101, ST-101, CTX-SERVICE-1)")
    evidence_type: EvidenceType
    source: str
    is_available: bool = Field(default=True, description="False if provider was not connected/unavailable")
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    db_reference: Dict[str, Any] = Field(
        default_factory=dict,
        description="Audit trail mapping back to PostgreSQL entity (e.g. parsed_log_id, context_id)",
    )


class RCAHypothesis(BaseModel):
    """Structured hypothesis explaining potential root cause or contributing factor."""

    hypothesis_id: str
    title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="List of verified evidence IDs (e.g. ['EVT-101', 'EXC-101'])",
    )
    contradicting_evidence: List[str] = Field(default_factory=list)
    reasoning: str
    causal_status: CausalStatus = Field(default=CausalStatus.HYPOTHESIS)
    role: RoleClassification = Field(default=RoleClassification.ROOT_CAUSE_CANDIDATE)


class RCAResult(BaseModel):
    """Result of Root Cause Analysis reasoning."""

    analysis_status: AnalysisStatus
    summary: str
    hypotheses: List[RCAHypothesis] = Field(default_factory=list)
    confidence: Optional[float] = None
    confidence_level: Optional[ConfidenceLevel] = None
    limitations: List[str] = Field(default_factory=list)
    provider: str
    model: str


class IncidentRCAAnalysisResponse(BaseModel):
    """API response model for an RCA analysis execution."""

    id: int
    incident_id: int
    analysis_id: str
    analysis_status: str
    provider: str
    model: str
    summary: str
    confidence: Optional[float] = None
    confidence_level: Optional[str] = None
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_snapshot: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentRCAHistoryResponse(BaseModel):
    """API response model for RCA analysis history."""

    incident_id: int
    total: int
    items: List[IncidentRCAAnalysisResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
