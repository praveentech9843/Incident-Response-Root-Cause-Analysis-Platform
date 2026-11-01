from typing import List, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from app.correlation.engine import CorrelationEngine, CorrelatedIncidentResult
from app.models.incident import Incident
from app.repositories.incident_repository import IncidentRepository
from app.schemas.incident import (
    IncidentResponse,
    IncidentDetailResponse,
    IncidentListResponse,
    CorrelateIncidentsResponse,
)
from app.schemas.parsed_log import ParsedLogEvent


class CorrelationService:
    """
    Service managing incident correlation workflows, deduplication, and database persistence.
    Operates strictly within Phase 3 correlation boundaries without root-cause deduction.
    """

    def __init__(
        self,
        incident_repo: IncidentRepository,
        engine: Optional[CorrelationEngine] = None,
    ):
        self.incident_repo = incident_repo
        self.engine = engine or CorrelationEngine(
            default_window_seconds=settings.INCIDENT_CORRELATION_WINDOW_SECONDS
        )

    def correlate_incidents(
        self,
        log_id: Optional[int] = None,
        time_window_seconds: Optional[int] = None,
    ) -> CorrelateIncidentsResponse:
        """
        Run deterministic correlation over eligible parsed log events.
        Identifies correlated incident clusters, prevents duplicate creation,
        and persists newly discovered incidents and incident_events.
        """
        # 1. Fetch candidate parsed log events
        candidate_events = self.incident_repo.get_candidate_parsed_logs(log_id=log_id)
        if not candidate_events:
            return CorrelateIncidentsResponse(
                events_considered=0,
                incidents_created=0,
                incidents_existing=0,
                incidents=[],
            )

        # 2. Run deterministic clustering through correlation engine
        cluster_results: List[CorrelatedIncidentResult] = self.engine.correlate(
            candidate_events, window_seconds=time_window_seconds
        )

        incidents_created = 0
        incidents_existing = 0
        final_incidents: List[IncidentResponse] = []

        # 3. Persist or reuse incidents deterministically using incident_key
        for cluster in cluster_results:
            existing = self.incident_repo.get_by_key(cluster.incident_key)
            if existing:
                incidents_existing += 1
                final_incidents.append(IncidentResponse.model_validate(existing))
            else:
                new_incident = Incident(
                    incident_key=cluster.incident_key,
                    title=cluster.title,
                    status=cluster.status,
                    started_at=cluster.started_at,
                    ended_at=cluster.ended_at,
                    event_count=cluster.event_count,
                    service_count=cluster.service_count,
                    correlation_reason=cluster.correlation_reason,
                    correlation_confidence=cluster.correlation_confidence,
                )
                persisted = self.incident_repo.create_incident_with_events(
                    new_incident, cluster.events
                )
                incidents_created += 1
                final_incidents.append(IncidentResponse.model_validate(persisted))

        return CorrelateIncidentsResponse(
            events_considered=len(candidate_events),
            incidents_created=incidents_created,
            incidents_existing=incidents_existing,
            incidents=final_incidents,
        )

    def get_incidents(
        self,
        status_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IncidentListResponse:
        """Fetch paginated incidents from PostgreSQL."""
        items, total = self.incident_repo.get_all(
            status=status_filter, severity=severity_filter, limit=limit, offset=offset
        )
        return IncidentListResponse(
            items=[IncidentResponse.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get_incident_detail(self, incident_id: int) -> IncidentDetailResponse:
        """Fetch a specific incident with its chronologically ordered constituent parsed events."""
        incident = self.incident_repo.get_by_id(incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with ID {incident_id} not found.",
            )

        events = self.incident_repo.get_events_for_incident(incident_id)
        incident_dict = IncidentResponse.model_validate(incident).model_dump()
        incident_dict["events"] = [ParsedLogEvent.model_validate(e) for e in events]
        return IncidentDetailResponse(**incident_dict)
