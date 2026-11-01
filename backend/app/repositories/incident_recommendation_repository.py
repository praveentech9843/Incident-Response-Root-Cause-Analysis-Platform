from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.incident_recommendation import IncidentRecommendation
from app.recommendations.schemas import RecommendationItem


class IncidentRecommendationRepository:
    """Repository handling persistence and retrieval of incident recommendations in PostgreSQL."""

    def __init__(self, db: Session):
        self.db = db

    def create_recommendations(
        self,
        incident_id: int,
        rca_analysis_id: int,
        items: List[RecommendationItem],
    ) -> List[IncidentRecommendation]:
        created_records: List[IncidentRecommendation] = []
        batch_timestamp = datetime.now(timezone.utc)
        for item in items:
            rec = IncidentRecommendation(
                recommendation_id=item.recommendation_id,
                incident_id=incident_id,
                rca_analysis_id=rca_analysis_id,
                type=item.type.value if hasattr(item.type, "value") else str(item.type),
                title=item.title,
                description=item.description,
                rationale=item.rationale,
                supporting_evidence=item.supporting_evidence,
                confidence=item.confidence,
                confidence_level=(
                    item.confidence_level.value
                    if hasattr(item.confidence_level, "value")
                    else str(item.confidence_level)
                ),
                risk_level=item.risk_level.value if hasattr(item.risk_level, "value") else str(item.risk_level),
                expected_impact=item.expected_impact,
                prerequisites=item.prerequisites,
                verification_steps=item.verification_steps,
                status=item.status.value if hasattr(item.status, "value") else str(item.status),
                created_at=batch_timestamp,
            )
            self.db.add(rec)
            created_records.append(rec)

        if created_records:
            self.db.commit()
            for rec in created_records:
                self.db.refresh(rec)

        return created_records

    def get_latest_recommendations_for_incident(
        self, incident_id: int
    ) -> List[IncidentRecommendation]:
        """Returns the most recent batch of recommendations generated for the incident."""
        latest_rec = (
            self.db.query(IncidentRecommendation)
            .filter(IncidentRecommendation.incident_id == incident_id)
            .order_by(IncidentRecommendation.id.desc())
            .first()
        )
        if not latest_rec:
            return []

        return (
            self.db.query(IncidentRecommendation)
            .filter(
                IncidentRecommendation.incident_id == incident_id,
                IncidentRecommendation.created_at == latest_rec.created_at,
            )
            .order_by(IncidentRecommendation.id.asc())
            .all()
        )

    def get_recommendation_by_id(
        self, incident_id: int, recommendation_id: str
    ) -> Optional[IncidentRecommendation]:
        """Returns a specific recommendation by its unique string recommendation_id."""
        stmt = (
            select(IncidentRecommendation)
            .where(
                IncidentRecommendation.incident_id == incident_id,
                IncidentRecommendation.recommendation_id == recommendation_id,
            )
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def get_history_for_incident(
        self, incident_id: int, limit: int = 100, offset: int = 0
    ) -> List[IncidentRecommendation]:
        """Returns historical recommendations for an incident ordered by created_at descending."""
        stmt = (
            select(IncidentRecommendation)
            .where(IncidentRecommendation.incident_id == incident_id)
            .order_by(IncidentRecommendation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
