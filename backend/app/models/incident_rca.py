from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class IncidentRCAAnalysis(Base):
    """
    SQLAlchemy model representing an Evidence-Grounded Root Cause Analysis run
    associated with an Incident.
    Stores the full evidence snapshot, validated hypotheses, limitations,
    and provider/model metadata for auditing.
    """

    __tablename__ = "incident_rca_analyses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_id = Column(String(64), nullable=False, unique=True, index=True)
    analysis_status = Column(String(32), nullable=False, index=True)
    provider = Column(String(64), nullable=False)
    model = Column(String(128), nullable=False)
    summary = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    confidence_level = Column(String(32), nullable=True)
    hypotheses = Column(JSONB, nullable=False, default=list)
    evidence_snapshot = Column(JSONB, nullable=False, default=dict)
    limitations = Column(JSONB, nullable=False, default=list)
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

    incident = relationship("Incident", back_populates="rca_analyses")
    recommendations = relationship(
        "IncidentRecommendation",
        back_populates="rca_analysis",
        cascade="all, delete-orphan",
        order_by="IncidentRecommendation.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_incident_rca_analyses_incident_created", "incident_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentRCAAnalysis(id={self.id}, incident_id={self.incident_id}, "
            f"analysis_id='{self.analysis_id}', status='{self.analysis_status}')>"
        )
