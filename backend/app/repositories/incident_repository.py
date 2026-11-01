from typing import List, Optional, Tuple
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.parsed_log import ParsedLog


class IncidentRepository:
    """Repository handling persistence and querying of incidents and incident_events."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, incident_id: int) -> Optional[Incident]:
        """Fetch an incident by its primary key ID."""
        return self.db.query(Incident).filter(Incident.id == incident_id).first()

    def get_by_key(self, incident_key: str) -> Optional[Incident]:
        """Fetch an incident by its unique deterministic incident_key."""
        return self.db.query(Incident).filter(Incident.incident_key == incident_key).first()

    def get_events_for_incident(self, incident_id: int) -> List[ParsedLog]:
        """
        Retrieve all parsed log events associated with an incident,
        ordered chronologically: timestamp asc (nulls last), event_index asc, id asc.
        """
        return (
            self.db.query(ParsedLog)
            .join(IncidentEvent, IncidentEvent.parsed_log_id == ParsedLog.id)
            .filter(IncidentEvent.incident_id == incident_id)
            .order_by(
                ParsedLog.timestamp.is_(None),
                asc(ParsedLog.timestamp),
                asc(IncidentEvent.event_index),
                asc(ParsedLog.id),
            )
            .all()
        )

    def create_incident_with_events(
        self,
        incident: Incident,
        parsed_events: List[ParsedLog],
    ) -> Incident:
        """
        Persist a new incident and its constituent incident_events within a single transaction.
        """
        self.db.add(incident)
        self.db.flush()  # Populates incident.id

        for idx, event in enumerate(parsed_events):
            link = IncidentEvent(
                incident_id=incident.id,
                parsed_log_id=event.id,
                event_index=idx,
            )
            self.db.add(link)

        self.db.commit()
        self.db.refresh(incident)
        return incident

    def get_all(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Incident], int]:
        """Retrieve paginated incidents and total count."""
        query = self.db.query(Incident)
        if status:
            query = query.filter(Incident.status == status.upper())
        if severity and hasattr(Incident, "severity"):
            query = query.filter(getattr(Incident, "severity") == severity.upper())

        total = query.count()
        items = (
            query.order_by(
                Incident.started_at.is_(None),
                desc(Incident.started_at),
                desc(Incident.id),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def get_candidate_parsed_logs(self, log_id: Optional[int] = None) -> List[ParsedLog]:
        """
        Retrieve parsed log events eligible for correlation.
        If log_id is provided, filters to that source log.
        Events are ordered chronologically.
        """
        query = self.db.query(ParsedLog)
        if log_id is not None:
            query = query.filter(ParsedLog.log_id == log_id)

        return query.order_by(
            ParsedLog.timestamp.is_(None),
            asc(ParsedLog.timestamp),
            asc(ParsedLog.log_id),
            asc(ParsedLog.event_index),
            asc(ParsedLog.id),
        ).all()
