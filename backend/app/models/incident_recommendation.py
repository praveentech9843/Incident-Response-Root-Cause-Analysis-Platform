from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class IncidentRecommendation(Base):
    """
    SQLAlchemy model representing an Evidence-Grounded Investigation or Fix Recommendation
    derived strictly from a validated Phase 5 RCA analysis.
    Preserves auditability, rationale, supporting evidence IDs, risk level, and verification steps.
    Never executes actions automatically.
    """

    __tablename__ = "incident_recommendations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recommendation_id = Column(String(64), nullable=False, unique=True, index=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rca_analysis_id = Column(
        Integer,
        ForeignKey("incident_rca_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(String(32), nullable=False, index=True)  # INVESTIGATION, DIAGNOSTIC_VERIFICATION, FIX, PREVENTION, VERIFICATION
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    supporting_evidence = Column(JSONB, nullable=False, default=list)
    confidence = Column(Float, nullable=False)
    confidence_level = Column(String(16), nullable=False)  # LOW, MEDIUM, HIGH
    risk_level = Column(String(16), nullable=False, default="LOW")  # LOW, MEDIUM, HIGH, UNKNOWN
    expected_impact = Column(Text, nullable=False)
    prerequisites = Column(JSONB, nullable=False, default=list)
    verification_steps = Column(JSONB, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="PROPOSED", index=True)  # PROPOSED, REVIEW_REQUIRED, DISMISSED
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

    incident = relationship("Incident", back_populates="recommendations")
    rca_analysis = relationship("IncidentRCAAnalysis", back_populates="recommendations")

    __table_args__ = (
        Index("ix_incident_recommendations_incident_created", "incident_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentRecommendation(id={self.id}, incident_id={self.incident_id}, "
            f"rec_id='{self.recommendation_id}', type='{self.type}', status='{self.status}')>"
        )
