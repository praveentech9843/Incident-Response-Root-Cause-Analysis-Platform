from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.core.database import Base


class IncidentEvent(Base):
    """
    SQLAlchemy model representing the many-to-many relationship linking an Incident
    to its constituent ParsedLog events, preserving event ordering within the incident.
    """

    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    incident_id = Column(
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parsed_log_id = Column(
        Integer,
        ForeignKey("parsed_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_index = Column(Integer, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    incident = relationship("Incident", back_populates="incident_events")
    parsed_log = relationship(
        "ParsedLog",
        backref=backref("incident_events", cascade="all, delete-orphan", passive_deletes=True),
    )

    __table_args__ = (
        UniqueConstraint("incident_id", "parsed_log_id", name="uq_incident_events_incident_parsed_log"),
        Index("ix_incident_events_incident_id_event_index", "incident_id", "event_index"),
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentEvent(id={self.id}, incident_id={self.incident_id}, "
            f"parsed_log_id={self.parsed_log_id}, event_index={self.event_index})>"
        )
