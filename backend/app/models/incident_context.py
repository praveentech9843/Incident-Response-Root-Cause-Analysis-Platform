from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class IncidentContext(Base):
    """
    SQLAlchemy model representing operational context enrichment attached to an Incident.
    Stores structured category data (SERVICE, DEPLOYMENT, INFRASTRUCTURE, METRICS,
    HISTORY, DEPENDENCIES) along with explicit availability statuses.
    Strictly evidence-only; does NOT infer root causes or causal dependencies.
    """

    __tablename__ = "incident_contexts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context_category = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    data = Column(JSONB, nullable=False, default=dict)
    source = Column(String(128), nullable=False)
    collected_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
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

    incident = relationship("Incident", back_populates="contexts")

    __table_args__ = (
        UniqueConstraint("incident_id", "context_category", name="uq_incident_contexts_incident_category"),
        Index("ix_incident_contexts_incident_category", "incident_id", "context_category"),
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentContext(id={self.id}, incident_id={self.incident_id}, "
            f"category='{self.context_category}', status='{self.status}')>"
        )
