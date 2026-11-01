import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.incident_rca import IncidentRCAAnalysis
from app.rca.schemas import RCAResult


class IncidentRCARepository:
    """Repository handling persistence and retrieval of Incident RCA analyses in PostgreSQL."""

    def __init__(self, db: Session):
        self.db = db

    def create_analysis(
        self,
        incident_id: int,
        result: RCAResult,
        evidence_snapshot: Dict[str, Any],
    ) -> IncidentRCAAnalysis:
        analysis_id = f"rca-{uuid.uuid4().hex[:12]}"
        db_analysis = IncidentRCAAnalysis(
            incident_id=incident_id,
            analysis_id=analysis_id,
            analysis_status=result.analysis_status.value,
            provider=result.provider,
            model=result.model,
            summary=result.summary,
            confidence=result.confidence,
            confidence_level=result.confidence_level.value if result.confidence_level else None,
            hypotheses=[h.model_dump(mode="json") for h in result.hypotheses],
            evidence_snapshot=evidence_snapshot,
            limitations=result.limitations,
        )
        self.db.add(db_analysis)
        self.db.commit()
        self.db.refresh(db_analysis)
        return db_analysis

    def get_latest_for_incident(self, incident_id: int) -> Optional[IncidentRCAAnalysis]:
        stmt = (
            select(IncidentRCAAnalysis)
            .where(IncidentRCAAnalysis.incident_id == incident_id)
            .order_by(IncidentRCAAnalysis.created_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def get_history_for_incident(
        self,
        incident_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> List[IncidentRCAAnalysis]:
        stmt = (
            select(IncidentRCAAnalysis)
            .where(IncidentRCAAnalysis.incident_id == incident_id)
            .order_by(IncidentRCAAnalysis.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_for_incident(self, incident_id: int) -> int:
        stmt = (
            select(func.count(IncidentRCAAnalysis.id))
            .where(IncidentRCAAnalysis.incident_id == incident_id)
        )
        return self.db.execute(stmt).scalar() or 0

    def get_by_analysis_id(self, analysis_id: str) -> Optional[IncidentRCAAnalysis]:
        stmt = select(IncidentRCAAnalysis).where(IncidentRCAAnalysis.analysis_id == analysis_id)
        return self.db.execute(stmt).scalars().first()
