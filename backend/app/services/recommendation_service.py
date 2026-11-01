from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.recommendations.base import RecommendationProvider
from app.recommendations.evidence import RecommendationEvidenceBuilder
from app.recommendations.generator import RecommendationGenerator
from app.recommendations.providers.factory import get_recommendation_provider
from app.recommendations.schemas import (
    IncidentRecommendationHistoryResponse,
    IncidentRecommendationListResponse,
    IncidentRecommendationResponse,
)
from app.repositories.incident_rca_repository import IncidentRCARepository
from app.repositories.incident_recommendation_repository import (
    IncidentRecommendationRepository,
)


class RecommendationService:
    """
    Service layer coordinating operational investigation and fix recommendation generation,
    validation, persistence, and audit history.
    """

    def __init__(self, db: Session, provider: Optional[RecommendationProvider] = None):
        self.db = db
        self.repo = IncidentRecommendationRepository(db)
        self.rca_repo = IncidentRCARepository(db)
        resolved_provider = provider if provider is not None else get_recommendation_provider()
        self.generator = RecommendationGenerator(provider=resolved_provider)

    def _get_incident_or_404(self, incident_id: int) -> Incident:
        incident = self.db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with id {incident_id} not found",
            )
        return incident

    def generate_recommendations(self, incident_id: int) -> IncidentRecommendationListResponse:
        """
        Generates operational recommendations strictly derived from the latest validated RCA analysis.
        Rejects generation with 409 Conflict if no RCA analysis exists.
        """
        incident = self._get_incident_or_404(incident_id)

        # 1. Retrieve latest validated RCA analysis
        latest_rca = self.rca_repo.get_latest_for_incident(incident_id)
        if not latest_rca:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Validated RCA is required before generating recommendations.",
            )

        # 2. Build RecommendationInput context
        rec_input = RecommendationEvidenceBuilder.build(incident, latest_rca)

        # 3. Generate and validate recommendations
        result = self.generator.generate(rec_input)

        # 4. Persist recommendations to PostgreSQL for auditability
        persisted_records = []
        if result.recommendations:
            persisted_records = self.repo.create_recommendations(
                incident_id=incident_id,
                rca_analysis_id=latest_rca.id,
                items=result.recommendations,
            )

        items = [
            IncidentRecommendationResponse.model_validate(rec)
            for rec in persisted_records
        ]

        return IncidentRecommendationListResponse(
            incident_id=incident_id,
            rca_analysis_id=latest_rca.id,
            status=result.status.value if hasattr(result.status, "value") else str(result.status),
            total_recommendations=len(items),
            recommendations=items,
            limitations=result.limitations,
            provider=result.provider,
            model=result.model,
            generated_at=datetime.now(timezone.utc),
        )

    def get_latest_recommendations(self, incident_id: int) -> IncidentRecommendationListResponse:
        """Retrieves the latest generated batch of recommendations for an incident."""
        self._get_incident_or_404(incident_id)
        records = self.repo.get_latest_recommendations_for_incident(incident_id)

        rca_analysis_id = records[0].rca_analysis_id if records else 0
        items = [IncidentRecommendationResponse.model_validate(r) for r in records]

        return IncidentRecommendationListResponse(
            incident_id=incident_id,
            rca_analysis_id=rca_analysis_id,
            status="COMPLETED" if items else "NO_RECOMMENDATIONS",
            total_recommendations=len(items),
            recommendations=items,
            limitations=[],
            provider="stored",
            model="stored",
            generated_at=records[0].created_at if records else datetime.now(timezone.utc),
        )

    def get_recommendation_by_id(
        self, incident_id: int, recommendation_id: str
    ) -> IncidentRecommendationResponse:
        """Retrieves a single recommendation by unique string ID."""
        self._get_incident_or_404(incident_id)
        record = self.repo.get_recommendation_by_id(incident_id, recommendation_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Recommendation with id '{recommendation_id}' not found for incident {incident_id}",
            )
        return IncidentRecommendationResponse.model_validate(record)

    def get_recommendation_history(
        self, incident_id: int, limit: int = 100, offset: int = 0
    ) -> IncidentRecommendationHistoryResponse:
        """Retrieves all historical recommendations generated for the incident."""
        self._get_incident_or_404(incident_id)
        records = self.repo.get_history_for_incident(incident_id, limit=limit, offset=offset)
        items = [IncidentRecommendationResponse.model_validate(r) for r in records]

        return IncidentRecommendationHistoryResponse(
            incident_id=incident_id,
            total_recommendations=len(items),
            items=items,
        )
