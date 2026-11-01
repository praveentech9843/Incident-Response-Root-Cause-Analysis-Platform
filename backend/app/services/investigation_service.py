from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.incident_recommendation import IncidentRecommendation
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
    TimelineEventResponse,
    TimelineEventListResponse,
    TimelineEventType,
    InvestigationStatus,
    VerificationStatus,
)
from app.investigation.evidence_validator import (
    EvidenceReferenceValidator,
    InvalidEvidenceReferenceError,
)
from app.repositories.incident_repository import IncidentRepository
from app.repositories.incident_investigation_repository import IncidentInvestigationRepository


class InvestigationService:
    """
    Business service orchestrating Phase 7 developer investigation workflows,
    action recording, recommendation reviews, verification checklists, resolution rules,
    and audit timelines.
    Strictly adheres to: RECOMMENDATION != EXECUTION.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.incident_repo = IncidentRepository(db)
        self.investigation_repo = IncidentInvestigationRepository(db)

    def _get_incident_or_404(self, incident_id: int) -> Incident:
        incident = self.incident_repo.get_by_id(incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with id {incident_id} not found",
            )
        return incident

    def _get_active_investigation_or_404(self, incident_id: int):
        inv = self.investigation_repo.get_active_investigation(incident_id)
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No investigation found for incident {incident_id}. Please start an investigation first.",
            )
        return inv

    def _get_or_create_investigation(self, incident: Incident, actor: str = "developer"):
        inv = self.investigation_repo.get_active_investigation(incident.id)
        if not inv:
            inv = self.investigation_repo.create_investigation(
                incident_id=incident.id,
                assigned_to=actor,
                status="INVESTIGATING",
                investigation_summary="Auto-initialized on developer action",
            )
            if incident.status == "OPEN":
                incident.status = "INVESTIGATING"
                self.db.commit()
            self.investigation_repo.create_timeline_event(
                incident_id=incident.id,
                investigation_id=inv.id,
                event_type=TimelineEventType.INVESTIGATION_STARTED.value,
                actor=actor,
                description=f"Investigation started by {actor}",
            )
        return inv

    # =========================================================================
    # Investigation
    # =========================================================================

    def start_investigation(
        self,
        incident_id: int,
        req: StartInvestigationRequest,
    ) -> InvestigationResponse:
        incident = self._get_incident_or_404(incident_id)
        existing = self.investigation_repo.get_active_investigation(incident_id)

        actor = req.assigned_to or "developer"
        if existing and existing.status in ("INVESTIGATING", "ASSIGNED", "READY_FOR_VERIFICATION"):
            # Update assignment if provided
            if req.assigned_to or req.investigation_summary:
                existing = self.investigation_repo.update_investigation(
                    existing,
                    assigned_to=req.assigned_to,
                    assigned_to_name=req.assigned_to_name,
                    investigation_summary=req.investigation_summary,
                )
            return InvestigationResponse.model_validate(existing)

        inv_status = "ASSIGNED" if req.assigned_to else "INVESTIGATING"
        inv = self.investigation_repo.create_investigation(
            incident_id=incident_id,
            assigned_to=req.assigned_to,
            assigned_to_name=req.assigned_to_name,
            investigation_summary=req.investigation_summary,
            status=inv_status,
        )

        # Transition incident from OPEN -> INVESTIGATING if currently OPEN
        if incident.status == "OPEN":
            incident.status = "INVESTIGATING"
            self.db.commit()

        # Timeline event for start
        self.investigation_repo.create_timeline_event(
            incident_id=incident_id,
            investigation_id=inv.id,
            event_type=TimelineEventType.INVESTIGATION_STARTED.value,
            actor=actor,
            description=f"Investigation started for incident {incident.incident_key}",
        )

        # Timeline event for assignment if assigned
        if req.assigned_to:
            self.investigation_repo.create_timeline_event(
                incident_id=incident_id,
                investigation_id=inv.id,
                event_type=TimelineEventType.INCIDENT_ASSIGNED.value,
                actor=actor,
                description=f"Incident assigned to {req.assigned_to_name or req.assigned_to}",
            )

        return InvestigationResponse.model_validate(inv)

    def get_investigation(self, incident_id: int) -> InvestigationResponse:
        self._get_incident_or_404(incident_id)
        inv = self._get_active_investigation_or_404(incident_id)
        return InvestigationResponse.model_validate(inv)

    def update_investigation(
        self,
        incident_id: int,
        req: UpdateInvestigationRequest,
    ) -> InvestigationResponse:
        incident = self._get_incident_or_404(incident_id)
        inv = self._get_active_investigation_or_404(incident_id)

        actor = req.assigned_to or inv.assigned_to or "developer"

        # Disallow setting to RESOLVED via PATCH (must use POST /resolve with checklist)
        if req.status == InvestigationStatus.RESOLVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot resolve investigation via PATCH. Please use the /resolve endpoint with verification checklist.",
            )

        old_assigned = inv.assigned_to
        old_status = inv.status

        status_val = req.status.value if req.status else None
        updated_inv = self.investigation_repo.update_investigation(
            inv,
            assigned_to=req.assigned_to,
            assigned_to_name=req.assigned_to_name,
            status=status_val,
            investigation_summary=req.investigation_summary,
        )

        if req.assigned_to and req.assigned_to != old_assigned:
            self.investigation_repo.create_timeline_event(
                incident_id=incident_id,
                investigation_id=inv.id,
                event_type=TimelineEventType.INCIDENT_ASSIGNED.value,
                actor=actor,
                description=f"Incident reassigned to {req.assigned_to_name or req.assigned_to}",
            )

        if req.status and req.status.value != old_status:
            self.investigation_repo.create_timeline_event(
                incident_id=incident_id,
                investigation_id=inv.id,
                event_type=TimelineEventType.STATUS_CHANGED.value,
                actor=actor,
                description=f"Investigation status changed from {old_status} to {req.status.value}",
            )

        return InvestigationResponse.model_validate(updated_inv)

    # =========================================================================
    # Notes
    # =========================================================================

    def add_note(
        self,
        incident_id: int,
        req: CreateInvestigationNoteRequest,
    ) -> InvestigationNoteResponse:
        incident = self._get_incident_or_404(incident_id)
        inv = self._get_or_create_investigation(incident, actor=req.author)

        # Validate evidence references if provided
        if req.evidence_references:
            try:
                EvidenceReferenceValidator.validate_references(incident, req.evidence_references)
            except InvalidEvidenceReferenceError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        note = self.investigation_repo.create_note(
            incident_id=incident_id,
            investigation_id=inv.id,
            author=req.author,
            note=req.note,
            evidence_references=req.evidence_references,
        )

        self.investigation_repo.create_timeline_event(
            incident_id=incident_id,
            investigation_id=inv.id,
            event_type=TimelineEventType.NOTE_ADDED.value,
            actor=req.author,
            description=f"Note added by {req.author}: {req.note[:80]}",
            related_entity_type="NOTE",
            related_entity_id=str(note.id),
        )

        return InvestigationNoteResponse.model_validate(note)

    def get_notes(self, incident_id: int) -> InvestigationNoteListResponse:
        self._get_incident_or_404(incident_id)
        notes = self.investigation_repo.get_notes_for_incident(incident_id)
        return InvestigationNoteListResponse(
            incident_id=incident_id,
            total=len(notes),
            notes=[InvestigationNoteResponse.model_validate(n) for n in notes],
        )

    # =========================================================================
    # Actions
    # =========================================================================

    def add_action(
        self,
        incident_id: int,
        req: CreateInvestigationActionRequest,
    ) -> InvestigationActionResponse:
        incident = self._get_incident_or_404(incident_id)
        inv = self._get_or_create_investigation(incident, actor=req.performed_by)

        # Strictly validate evidence references
        if req.evidence_references:
            try:
                EvidenceReferenceValidator.validate_references(incident, req.evidence_references)
            except InvalidEvidenceReferenceError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        action = self.investigation_repo.create_action(
            incident_id=incident_id,
            investigation_id=inv.id,
            action_type=req.action_type.value,
            description=req.description,
            performed_by=req.performed_by,
            result=req.result,
            evidence_references=req.evidence_references,
        )

        self.investigation_repo.create_timeline_event(
            incident_id=incident_id,
            investigation_id=inv.id,
            event_type=TimelineEventType.ACTION_RECORDED.value,
            actor=req.performed_by,
            description=f"Action ({req.action_type.value}) performed by {req.performed_by}: {req.description[:80]}",
            related_entity_type="ACTION",
            related_entity_id=str(action.id),
        )

        return InvestigationActionResponse.model_validate(action)

    def get_actions(self, incident_id: int) -> InvestigationActionListResponse:
        self._get_incident_or_404(incident_id)
        actions = self.investigation_repo.get_actions_for_incident(incident_id)
        return InvestigationActionListResponse(
            incident_id=incident_id,
            total=len(actions),
            actions=[InvestigationActionResponse.model_validate(a) for a in actions],
        )

    # =========================================================================
    # Recommendation Reviews
    # =========================================================================

    def review_recommendation(
        self,
        incident_id: int,
        recommendation_id: str,
        req: CreateRecommendationReviewRequest,
    ) -> RecommendationReviewResponse:
        incident = self._get_incident_or_404(incident_id)
        inv = self.investigation_repo.get_active_investigation(incident_id)
        inv_id = inv.id if inv else None

        # Verify recommendation exists for this incident (accepts either string code or integer id)
        rec_query = self.db.query(IncidentRecommendation).filter(
            IncidentRecommendation.incident_id == incident_id
        )
        if str(recommendation_id).isdigit():
            rec = rec_query.filter(
                (IncidentRecommendation.recommendation_id == str(recommendation_id))
                | (IncidentRecommendation.id == int(recommendation_id))
            ).first()
        else:
            rec = rec_query.filter(
                IncidentRecommendation.recommendation_id == str(recommendation_id)
            ).first()

        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation '{recommendation_id}' not found for incident {incident_id}",
            )

        review = self.investigation_repo.create_recommendation_review(
            incident_id=incident_id,
            investigation_id=inv_id,
            recommendation_id=rec.recommendation_id,
            reviewed_by=req.reviewed_by,
            decision=req.decision.value,
            reason=req.reason,
        )

        desc = f"Recommendation {recommendation_id} marked as {req.decision.value} by {req.reviewed_by}"
        if req.reason:
            desc += f": {req.reason[:60]}"

        self.investigation_repo.create_timeline_event(
            incident_id=incident_id,
            investigation_id=inv_id,
            event_type=TimelineEventType.RECOMMENDATION_REVIEWED.value,
            actor=req.reviewed_by,
            description=desc,
            related_entity_type="RECOMMENDATION_REVIEW",
            related_entity_id=recommendation_id,
        )

        return RecommendationReviewResponse.model_validate(review)

    def get_recommendation_reviews(self, incident_id: int) -> RecommendationReviewListResponse:
        self._get_incident_or_404(incident_id)
        reviews = self.investigation_repo.get_reviews_for_incident(incident_id)
        return RecommendationReviewListResponse(
            incident_id=incident_id,
            total=len(reviews),
            reviews=[RecommendationReviewResponse.model_validate(r) for r in reviews],
        )

    # =========================================================================
    # Verification Steps
    # =========================================================================

    def create_verification_step(
        self,
        incident_id: int,
        req: CreateVerificationStepRequest,
    ) -> VerificationStepResponse:
        incident = self._get_incident_or_404(incident_id)
        inv = self._get_or_create_investigation(incident)

        if req.evidence_references:
            try:
                EvidenceReferenceValidator.validate_references(incident, req.evidence_references)
            except InvalidEvidenceReferenceError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        step = self.investigation_repo.create_verification_step(
            incident_id=incident_id,
            investigation_id=inv.id,
            title=req.title,
            description=req.description,
            is_required=req.is_required,
            evidence_references=req.evidence_references,
        )

        self.investigation_repo.create_timeline_event(
            incident_id=incident_id,
            investigation_id=inv.id,
            event_type=TimelineEventType.VERIFICATION_CREATED.value,
            actor=inv.assigned_to or "developer",
            description=f"Verification step defined: '{req.title}'",
            related_entity_type="VERIFICATION_STEP",
            related_entity_id=str(step.id),
        )

        return VerificationStepResponse.model_validate(step)

    def get_verification_steps(self, incident_id: int) -> VerificationStepListResponse:
        self._get_incident_or_404(incident_id)
        steps = self.investigation_repo.get_verification_steps_for_incident(incident_id)

        pending_count = sum(1 for s in steps if s.status == "PENDING")
        passed_count = sum(1 for s in steps if s.status == "PASSED")
        failed_count = sum(1 for s in steps if s.status == "FAILED")

        return VerificationStepListResponse(
            incident_id=incident_id,
            total=len(steps),
            pending_count=pending_count,
            passed_count=passed_count,
            failed_count=failed_count,
            steps=[VerificationStepResponse.model_validate(s) for s in steps],
        )

    def update_verification_step(
        self,
        incident_id: int,
        verification_id: int,
        req: UpdateVerificationStepRequest,
    ) -> VerificationStepResponse:
        incident = self._get_incident_or_404(incident_id)
        step = self.investigation_repo.get_verification_step(verification_id)
        if not step or step.incident_id != incident_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Verification step {verification_id} not found for incident {incident_id}",
            )

        if req.evidence_references is not None:
            try:
                EvidenceReferenceValidator.validate_references(incident, req.evidence_references)
            except InvalidEvidenceReferenceError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        old_status = step.status
        updated_step = self.investigation_repo.update_verification_step(
            step=step,
            status=req.status.value,
            result=req.result,
            verified_by=req.verified_by,
            evidence_references=req.evidence_references,
        )

        actor = req.verified_by or "developer"
        self.investigation_repo.create_timeline_event(
            incident_id=incident_id,
            investigation_id=step.investigation_id,
            event_type=TimelineEventType.VERIFICATION_UPDATED.value,
            actor=actor,
            description=f"Verification step '{step.title}' updated from {old_status} to {req.status.value}",
            related_entity_type="VERIFICATION_STEP",
            related_entity_id=str(step.id),
        )

        return VerificationStepResponse.model_validate(updated_step)

    # =========================================================================
    # Resolution & Reopen
    # =========================================================================

    def resolve_incident(
        self,
        incident_id: int,
        req: ResolveIncidentRequest,
    ) -> ResolveIncidentResponse:
        # 1. Incident exists
        incident = self._get_incident_or_404(incident_id)

        # 2. Investigation exists
        inv = self.investigation_repo.get_active_investigation(incident_id)
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incident cannot be resolved without an active investigation.",
            )

        # 3. Developer/resolver exists (checked by Pydantic model validator)
        # 4. Resolution summary exists (checked by Pydantic model validator)

        # 5. Required verification steps exist
        steps = self.investigation_repo.get_verification_steps_for_incident(incident_id)
        if not steps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incident cannot be resolved: At least one required verification step must be defined and passed.",
            )

        # 6. All required verification steps must be PASSED
        required_steps = [s for s in steps if s.is_required]
        if not required_steps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incident cannot be resolved: At least one required verification step must be defined.",
            )

        pending_steps = [s for s in required_steps if s.status == "PENDING"]
        if pending_steps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Incident cannot be resolved because {len(pending_steps)} required verification step(s) are still pending.",
            )

        failed_required_steps = [s for s in required_steps if s.status == "FAILED"]
        if failed_required_steps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Incident cannot be resolved because {len(failed_required_steps)} required verification step(s) failed.",
            )

        # 8. No contradictory FAILED verification remains (even among optional steps)
        any_failed_steps = [s for s in steps if s.status == "FAILED"]
        if any_failed_steps:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incident cannot be resolved while contradictory failed verification steps remain.",
            )

        # 7. Evidence references are valid
        if req.evidence_references:
            try:
                EvidenceReferenceValidator.validate_references(incident, req.evidence_references)
            except InvalidEvidenceReferenceError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        now = datetime.now(timezone.utc)

        # Mutate workflow state on incident
        incident.status = "RESOLVED"
        incident.resolved_at = now
        incident.resolved_by = req.resolved_by
        incident.resolution_summary = req.resolution_summary
        incident.root_cause_confirmed = req.root_cause_confirmed.value
        incident.updated_at = now

        # Mutate workflow state on investigation
        inv.status = "RESOLVED"
        inv.completed_at = now
        inv.updated_at = now

        self.db.commit()
        self.db.refresh(incident)
        self.db.refresh(inv)

        # Record timeline event
        self.investigation_repo.create_timeline_event(
            incident_id=incident_id,
            investigation_id=inv.id,
            event_type=TimelineEventType.INCIDENT_RESOLVED.value,
            actor=req.resolved_by,
            description=f"Incident marked as RESOLVED by {req.resolved_by}: {req.resolution_summary[:100]}",
            related_entity_type="INCIDENT",
            related_entity_id=str(incident.id),
        )

        return ResolveIncidentResponse(
            incident_id=incident.id,
            status=incident.status,
            resolved_at=incident.resolved_at,
            resolved_by=incident.resolved_by,
            resolution_summary=incident.resolution_summary,
            root_cause_confirmed=incident.root_cause_confirmed,
            investigation_status=inv.status,
        )

    def reopen_incident(
        self,
        incident_id: int,
        req: ReopenIncidentRequest,
    ) -> ReopenIncidentResponse:
        incident = self._get_incident_or_404(incident_id)

        if incident.status != "RESOLVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reopen incident with status '{incident.status}'. Only RESOLVED incidents can be reopened.",
            )

        inv = self.investigation_repo.get_active_investigation(incident_id)

        now = datetime.now(timezone.utc)
        incident.status = "INVESTIGATING"
        incident.resolved_at = None
        incident.resolved_by = None
        incident.resolution_summary = None
        incident.root_cause_confirmed = None
        incident.updated_at = now

        if inv:
            inv.status = "INVESTIGATING"
            inv.completed_at = None
            inv.updated_at = now

        # Invalidate previous verification results from previous resolution cycle
        self.investigation_repo.reset_verification_steps_for_incident(incident_id, commit=False)

        self.db.commit()
        self.db.refresh(incident)
        if inv:
            self.db.refresh(inv)

        desc = f"Incident reopened by {req.reopened_by}"
        if req.reason:
            desc += f": {req.reason}"

        self.investigation_repo.create_timeline_event(
            incident_id=incident_id,
            investigation_id=inv.id if inv else None,
            event_type=TimelineEventType.INCIDENT_REOPENED.value,
            actor=req.reopened_by,
            description=desc,
            related_entity_type="INCIDENT",
            related_entity_id=str(incident.id),
        )

        return ReopenIncidentResponse(
            incident_id=incident.id,
            status=incident.status,
            reopened_by=req.reopened_by,
            investigation_status=inv.status if inv else "INVESTIGATING",
            message="Incident successfully reopened for continued investigation.",
        )

    # =========================================================================
    # Timeline
    # =========================================================================

    def get_timeline(self, incident_id: int) -> TimelineEventListResponse:
        self._get_incident_or_404(incident_id)
        events = self.investigation_repo.get_timeline_events_for_incident(incident_id)
        return TimelineEventListResponse(
            incident_id=incident_id,
            total=len(events),
            events=[TimelineEventResponse.model_validate(e) for e in events],
        )
