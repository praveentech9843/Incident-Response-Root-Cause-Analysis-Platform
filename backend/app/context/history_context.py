from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import asc, select

from app.context.base import (
    ContextProvider,
    ContextCategory,
    ContextStatus,
    ContextResult,
)
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.parsed_log import ParsedLog


class HistoryContextProvider(ContextProvider):
    """
    Derives incident history context strictly from existing persisted incidents in PostgreSQL.
    Identifies prior occurrences sharing services or patterns without fabricating history.
    """

    @property
    def category(self) -> ContextCategory:
        return ContextCategory.HISTORY

    def collect(
        self,
        incident: Incident,
        events: List[ParsedLog],
        db: Session,
    ) -> ContextResult:
        # Extract unique services involved in this incident
        current_services = {e.service_name.strip() for e in events if e.service_name and e.service_name.strip()}

        # Query past incidents that occurred prior to this incident
        # Prior is defined by started_at < incident.started_at (or created_at < incident.created_at, or id < incident.id)
        query = db.query(Incident).filter(Incident.id != incident.id)

        if incident.started_at is not None:
            query = query.filter(
                (Incident.started_at < incident.started_at)
                | ((Incident.started_at.is_(None)) & (Incident.created_at < incident.created_at))
                | (Incident.id < incident.id)
            )
        else:
            query = query.filter((Incident.created_at < incident.created_at) | (Incident.id < incident.id))

        if current_services:
            # Subquery to match past incidents that share at least one service
            matching_incident_subq = (
                select(IncidentEvent.incident_id)
                .join(ParsedLog, ParsedLog.id == IncidentEvent.parsed_log_id)
                .filter(ParsedLog.service_name.in_(list(current_services)))
                .distinct()
            )
            query = query.filter(Incident.id.in_(matching_incident_subq))

        past_incidents = (
            query.order_by(
                Incident.started_at.is_(None),
                asc(Incident.started_at),
                asc(Incident.created_at),
                asc(Incident.id),
            ).all()
        )

        prev_count = len(past_incidents)
        prev_ids = [p.id for p in past_incidents]
        recurring = prev_count > 0

        first_ts = None
        latest_ts = None
        if past_incidents:
            first_event = past_incidents[0].started_at or past_incidents[0].created_at
            latest_event = past_incidents[-1].started_at or past_incidents[-1].created_at
            first_ts = first_event.isoformat() if first_event else None
            latest_ts = latest_event.isoformat() if latest_event else None

        data = {
            "previous_occurrence_count": prev_count,
            "previous_incident_ids": prev_ids,
            "first_occurrence_timestamp": first_ts,
            "latest_occurrence_timestamp": latest_ts,
            "recurring": recurring,
            "matching_services": sorted(list(current_services)),
            "source_details": f"Queried from PostgreSQL incidents table matching {len(current_services)} observed services",
        }

        return ContextResult(
            category=self.category,
            status=ContextStatus.AVAILABLE,
            data=data,
            source="incident_history_db",
        )
