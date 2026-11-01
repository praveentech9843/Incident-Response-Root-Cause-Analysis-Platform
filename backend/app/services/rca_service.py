from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.parsed_log import ParsedLog
from app.models.incident_context import IncidentContext
from app.rca.analyzer import RootCauseAnalyzer
from app.rca.base import RCAProvider
from app.rca.evidence import RCAEvidenceBuilder
from app.rca.providers.factory import get_rca_provider
from app.rca.schemas import (
    IncidentRCAAnalysisResponse,
    IncidentRCAHistoryResponse,
)
from app.repositories.incident_rca_repository import IncidentRCARepository


class RCAService:
    """Service layer coordinating Root Cause Analysis execution and historical retrieval."""

    def __init__(self, db: Session, provider: Optional[RCAProvider] = None):
        self.db = db
        self.repo = IncidentRCARepository(db)
        resolved_provider = provider if provider is not None else get_rca_provider()
        self.analyzer = RootCauseAnalyzer(provider=resolved_provider)

    def _get_incident_or_404(self, incident_id: int) -> Incident:
        incident = self.db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with id {incident_id} not found",
            )
        return incident

    def run_incident_rca(self, incident_id: int) -> IncidentRCAAnalysisResponse:
        """Executes evidence-grounded RCA reasoning and persists an auditable analysis record."""
        incident = self._get_incident_or_404(incident_id)

        # 1. Load constituent parsed log events via incident_events
        incident_events = (
            self.db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.event_index.asc())
            .all()
        )
        parsed_log_ids = [ie.parsed_log_id for ie in incident_events]
        parsed_logs = []
        if parsed_log_ids:
            # Preserve event_index ordering
            logs_map = {
                pl.id: pl
                for pl in self.db.query(ParsedLog).filter(ParsedLog.id.in_(parsed_log_ids)).all()
            }
            parsed_logs = [logs_map[pid] for pid in parsed_log_ids if pid in logs_map]

        # 2. Load Phase 4 operational context records
        contexts = (
            self.db.query(IncidentContext)
            .filter(IncidentContext.incident_id == incident_id)
            .all()
        )

        # 3. Build deterministic, controlled evidence package
        evidence_package = RCAEvidenceBuilder.build(
            incident=incident,
            events=parsed_logs,
            contexts=contexts,
        )

        # 4. Execute RCA reasoning and validation
        rca_result = self.analyzer.analyze(evidence_package)

        # 5. Persist analysis along with full evidence snapshot for auditability
        db_analysis = self.repo.create_analysis(
            incident_id=incident_id,
            result=rca_result,
            evidence_snapshot=evidence_package.to_snapshot(),
        )

        return IncidentRCAAnalysisResponse.model_validate(db_analysis)

    def get_latest_rca(self, incident_id: int) -> IncidentRCAAnalysisResponse:
        """Retrieves the most recent RCA analysis for an incident."""
        self._get_incident_or_404(incident_id)
        latest = self.repo.get_latest_for_incident(incident_id)
        if not latest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No RCA analysis found for incident {incident_id}",
            )
        return IncidentRCAAnalysisResponse.model_validate(latest)

    def get_rca_history(
        self,
        incident_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> IncidentRCAHistoryResponse:
        """Retrieves all previous RCA analyses for an incident in descending chronological order."""
        self._get_incident_or_404(incident_id)
        items = self.repo.get_history_for_incident(incident_id, limit=limit, offset=offset)
        total = self.repo.count_for_incident(incident_id)

        return IncidentRCAHistoryResponse(
            incident_id=incident_id,
            total=total,
            items=[IncidentRCAAnalysisResponse.model_validate(item) for item in items],
        )

    def get_rca_by_id(self, incident_id: int, analysis_id: str) -> IncidentRCAAnalysisResponse:
        """Retrieves a specific RCA analysis by its unique analysis_id."""
        self._get_incident_or_404(incident_id)
        analysis = self.repo.get_by_analysis_id(analysis_id)
        if not analysis or analysis.incident_id != incident_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"RCA analysis '{analysis_id}' not found for incident {incident_id}",
            )
        return IncidentRCAAnalysisResponse.model_validate(analysis)
