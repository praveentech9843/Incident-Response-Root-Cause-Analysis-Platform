from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Incident(Base):
    """
    SQLAlchemy model representing a correlated incident grouping multiple
    parsed log events across services within a temporal or contextual window.
    Strictly correlation-focused; does NOT infer root causes or causality.
    """

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_key = Column(String(64), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    started_at = Column(DateTime(timezone=True), nullable=True, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True, index=True)
    event_count = Column(Integer, nullable=False, default=0)
    service_count = Column(Integer, nullable=False, default=0)
    correlation_reason = Column(Text, nullable=False)
    correlation_confidence = Column(Float, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True, index=True)
    resolution_summary = Column(Text, nullable=True)
    resolved_by = Column(String(128), nullable=True)
    root_cause_confirmed = Column(String(32), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationship to incident_events with cascade delete
    incident_events = relationship(
        "IncidentEvent",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentEvent.event_index",
    )

    # Relationship to incident_contexts with cascade delete
    contexts = relationship(
        "IncidentContext",
        back_populates="incident",
        cascade="all, delete-orphan",
    )

    # Relationship to incident_rca_analyses with cascade delete
    rca_analyses = relationship(
        "IncidentRCAAnalysis",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentRCAAnalysis.created_at.desc()",
    )

    # Relationship to incident_recommendations with cascade delete
    recommendations = relationship(
        "IncidentRecommendation",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentRecommendation.created_at.desc()",
    )

    # Phase 7 relationships with cascade delete
    investigations = relationship(
        "IncidentInvestigation",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentInvestigation.created_at.desc()",
    )
    investigation_notes = relationship(
        "IncidentInvestigationNote",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentInvestigationNote.created_at.asc()",
    )
    investigation_actions = relationship(
        "IncidentInvestigationAction",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentInvestigationAction.created_at.asc()",
    )
    recommendation_reviews = relationship(
        "IncidentRecommendationReview",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentRecommendationReview.created_at.asc()",
    )
    verification_steps = relationship(
        "IncidentVerificationStep",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentVerificationStep.created_at.asc()",
    )
    timeline_events = relationship(
        "IncidentTimelineEvent",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentTimelineEvent.timestamp.asc()",
    )

    def __repr__(self) -> str:
        return (
            f"<Incident(id={self.id}, key='{self.incident_key}', "
            f"title='{self.title}', status='{self.status}')>"
        )

