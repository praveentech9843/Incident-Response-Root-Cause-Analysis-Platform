from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class IncidentInvestigation(Base):
    """
    SQLAlchemy model representing a persistent Developer Investigation workflow
    associated with an incident. Tracks ownership, assignment, investigation status,
    and audit timestamps.
    """

    __tablename__ = "incident_investigations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_to = Column(String(128), nullable=True, index=True)
    assigned_to_name = Column(String(128), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        String(32),
        nullable=False,
        default="UNASSIGNED",
        index=True,
    )  # UNASSIGNED, ASSIGNED, INVESTIGATING, READY_FOR_VERIFICATION, RESOLVED, CLOSED
    investigation_summary = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    incident = relationship("Incident", back_populates="investigations")
    notes = relationship(
        "IncidentInvestigationNote",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="IncidentInvestigationNote.created_at.asc()",
    )
    actions = relationship(
        "IncidentInvestigationAction",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="IncidentInvestigationAction.created_at.asc()",
    )
    recommendation_reviews = relationship(
        "IncidentRecommendationReview",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="IncidentRecommendationReview.created_at.asc()",
    )
    verification_steps = relationship(
        "IncidentVerificationStep",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="IncidentVerificationStep.created_at.asc()",
    )
    timeline_events = relationship(
        "IncidentTimelineEvent",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="IncidentTimelineEvent.timestamp.asc()",
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentInvestigation(id={self.id}, incident_id={self.incident_id}, "
            f"assigned_to='{self.assigned_to}', status='{self.status}')>"
        )


class IncidentInvestigationNote(Base):
    """
    Persistent developer investigation note.
    Records manual observations and developer remarks without automated mutation.
    """

    __tablename__ = "incident_investigation_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id = Column(
        Integer,
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author = Column(String(128), nullable=False)
    note = Column(Text, nullable=False)
    evidence_references = Column(JSONB, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    incident = relationship("Incident", back_populates="investigation_notes")
    investigation = relationship("IncidentInvestigation", back_populates="notes")

    def __repr__(self) -> str:
        return f"<IncidentInvestigationNote(id={self.id}, author='{self.author}')>"


class IncidentInvestigationAction(Base):
    """
    Persistent log of developer investigation actions.
    Records actions performed externally by human engineers (e.g. LOG_REVIEW, DIAGNOSTIC_CHECK, FIX_APPLIED).
    The platform records the action; it NEVER executes arbitrary shell or diagnostic commands.
    """

    __tablename__ = "incident_investigation_actions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id = Column(
        Integer,
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type = Column(
        String(32),
        nullable=False,
        index=True,
    )  # OBSERVATION, DIAGNOSTIC_CHECK, CONFIG_REVIEW, LOG_REVIEW, METRIC_REVIEW, DEPENDENCY_CHECK, FIX_APPLIED, VERIFICATION, OTHER
    description = Column(Text, nullable=False)
    performed_by = Column(String(128), nullable=False)
    result = Column(Text, nullable=False)
    evidence_references = Column(JSONB, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    incident = relationship("Incident", back_populates="investigation_actions")
    investigation = relationship("IncidentInvestigation", back_populates="actions")

    def __repr__(self) -> str:
        return (
            f"<IncidentInvestigationAction(id={self.id}, type='{self.action_type}', "
            f"performed_by='{self.performed_by}')>"
        )


class IncidentRecommendationReview(Base):
    """
    Persistent record of a developer decision on a Phase 6 recommendation.
    Tracks ACCEPTED, REJECTED, DEFERRED, or NOT_APPLICABLE decisions without mutating
    the original recommendation or evidence.
    """

    __tablename__ = "incident_recommendation_reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id = Column(
        Integer,
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    recommendation_id = Column(String(64), nullable=False, index=True)
    reviewed_by = Column(String(128), nullable=False)
    decision = Column(
        String(32),
        nullable=False,
        index=True,
    )  # ACCEPTED, REJECTED, DEFERRED, NOT_APPLICABLE
    reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    incident = relationship("Incident", back_populates="recommendation_reviews")
    investigation = relationship("IncidentInvestigation", back_populates="recommendation_reviews")

    def __repr__(self) -> str:
        return (
            f"<IncidentRecommendationReview(id={self.id}, rec='{self.recommendation_id}', "
            f"decision='{self.decision}')>"
        )


class IncidentVerificationStep(Base):
    """
    Persistent verification checklist step defined and verified by developers.
    Incident resolution requires all required verification steps to be PASSED.
    """

    __tablename__ = "incident_verification_steps"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id = Column(
        Integer,
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    status = Column(
        String(32),
        nullable=False,
        default="PENDING",
        index=True,
    )  # PENDING, PASSED, FAILED, NOT_APPLICABLE
    result = Column(Text, nullable=True)
    verified_by = Column(String(128), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    evidence_references = Column(JSONB, nullable=False, default=list)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    incident = relationship("Incident", back_populates="verification_steps")
    investigation = relationship("IncidentInvestigation", back_populates="verification_steps")

    def __repr__(self) -> str:
        return (
            f"<IncidentVerificationStep(id={self.id}, title='{self.title}', "
            f"status='{self.status}')>"
        )


class IncidentTimelineEvent(Base):
    """
    Persistent audit timeline event tracking lifecycle transitions and developer activity.
    Only derived from real actions and persisted state changes; never fabricated.
    """

    __tablename__ = "incident_timeline_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id = Column(
        Integer,
        ForeignKey("incident_investigations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_type = Column(
        String(64),
        nullable=False,
        index=True,
    )  # INVESTIGATION_STARTED, INCIDENT_ASSIGNED, NOTE_ADDED, ACTION_RECORDED,
    # RECOMMENDATION_REVIEWED, VERIFICATION_CREATED, VERIFICATION_UPDATED,
    # INCIDENT_RESOLVED, INCIDENT_REOPENED, STATUS_CHANGED
    actor = Column(String(128), nullable=False)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    related_entity_type = Column(String(64), nullable=True)
    related_entity_id = Column(String(64), nullable=True)
    description = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    incident = relationship("Incident", back_populates="timeline_events")
    investigation = relationship("IncidentInvestigation", back_populates="timeline_events")

    def __repr__(self) -> str:
        return (
            f"<IncidentTimelineEvent(id={self.id}, type='{self.event_type}', "
            f"actor='{self.actor}')>"
        )
