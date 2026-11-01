from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.incident_investigation import (
    IncidentInvestigation,
    IncidentInvestigationNote,
    IncidentInvestigationAction,
    IncidentRecommendationReview,
    IncidentVerificationStep,
    IncidentTimelineEvent,
)


class IncidentInvestigationRepository:
    """
    Data repository for Phase 7 developer investigation workflows, notes, actions,
    recommendation reviews, verification steps, and audit timeline events.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # =========================================================================
    # Investigation
    # =========================================================================

    def get_active_investigation(self, incident_id: int) -> Optional[IncidentInvestigation]:
        """Returns the most recent investigation for the incident."""
        return (
            self.db.query(IncidentInvestigation)
            .filter(IncidentInvestigation.incident_id == incident_id)
            .order_by(desc(IncidentInvestigation.created_at))
            .first()
        )

    def get_investigation_by_id(self, investigation_id: int) -> Optional[IncidentInvestigation]:
        return self.db.query(IncidentInvestigation).filter(IncidentInvestigation.id == investigation_id).first()

    def create_investigation(
        self,
        incident_id: int,
        assigned_to: Optional[str] = None,
        assigned_to_name: Optional[str] = None,
        investigation_summary: Optional[str] = None,
        status: str = "INVESTIGATING",
    ) -> IncidentInvestigation:
        now = datetime.now(timezone.utc)
        inv = IncidentInvestigation(
            incident_id=incident_id,
            assigned_to=assigned_to,
            assigned_to_name=assigned_to_name,
            assigned_at=now if assigned_to else None,
            status=status,
            investigation_summary=investigation_summary,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(inv)
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def update_investigation(
        self,
        investigation: IncidentInvestigation,
        assigned_to: Optional[str] = None,
        assigned_to_name: Optional[str] = None,
        status: Optional[str] = None,
        investigation_summary: Optional[str] = None,
    ) -> IncidentInvestigation:
        now = datetime.now(timezone.utc)
        if assigned_to is not None:
            investigation.assigned_to = assigned_to
            investigation.assigned_at = now
        if assigned_to_name is not None:
            investigation.assigned_to_name = assigned_to_name
        if status is not None:
            investigation.status = status
            if status == "RESOLVED":
                investigation.completed_at = now
            elif status in ("INVESTIGATING", "ASSIGNED"):
                investigation.completed_at = None
        if investigation_summary is not None:
            investigation.investigation_summary = investigation_summary

        investigation.updated_at = now
        self.db.commit()
        self.db.refresh(investigation)
        return investigation

    # =========================================================================
    # Investigation Notes
    # =========================================================================

    def create_note(
        self,
        incident_id: int,
        investigation_id: int,
        author: str,
        note: str,
        evidence_references: Optional[List[str]] = None,
    ) -> IncidentInvestigationNote:
        now = datetime.now(timezone.utc)
        note_record = IncidentInvestigationNote(
            incident_id=incident_id,
            investigation_id=investigation_id,
            author=author,
            note=note,
            evidence_references=evidence_references or [],
            created_at=now,
        )
        self.db.add(note_record)
        self.db.commit()
        self.db.refresh(note_record)
        return note_record

    def get_notes_for_incident(self, incident_id: int) -> List[IncidentInvestigationNote]:
        return (
            self.db.query(IncidentInvestigationNote)
            .filter(IncidentInvestigationNote.incident_id == incident_id)
            .order_by(IncidentInvestigationNote.created_at.asc())
            .all()
        )

    # =========================================================================
    # Investigation Actions
    # =========================================================================

    def create_action(
        self,
        incident_id: int,
        investigation_id: int,
        action_type: str,
        description: str,
        performed_by: str,
        result: str,
        evidence_references: Optional[List[str]] = None,
    ) -> IncidentInvestigationAction:
        now = datetime.now(timezone.utc)
        action_record = IncidentInvestigationAction(
            incident_id=incident_id,
            investigation_id=investigation_id,
            action_type=action_type,
            description=description,
            performed_by=performed_by,
            result=result,
            evidence_references=evidence_references or [],
            created_at=now,
        )
        self.db.add(action_record)
        self.db.commit()
        self.db.refresh(action_record)
        return action_record

    def get_actions_for_incident(self, incident_id: int) -> List[IncidentInvestigationAction]:
        return (
            self.db.query(IncidentInvestigationAction)
            .filter(IncidentInvestigationAction.incident_id == incident_id)
            .order_by(IncidentInvestigationAction.created_at.asc())
            .all()
        )

    # =========================================================================
    # Recommendation Reviews
    # =========================================================================

    def create_recommendation_review(
        self,
        incident_id: int,
        investigation_id: Optional[int],
        recommendation_id: str,
        reviewed_by: str,
        decision: str,
        reason: Optional[str] = None,
    ) -> IncidentRecommendationReview:
        now = datetime.now(timezone.utc)
        review = IncidentRecommendationReview(
            incident_id=incident_id,
            investigation_id=investigation_id,
            recommendation_id=recommendation_id,
            reviewed_by=reviewed_by,
            decision=decision,
            reason=reason,
            created_at=now,
        )
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def get_reviews_for_incident(self, incident_id: int) -> List[IncidentRecommendationReview]:
        return (
            self.db.query(IncidentRecommendationReview)
            .filter(IncidentRecommendationReview.incident_id == incident_id)
            .order_by(IncidentRecommendationReview.created_at.asc())
            .all()
        )

    # =========================================================================
    # Verification Steps
    # =========================================================================

    def create_verification_step(
        self,
        incident_id: int,
        investigation_id: int,
        title: str,
        description: Optional[str] = None,
        is_required: bool = True,
        evidence_references: Optional[List[str]] = None,
    ) -> IncidentVerificationStep:
        now = datetime.now(timezone.utc)
        step = IncidentVerificationStep(
            incident_id=incident_id,
            investigation_id=investigation_id,
            title=title,
            description=description,
            is_required=is_required,
            status="PENDING",
            evidence_references=evidence_references or [],
            created_at=now,
            updated_at=now,
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def get_verification_step(self, step_id: int) -> Optional[IncidentVerificationStep]:
        return self.db.query(IncidentVerificationStep).filter(IncidentVerificationStep.id == step_id).first()

    def get_verification_steps_for_incident(self, incident_id: int) -> List[IncidentVerificationStep]:
        return (
            self.db.query(IncidentVerificationStep)
            .filter(IncidentVerificationStep.incident_id == incident_id)
            .order_by(IncidentVerificationStep.created_at.asc())
            .all()
        )

    def update_verification_step(
        self,
        step: IncidentVerificationStep,
        status: str,
        result: Optional[str] = None,
        verified_by: Optional[str] = None,
        evidence_references: Optional[List[str]] = None,
    ) -> IncidentVerificationStep:
        now = datetime.now(timezone.utc)
        step.status = status
        if result is not None:
            step.result = result
        if verified_by is not None:
            step.verified_by = verified_by
        if status in ("PASSED", "FAILED"):
            step.verified_at = now
        elif status == "PENDING":
            step.verified_at = None
        if evidence_references is not None:
            step.evidence_references = evidence_references

        step.updated_at = now
        self.db.commit()
        self.db.refresh(step)
        return step

    def reset_verification_steps_for_incident(
        self,
        incident_id: int,
        commit: bool = True,
    ) -> List[IncidentVerificationStep]:
        """
        Resets all verification steps for an incident to PENDING and clears previous verification results.
        Preserves step definitions, titles, descriptions, is_required flags, and evidence_references.
        """
        now = datetime.now(timezone.utc)
        steps = self.get_verification_steps_for_incident(incident_id)
        for step in steps:
            step.status = "PENDING"
            step.result = None
            step.verified_by = None
            step.verified_at = None
            step.updated_at = now
        if commit:
            self.db.commit()
            for step in steps:
                self.db.refresh(step)
        return steps

    # =========================================================================
    # Timeline Events
    # =========================================================================

    def create_timeline_event(
        self,
        incident_id: int,
        investigation_id: Optional[int],
        event_type: str,
        actor: str,
        description: str,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> IncidentTimelineEvent:
        now = timestamp or datetime.now(timezone.utc)
        event = IncidentTimelineEvent(
            incident_id=incident_id,
            investigation_id=investigation_id,
            event_type=event_type,
            actor=actor,
            description=description,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            timestamp=now,
            created_at=now,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_timeline_events_for_incident(self, incident_id: int) -> List[IncidentTimelineEvent]:
        return (
            self.db.query(IncidentTimelineEvent)
            .filter(IncidentTimelineEvent.incident_id == incident_id)
            .order_by(IncidentTimelineEvent.timestamp.asc())
            .all()
        )
