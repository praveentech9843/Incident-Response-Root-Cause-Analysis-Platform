from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.context.base import (
    ContextCategory,
    ContextProvider,
    DeploymentProvider,
    InfrastructureProvider,
    MetricsProvider,
)
from app.context.service_context import ServiceContextProvider
from app.context.deployment_context import (
    DeploymentContextProvider,
    NullDeploymentProvider,
)
from app.context.infrastructure_context import (
    InfrastructureContextProvider,
    NullInfrastructureProvider,
)
from app.context.metrics_context import (
    MetricsContextProvider,
    NullMetricsProvider,
)
from app.context.history_context import HistoryContextProvider
from app.context.dependency_context import DependencyContextProvider
from app.repositories.incident_repository import IncidentRepository
from app.repositories.incident_context_repository import IncidentContextRepository
from app.schemas.incident_context import (
    IncidentContextItemResponse,
    EnrichedIncidentContextResponse,
)

logger = get_logger("app.services.context_enrichment")


class ContextEnrichmentService:
    """
    Orchestrates operational context enrichment for correlated incidents.
    Coordinates evidence collection across Service, Deployment, Infrastructure,
    Metrics, History, and Dependencies providers without fabricating data or performing RCA.
    """

    def __init__(
        self,
        db: Session,
        incident_repo: IncidentRepository,
        context_repo: IncidentContextRepository,
        deployment_provider: Optional[DeploymentProvider] = None,
        infrastructure_provider: Optional[InfrastructureProvider] = None,
        metrics_provider: Optional[MetricsProvider] = None,
    ):
        self.db = db
        self.incident_repo = incident_repo
        self.context_repo = context_repo
        self.deployment_provider = deployment_provider or NullDeploymentProvider()
        self.infrastructure_provider = infrastructure_provider or NullInfrastructureProvider()
        self.metrics_provider = metrics_provider or NullMetricsProvider()

    def _get_providers(self) -> List[ContextProvider]:
        """Construct the configured suite of context category collectors."""
        return [
            ServiceContextProvider(),
            DeploymentContextProvider(self.deployment_provider),
            InfrastructureContextProvider(self.infrastructure_provider),
            MetricsContextProvider(self.metrics_provider),
            HistoryContextProvider(),
            DependencyContextProvider(),
        ]

    def enrich_incident(self, incident_id: int) -> EnrichedIncidentContextResponse:
        """
        Execute full context enrichment pipeline for a specific incident.
        Truthfully collects real evidence, queries history, checks provider availability,
        and idempotently persists the resulting context entities.
        """
        incident = self.incident_repo.get_by_id(incident_id)
        if not incident:
            logger.warning("Incident enrichment requested for non-existent ID %s", incident_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with ID {incident_id} not found.",
            )

        events = self.incident_repo.get_events_for_incident(incident_id)
        logger.info(
            "Enriching incident %s ('%s') with %s constituent events",
            incident.id,
            incident.title,
            len(events),
        )

        providers = self._get_providers()
        results = []

        for p in providers:
            try:
                res = p.collect(incident=incident, events=events, db=self.db)
                results.append(res)
            except Exception as exc:
                logger.error(
                    "Error executing context provider %s for incident %s: %s",
                    p.category.value,
                    incident_id,
                    str(exc),
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to collect {p.category.value} context: {str(exc)}",
                )

        # Idempotently persist context entities
        saved_entities = self.context_repo.save_all_contexts(incident_id, results)

        contexts_dict: Dict[str, IncidentContextItemResponse] = {
            entity.context_category: IncidentContextItemResponse.model_validate(entity)
            for entity in saved_entities
        }

        return EnrichedIncidentContextResponse(
            incident_id=incident.id,
            incident_title=incident.title,
            total_categories=len(contexts_dict),
            contexts=contexts_dict,
            collected_at=datetime.now(timezone.utc),
        )

    def get_incident_context(self, incident_id: int) -> EnrichedIncidentContextResponse:
        """
        Retrieve all operational contexts for an incident.
        If the incident exists but has not been enriched yet, executes enrichment on demand.
        """
        incident = self.incident_repo.get_by_id(incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with ID {incident_id} not found.",
            )

        stored = self.context_repo.get_all_for_incident(incident_id)
        if not stored:
            # Auto-enrich on first request
            return self.enrich_incident(incident_id)

        contexts_dict = {
            entity.context_category: IncidentContextItemResponse.model_validate(entity)
            for entity in stored
        }

        latest_collected = max(
            (entity.collected_at for entity in stored),
            default=datetime.now(timezone.utc),
        )

        return EnrichedIncidentContextResponse(
            incident_id=incident.id,
            incident_title=incident.title,
            total_categories=len(contexts_dict),
            contexts=contexts_dict,
            collected_at=latest_collected,
        )

    def get_incident_context_category(
        self, incident_id: int, category_name: str
    ) -> IncidentContextItemResponse:
        """Retrieve a specific context category entity for an incident."""
        incident = self.incident_repo.get_by_id(incident_id)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with ID {incident_id} not found.",
            )

        norm_cat = ContextCategory.normalize(category_name)
        if not norm_cat:
            valid_cats = ", ".join([c.value for c in ContextCategory])
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown context category '{category_name}'. Valid categories are: {valid_cats}",
            )

        record = self.context_repo.get_by_incident_and_category(incident_id, norm_cat.value)
        if not record:
            # Trigger enrichment if not yet enriched
            self.enrich_incident(incident_id)
            record = self.context_repo.get_by_incident_and_category(incident_id, norm_cat.value)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Context for category '{norm_cat.value}' not found for incident {incident_id}.",
            )

        return IncidentContextItemResponse.model_validate(record)
