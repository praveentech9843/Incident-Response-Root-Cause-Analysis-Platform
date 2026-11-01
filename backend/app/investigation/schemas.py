from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvestigationStatus(str, Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    INVESTIGATING = "INVESTIGATING"
    READY_FOR_VERIFICATION = "READY_FOR_VERIFICATION"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ActionType(str, Enum):
    OBSERVATION = "OBSERVATION"
    DIAGNOSTIC_CHECK = "DIAGNOSTIC_CHECK"
    CONFIG_REVIEW = "CONFIG_REVIEW"
    LOG_REVIEW = "LOG_REVIEW"
    METRIC_REVIEW = "METRIC_REVIEW"
    DEPENDENCY_CHECK = "DEPENDENCY_CHECK"
    FIX_APPLIED = "FIX_APPLIED"
    VERIFICATION = "VERIFICATION"
    OTHER = "OTHER"


class RecommendationReviewDecision(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TimelineEventType(str, Enum):
    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    INCIDENT_ASSIGNED = "INCIDENT_ASSIGNED"
    NOTE_ADDED = "NOTE_ADDED"
    ACTION_RECORDED = "ACTION_RECORDED"
    RECOMMENDATION_REVIEWED = "RECOMMENDATION_REVIEWED"
    VERIFICATION_CREATED = "VERIFICATION_CREATED"
    VERIFICATION_UPDATED = "VERIFICATION_UPDATED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    INCIDENT_REOPENED = "INCIDENT_REOPENED"
    STATUS_CHANGED = "STATUS_CHANGED"


class RootCauseConfirmed(str, Enum):
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    UNCONFIRMED = "UNCONFIRMED"
    UNKNOWN = "UNKNOWN"


# =====================================================================
# Investigation Schemas
# =====================================================================

class StartInvestigationRequest(BaseModel):
    assigned_to: Optional[str] = Field(default=None, description="Developer ID (development mode)")
    assigned_to_name: Optional[str] = Field(default=None, description="Developer display name")
    investigation_summary: Optional[str] = Field(default=None, description="Initial investigation plan/summary")


class UpdateInvestigationRequest(BaseModel):
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    status: Optional[InvestigationStatus] = None
    investigation_summary: Optional[str] = None


class InvestigationResponse(BaseModel):
    id: int
    incident_id: int
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    status: str
    investigation_summary: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# Investigation Notes Schemas
# =====================================================================

class CreateInvestigationNoteRequest(BaseModel):
    author: str = Field(..., min_length=1, description="Developer identifier")
    note: str = Field(..., min_length=1, description="Investigation note content")
    evidence_references: List[str] = Field(default_factory=list, description="Referenced evidence tokens")

    @model_validator(mode="after")
    def validate_non_whitespace(self):
        if not self.author.strip():
            raise ValueError("Author cannot be empty or whitespace only")
        if not self.note.strip():
            raise ValueError("Note cannot be empty or whitespace only")
        return self


class InvestigationNoteResponse(BaseModel):
    id: int
    incident_id: int
    investigation_id: int
    author: str
    note: str
    evidence_references: List[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestigationNoteListResponse(BaseModel):
    incident_id: int
    total: int
    notes: List[InvestigationNoteResponse]


# =====================================================================
# Investigation Actions Schemas
# =====================================================================

class CreateInvestigationActionRequest(BaseModel):
    action_type: ActionType
    description: str = Field(..., min_length=1, description="What was investigated/performed externally")
    performed_by: str = Field(..., min_length=1, description="Developer identifier")
    result: str = Field(..., min_length=1, description="Observed outcome/findings")
    evidence_references: List[str] = Field(default_factory=list, description="Referenced evidence tokens")

    @model_validator(mode="after")
    def validate_non_whitespace(self):
        if not self.description.strip():
            raise ValueError("Description cannot be empty or whitespace only")
        if not self.performed_by.strip():
            raise ValueError("performed_by cannot be empty or whitespace only")
        if not self.result.strip():
            raise ValueError("Result cannot be empty or whitespace only")
        return self


class InvestigationActionResponse(BaseModel):
    id: int
    incident_id: int
    investigation_id: int
    action_type: str
    description: str
    performed_by: str
    result: str
    evidence_references: List[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestigationActionListResponse(BaseModel):
    incident_id: int
    total: int
    actions: List[InvestigationActionResponse]


# =====================================================================
# Recommendation Reviews Schemas
# =====================================================================

class CreateRecommendationReviewRequest(BaseModel):
    reviewed_by: str = Field(..., min_length=1, description="Developer identifier")
    decision: RecommendationReviewDecision
    reason: Optional[str] = Field(default=None, description="Justification for decision")

    @model_validator(mode="after")
    def validate_decision_reason(self):
        if not self.reviewed_by.strip():
            raise ValueError("reviewed_by cannot be empty or whitespace only")
        if self.decision in (RecommendationReviewDecision.REJECTED, RecommendationReviewDecision.DEFERRED):
            if not self.reason or not self.reason.strip():
                raise ValueError(f"Reason is required when decision is {self.decision.value}")
        return self


class RecommendationReviewResponse(BaseModel):
    id: int
    incident_id: int
    investigation_id: Optional[int] = None
    recommendation_id: str
    reviewed_by: str
    decision: str
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendationReviewListResponse(BaseModel):
    incident_id: int
    total: int
    reviews: List[RecommendationReviewResponse]


# =====================================================================
# Verification Steps Schemas
# =====================================================================

class CreateVerificationStepRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Verification check title")
    description: Optional[str] = None
    is_required: bool = True
    evidence_references: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_title(self):
        if not self.title.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return self


class UpdateVerificationStepRequest(BaseModel):
    status: VerificationStatus
    result: Optional[str] = None
    verified_by: Optional[str] = None
    evidence_references: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_verifier(self):
        if self.status in (VerificationStatus.PASSED, VerificationStatus.FAILED):
            if not self.verified_by or not self.verified_by.strip():
                raise ValueError(f"verified_by is required when status is set to {self.status.value}")
        return self


class VerificationStepResponse(BaseModel):
    id: int
    incident_id: int
    investigation_id: int
    title: str
    description: Optional[str] = None
    is_required: bool
    status: str
    result: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    evidence_references: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerificationStepListResponse(BaseModel):
    incident_id: int
    total: int
    pending_count: int
    passed_count: int
    failed_count: int
    steps: List[VerificationStepResponse]


# =====================================================================
# Resolution & Reopen Schemas
# =====================================================================

class ResolveIncidentRequest(BaseModel):
    resolved_by: str = Field(..., min_length=1, description="Developer identifier")
    resolution_summary: str = Field(..., min_length=1, description="Summary of root cause and applied fix")
    root_cause_confirmed: RootCauseConfirmed = Field(
        default=RootCauseConfirmed.UNKNOWN,
        description="Whether AI root cause hypothesis was confirmed by developer",
    )
    evidence_references: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_non_whitespace(self):
        if not self.resolved_by.strip():
            raise ValueError("resolved_by cannot be empty or whitespace only")
        if not self.resolution_summary.strip():
            raise ValueError("resolution_summary cannot be empty or whitespace only")
        return self


class ResolveIncidentResponse(BaseModel):
    incident_id: int
    status: str
    resolved_at: datetime
    resolved_by: str
    resolution_summary: str
    root_cause_confirmed: str
    investigation_status: str


class ReopenIncidentRequest(BaseModel):
    reopened_by: str = Field(..., min_length=1, description="Developer identifier")
    reason: Optional[str] = None

    @model_validator(mode="after")
    def validate_non_whitespace(self):
        if not self.reopened_by.strip():
            raise ValueError("reopened_by cannot be empty or whitespace only")
        return self


class ReopenIncidentResponse(BaseModel):
    incident_id: int
    status: str
    reopened_by: str
    investigation_status: str
    message: str


# =====================================================================
# Timeline Schemas
# =====================================================================

class TimelineEventResponse(BaseModel):
    id: int
    incident_id: int
    investigation_id: Optional[int] = None
    event_type: str
    actor: str
    timestamp: datetime
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TimelineEventListResponse(BaseModel):
    incident_id: int
    total: int
    events: List[TimelineEventResponse]
