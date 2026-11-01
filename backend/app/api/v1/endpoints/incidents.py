from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_acting_identity, get_current_user, require_roles
from app.alerting.engine import evaluate_incident_alerts
from app.core.database import get_db
from app.core.security import Role
from app.models.incident import Incident
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.repositories.incident_repository import IncidentRepository
from app.repositories.incident_context_repository import IncidentContextRepository
from app.schemas.incident import (
    IncidentResponse,
    IncidentDetailResponse,
    IncidentListResponse,
    CorrelateIncidentsRequest,
    CorrelateIncidentsResponse,
)
from app.schemas.incident_context import (
    IncidentContextItemResponse,
    EnrichedIncidentContextResponse,
)
from app.rca.schemas import (
    IncidentRCAAnalysisResponse,
    IncidentRCAHistoryResponse,
)
from app.recommendations.schemas import (
    IncidentRecommendationHistoryResponse,
    IncidentRecommendationListResponse,
    IncidentRecommendationResponse,
)
from app.services.correlation_service import CorrelationService
from app.services.context_enrichment_service import ContextEnrichmentService
from app.services.rca_service import RCAService
from app.services.recommendation_service import RecommendationService
from app.investigation.schemas import (
    StartInvestigationRequest,
    UpdateInvestigationRequest,
    InvestigationResponse,
    CreateInvestigationNoteRequest,
    InvestigationNoteResponse,
    InvestigationNoteListResponse,
    CreateInvestigationActionRequest,
    InvestigationActionResponse,
    InvestigationActionListResponse,
    CreateRecommendationReviewRequest,
    RecommendationReviewResponse,
    RecommendationReviewListResponse,
    CreateVerificationStepRequest,
    UpdateVerificationStepRequest,
    VerificationStepResponse,
    VerificationStepListResponse,
    ResolveIncidentRequest,
    ResolveIncidentResponse,
    ReopenIncidentRequest,
    ReopenIncidentResponse,
    TimelineEventListResponse,
)
from app.services.investigation_service import InvestigationService

router = APIRouter(prefix="/incidents", tags=["Incidents"])



def get_correlation_service(db: Session = Depends(get_db)) -> CorrelationService:
    """Dependency provider for CorrelationService."""
    repo = IncidentRepository(db)
    return CorrelationService(repo)


def get_context_service(db: Session = Depends(get_db)) -> ContextEnrichmentService:
    """Dependency provider for ContextEnrichmentService."""
    incident_repo = IncidentRepository(db)
    context_repo = IncidentContextRepository(db)
    return ContextEnrichmentService(
        db=db,
        incident_repo=incident_repo,
        context_repo=context_repo,
    )


def get_rca_service(db: Session = Depends(get_db)) -> RCAService:
    """Dependency provider for RCAService."""
    return RCAService(db=db)


def get_recommendation_service(db: Session = Depends(get_db)) -> RecommendationService:
    """Dependency provider for RecommendationService."""
    return RecommendationService(db=db)


def get_investigation_service(db: Session = Depends(get_db)) -> InvestigationService:
    """Dependency provider for InvestigationService."""
    return InvestigationService(db=db)



@router.post(
    "/correlate",
    response_model=CorrelateIncidentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Run deterministic incident correlation",
    description=(
        "Analyzes eligible parsed log events and identifies correlated incident clusters "
        "using explicit correlation identifiers, temporal proximity windows, and cross-service evidence. "
        "Prevents duplicate incident creation deterministically."
    ),
)
def correlate_incidents(
    payload: Optional[CorrelateIncidentsRequest] = None,
    log_id: Optional[int] = Query(None, description="Filter correlation to a specific log file ID"),
    time_window_seconds: Optional[int] = Query(None, description="Override temporal window (seconds)"),
    service: CorrelationService = Depends(get_correlation_service),
) -> CorrelateIncidentsResponse:
    """Execute correlation on candidate parsed logs."""
    # Allow parameters from request body or query parameters
    effective_log_id = payload.log_id if (payload and payload.log_id is not None) else log_id
    effective_window = (
        payload.time_window_seconds
        if (payload and payload.time_window_seconds is not None)
        else time_window_seconds
    )
    return service.correlate_incidents(
        log_id=effective_log_id,
        time_window_seconds=effective_window,
    )


@router.get(
    "",
    response_model=IncidentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List correlated incidents",
    description="Returns a paginated list of real correlated incidents persisted in PostgreSQL.",
)
def get_incidents(
    status: Optional[str] = Query(None, description="Filter by status (OPEN, RESOLVED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    page: Optional[int] = Query(None, ge=1, description="Page number (1-indexed)"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Page size"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset pagination"),
    service: CorrelationService = Depends(get_correlation_service),
) -> IncidentListResponse:
    """Retrieve paginated incidents from database."""
    eff_limit = page_size if page_size is not None else limit
    eff_offset = ((page - 1) * eff_limit) if page is not None else offset
    return service.get_incidents(
        status_filter=status,
        severity_filter=severity,
        limit=eff_limit,
        offset=eff_offset,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get incident detail with correlated events",
    description=(
        "Retrieves detailed incident metadata and its constituent parsed log events, "
        "ordered chronologically."
    ),
)
def get_incident(
    incident_id: int,
    service: CorrelationService = Depends(get_correlation_service),
) -> IncidentDetailResponse:
    """Retrieve a single incident by ID along with its correlated parsed events."""
    return service.get_incident_detail(incident_id=incident_id)


# =============================================================================
# Phase 4: Context Enrichment Endpoints
# =============================================================================


@router.post(
    "/{incident_id}/enrich",
    response_model=EnrichedIncidentContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Enrich incident with operational context",
    description=(
        "Executes context enrichment for an existing incident across service, deployment, "
        "infrastructure, metrics, history, and dependencies categories. Truthfully captures "
        "available evidence and explicit integration statuses without fabricating operational data."
    ),
)
def enrich_incident(
    incident_id: int,
    service: ContextEnrichmentService = Depends(get_context_service),
) -> EnrichedIncidentContextResponse:
    """Trigger context enrichment for a correlated incident."""
    return service.enrich_incident(incident_id=incident_id)


@router.get(
    "/{incident_id}/context",
    response_model=EnrichedIncidentContextResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all enriched operational contexts for an incident",
    description=(
        "Returns all 6 operational context categories for the incident, with explicit "
        "availability statuses (AVAILABLE, NOT_CONNECTED, UNAVAILABLE, INTEGRATION_REQUIRED)."
    ),
)
def get_incident_context(
    incident_id: int,
    service: ContextEnrichmentService = Depends(get_context_service),
) -> EnrichedIncidentContextResponse:
    """Retrieve all operational context categories for an incident."""
    return service.get_incident_context(incident_id=incident_id)


@router.get(
    "/{incident_id}/context/{category}",
    response_model=IncidentContextItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Get specific operational context category",
    description=(
        "Returns a single operational context category for the incident (e.g., service, "
        "deployment, infrastructure, metrics, history, dependencies)."
    ),
)
def get_incident_context_category(
    incident_id: int,
    category: str,
    service: ContextEnrichmentService = Depends(get_context_service),
) -> IncidentContextItemResponse:
    """Retrieve a specific context category for an incident."""
    return service.get_incident_context_category(incident_id=incident_id, category_name=category)


@router.post(
    "/{incident_id}/rca",
    response_model=IncidentRCAAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Run AI-assisted Root Cause Analysis",
    description=(
        "Executes evidence-grounded root-cause analysis over the controlled evidence package. "
        "Strictly forbids hallucinated metrics/deployments and validates all evidence citations."
    ),
)
def run_incident_rca(
    incident_id: int,
    service: RCAService = Depends(get_rca_service),
) -> IncidentRCAAnalysisResponse:
    """Run evidence-grounded RCA against incident data and context."""
    return service.run_incident_rca(incident_id=incident_id)


@router.get(
    "/{incident_id}/rca",
    response_model=IncidentRCAAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest Root Cause Analysis",
    description="Retrieves the most recent RCA analysis generated for the incident.",
)
def get_latest_rca(
    incident_id: int,
    service: RCAService = Depends(get_rca_service),
) -> IncidentRCAAnalysisResponse:
    """Retrieve latest RCA analysis for an incident."""
    return service.get_latest_rca(incident_id=incident_id)


@router.get(
    "/{incident_id}/rca/history",
    response_model=IncidentRCAHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get RCA analysis history",
    description="Returns all previous RCA analyses executed for this incident.",
)
def get_rca_history(
    incident_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: RCAService = Depends(get_rca_service),
) -> IncidentRCAHistoryResponse:
    """Retrieve RCA analysis history for an incident."""
    return service.get_rca_history(incident_id=incident_id, limit=limit, offset=offset)


@router.get(
    "/{incident_id}/rca/{analysis_id}",
    response_model=IncidentRCAAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get specific RCA analysis by ID",
    description="Retrieves a specific historical RCA analysis by its unique analysis_id.",
)
def get_rca_by_id(
    incident_id: int,
    analysis_id: str,
    service: RCAService = Depends(get_rca_service),
) -> IncidentRCAAnalysisResponse:
    """Retrieve a specific historical RCA analysis."""
    return service.get_rca_by_id(incident_id=incident_id, analysis_id=analysis_id)


# =====================================================================
# Phase 6: Evidence-Grounded Investigation & Fix Recommendations Endpoints
# =====================================================================

@router.post(
    "/{incident_id}/recommendations",
    response_model=IncidentRecommendationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate evidence-grounded recommendations",
    description="Generates operational investigation and fix recommendations strictly derived from the latest validated RCA.",
)
def generate_recommendations(
    incident_id: int,
    service: RecommendationService = Depends(get_recommendation_service),
) -> IncidentRecommendationListResponse:
    """Generate recommendations from latest validated RCA."""
    return service.generate_recommendations(incident_id=incident_id)


@router.get(
    "/{incident_id}/recommendations",
    response_model=IncidentRecommendationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest recommendations",
    description="Retrieves the latest generated batch of recommendations for the incident.",
)
def get_latest_recommendations(
    incident_id: int,
    service: RecommendationService = Depends(get_recommendation_service),
) -> IncidentRecommendationListResponse:
    """Retrieve latest recommendations for an incident."""
    return service.get_latest_recommendations(incident_id=incident_id)


@router.get(
    "/{incident_id}/recommendations/history",
    response_model=IncidentRecommendationHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recommendation history",
    description="Returns all historical recommendations generated for this incident.",
)
def get_recommendation_history(
    incident_id: int,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: RecommendationService = Depends(get_recommendation_service),
) -> IncidentRecommendationHistoryResponse:
    """Retrieve historical recommendations for an incident."""
    return service.get_recommendation_history(incident_id=incident_id, limit=limit, offset=offset)


# --- Recommendation Reviews ---

@router.get(
    "/{incident_id}/recommendations/reviews",
    response_model=RecommendationReviewListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recommendation reviews",
    description="Retrieves all developer decisions on recommendations for this incident.",
)
def get_recommendation_reviews(
    incident_id: int,
    service: InvestigationService = Depends(get_investigation_service),
) -> RecommendationReviewListResponse:
    """Retrieve recommendation reviews."""
    return service.get_recommendation_reviews(incident_id=incident_id)


@router.post(
    "/{incident_id}/recommendations/{recommendation_id}/review",
    response_model=RecommendationReviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Review Phase 6 recommendation",
    description="Records developer decision (ACCEPTED, REJECTED, DEFERRED, NOT_APPLICABLE) without mutating the recommendation.",
)
def review_recommendation(
    incident_id: int,
    recommendation_id: str,
    req: CreateRecommendationReviewRequest,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
    db: Session = Depends(get_db),
) -> RecommendationReviewResponse:
    """Review Phase 6 recommendation."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    req.reviewed_by = get_acting_identity(current_user, req.reviewed_by)
    res = service.review_recommendation(incident_id=incident_id, recommendation_id=recommendation_id, req=req)
    log_audit_event(
        db=db,
        actor=current_user.username,
        action="RECOMMENDATION_REVIEW",
        target_entity="RECOMMENDATION",
        target_id=recommendation_id,
        request_id=request_id,
        metadata={"incident_id": incident_id, "decision": req.decision},
    )
    return res


@router.get(
    "/{incident_id}/recommendations/{recommendation_id}",
    response_model=IncidentRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get specific recommendation by ID",
    description="Retrieves a specific recommendation by its unique recommendation_id.",
)
def get_recommendation_by_id(
    incident_id: int,
    recommendation_id: str,
    service: RecommendationService = Depends(get_recommendation_service),
) -> IncidentRecommendationResponse:
    """Retrieve a specific recommendation by ID."""
    return service.get_recommendation_by_id(incident_id=incident_id, recommendation_id=recommendation_id)


# =====================================================================
# Phase 7: Developer Investigation & Resolution Endpoints
# =====================================================================

# --- Investigation Workspace ---

@router.post(
    "/{incident_id}/investigation",
    response_model=InvestigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Start or update developer investigation",
    description="Initializes or retrieves the active developer investigation workspace for an incident.",
)
def start_investigation(
    incident_id: int,
    req: StartInvestigationRequest,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    """Start or update developer investigation."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    if current_user.id != 0 or not req.assigned_to:
        req.assigned_to = current_user.username
    res = service.start_investigation(incident_id=incident_id, req=req)
    log_audit_event(
        db=db,
        actor=current_user.username,
        action="INCIDENT_ASSIGN",
        target_entity="INCIDENT",
        target_id=str(incident_id),
        request_id=request_id,
        metadata={"assigned_to": req.assigned_to},
    )
    return res


@router.get(
    "/{incident_id}/investigation",
    response_model=InvestigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active developer investigation",
    description="Retrieves the active developer investigation workspace for an incident.",
)
def get_investigation(
    incident_id: int,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationResponse:
    """Get active developer investigation."""
    return service.get_investigation(incident_id=incident_id)


@router.patch(
    "/{incident_id}/investigation",
    response_model=InvestigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Update developer investigation status or assignment",
    description="Updates developer assignment or workflow state for the active investigation.",
)
def update_investigation(
    incident_id: int,
    req: UpdateInvestigationRequest,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    """Update developer investigation status or assignment."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    if req.assigned_to and current_user.id != 0:
        req.assigned_to = current_user.username
    res = service.update_investigation(incident_id=incident_id, req=req)
    if req.assigned_to:
        log_audit_event(
            db=db,
            actor=current_user.username,
            action="INCIDENT_ASSIGN",
            target_entity="INCIDENT",
            target_id=str(incident_id),
            request_id=request_id,
            metadata={"assigned_to": req.assigned_to},
        )
    return res


# --- Investigation Notes ---

@router.post(
    "/{incident_id}/investigation/notes",
    response_model=InvestigationNoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Add investigation note",
    description="Adds a developer investigation note with optional evidence citations.",
)
def add_investigation_note(
    incident_id: int,
    req: CreateInvestigationNoteRequest,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationNoteResponse:
    """Add a developer investigation note."""
    req.author = get_acting_identity(current_user, req.author)
    return service.add_note(incident_id=incident_id, req=req)


@router.get(
    "/{incident_id}/investigation/notes",
    response_model=InvestigationNoteListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get investigation notes",
    description="Retrieves all developer notes recorded for the incident.",
)
def get_investigation_notes(
    incident_id: int,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationNoteListResponse:
    """Retrieve all investigation notes."""
    return service.get_notes(incident_id=incident_id)


# --- Investigation Actions ---

@router.post(
    "/{incident_id}/investigation/actions",
    response_model=InvestigationActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Record developer action",
    description="Records an external developer diagnostic or investigation action. Does NOT execute code or shell commands.",
)
def add_investigation_action(
    incident_id: int,
    req: CreateInvestigationActionRequest,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationActionResponse:
    """Record an investigation action."""
    req.performed_by = get_acting_identity(current_user, req.performed_by)
    return service.add_action(incident_id=incident_id, req=req)


@router.get(
    "/{incident_id}/investigation/actions",
    response_model=InvestigationActionListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get investigation actions",
    description="Retrieves all developer actions recorded for the incident.",
)
def get_investigation_actions(
    incident_id: int,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationActionListResponse:
    """Retrieve all investigation actions."""
    return service.get_actions(incident_id=incident_id)


# --- Verification Checklist ---

@router.post(
    "/{incident_id}/verification",
    response_model=VerificationStepResponse,
    status_code=status.HTTP_200_OK,
    summary="Create verification step",
    description="Creates a verification checklist item required before incident resolution.",
)
def create_verification_step(
    incident_id: int,
    req: CreateVerificationStepRequest,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
) -> VerificationStepResponse:
    """Create verification checklist step."""
    return service.create_verification_step(incident_id=incident_id, req=req)


@router.get(
    "/{incident_id}/verification",
    response_model=VerificationStepListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get verification checklist",
    description="Retrieves all verification steps and verification status counts.",
)
def get_verification_steps(
    incident_id: int,
    service: InvestigationService = Depends(get_investigation_service),
) -> VerificationStepListResponse:
    """Retrieve all verification checklist steps."""
    return service.get_verification_steps(incident_id=incident_id)


@router.patch(
    "/{incident_id}/verification/{verification_id}",
    response_model=VerificationStepResponse,
    status_code=status.HTTP_200_OK,
    summary="Update verification step status",
    description="Updates verification status (PASSED, FAILED, PENDING, NOT_APPLICABLE) with results.",
)
def update_verification_step(
    incident_id: int,
    verification_id: int,
    req: UpdateVerificationStepRequest,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
    db: Session = Depends(get_db),
) -> VerificationStepResponse:
    """Update verification step status."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    if req.verified_by:
        req.verified_by = get_acting_identity(current_user, req.verified_by)
    res = service.update_verification_step(
        incident_id=incident_id,
        verification_id=verification_id,
        req=req,
    )
    log_audit_event(
        db=db,
        actor=current_user.username,
        action="VERIFICATION_UPDATE",
        target_entity="VERIFICATION_STEP",
        target_id=str(verification_id),
        request_id=request_id,
        metadata={"incident_id": incident_id, "status": req.status},
    )
    return res


# --- Incident Resolution & Reopening ---

@router.post(
    "/{incident_id}/resolve",
    response_model=ResolveIncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve incident",
    description="Validates that all required verification steps are passed and marks incident and investigation as RESOLVED.",
)
def resolve_incident(
    incident_id: int,
    req: ResolveIncidentRequest,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
    db: Session = Depends(get_db),
) -> ResolveIncidentResponse:
    """Resolve incident with verified checklist."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    req.resolved_by = get_acting_identity(current_user, req.resolved_by)
    res = service.resolve_incident(incident_id=incident_id, req=req)
    log_audit_event(
        db=db,
        actor=current_user.username,
        action="INCIDENT_RESOLVE",
        target_entity="INCIDENT",
        target_id=str(incident_id),
        request_id=request_id,
        metadata={"resolved_by": req.resolved_by, "root_cause_confirmed": str(req.root_cause_confirmed)},
    )
    # Evaluate alerts on resolution
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        evaluate_incident_alerts(db, incident, alert_type="INCIDENT_RESOLVED")
    return res


@router.post(
    "/{incident_id}/reopen",
    response_model=ReopenIncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Reopen incident",
    description="Reopens a resolved incident for continued investigation and clears resolution timestamps.",
)
def reopen_incident(
    incident_id: int,
    req: ReopenIncidentRequest,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value, Role.DEVELOPER.value])),
    service: InvestigationService = Depends(get_investigation_service),
    db: Session = Depends(get_db),
) -> ReopenIncidentResponse:
    """Reopen a resolved incident."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    req.reopened_by = get_acting_identity(current_user, req.reopened_by)
    res = service.reopen_incident(incident_id=incident_id, req=req)
    log_audit_event(
        db=db,
        actor=current_user.username,
        action="INCIDENT_REOPEN",
        target_entity="INCIDENT",
        target_id=str(incident_id),
        request_id=request_id,
        metadata={"reopened_by": req.reopened_by, "reason": req.reason},
    )
    return res


# --- Investigation Timeline ---

@router.get(
    "/{incident_id}/timeline",
    response_model=TimelineEventListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get incident audit timeline",
    description="Retrieves chronological audit timeline events of all developer actions, transitions, and reviews.",
)
def get_timeline(
    incident_id: int,
    service: InvestigationService = Depends(get_investigation_service),
) -> TimelineEventListResponse:
    """Get audit timeline events."""
    return service.get_timeline(incident_id=incident_id)


