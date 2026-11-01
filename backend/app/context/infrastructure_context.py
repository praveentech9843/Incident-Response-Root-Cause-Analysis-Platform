from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.context.base import (
    ContextProvider,
    ContextCategory,
    ContextStatus,
    ContextResult,
    InfrastructureProvider,
)
from app.models.incident import Incident
from app.models.parsed_log import ParsedLog


class NullInfrastructureProvider(InfrastructureProvider):
    """
    Default provider when no container or orchestrator provider is connected.
    Explicitly reports NOT_CONNECTED without fabricating nodes, pods, or clusters.
    """

    def get_infrastructure_info(
        self,
        services: List[str],
        incident: Incident,
    ) -> Tuple[ContextStatus, Dict[str, Any], str]:
        data = {
            "cluster": None,
            "namespace": None,
            "pods": [],
            "nodes": [],
            "containers": [],
            "availability_zone": None,
            "cloud_provider": None,
            "connected": False,
            "provider_name": "None",
            "message": "Infrastructure orchestrator is not connected. Connect Kubernetes, ECS, or Docker engine to populate runtime topology.",
        }
        return ContextStatus.NOT_CONNECTED, data, "NullInfrastructureProvider"


class InfrastructureContextProvider(ContextProvider):
    """
    Collects infrastructure context using an extensible InfrastructureProvider interface.
    Defaults to NullInfrastructureProvider which truthfully returns NOT_CONNECTED.
    """

    def __init__(self, provider: Optional[InfrastructureProvider] = None):
        self.provider = provider or NullInfrastructureProvider()

    @property
    def category(self) -> ContextCategory:
        return ContextCategory.INFRASTRUCTURE

    def collect(
        self,
        incident: Incident,
        events: List[ParsedLog],
        db: Session,
    ) -> ContextResult:
        observed_services = [e.service_name for e in events if e.service_name]
        status, data, source = self.provider.get_infrastructure_info(observed_services, incident)

        return ContextResult(
            category=self.category,
            status=status,
            data=data,
            source=source,
        )
