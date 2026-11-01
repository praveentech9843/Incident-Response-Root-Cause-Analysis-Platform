from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.context.base import (
    ContextProvider,
    ContextCategory,
    ContextStatus,
    ContextResult,
    DeploymentProvider,
)
from app.models.incident import Incident
from app.models.parsed_log import ParsedLog


class NullDeploymentProvider(DeploymentProvider):
    """
    Default provider when no external CI/CD or Git provider is configured.
    Explicitly communicates INTEGRATION_REQUIRED and avoids fabricating data.
    """

    def get_deployment_info(
        self,
        services: List[str],
        incident: Incident,
    ) -> Tuple[ContextStatus, Dict[str, Any], str]:
        data = {
            "deployment_version": None,
            "git_commit": None,
            "build_number": None,
            "deployed_at": None,
            "author": None,
            "release_notes": None,
            "rollback_available": None,
            "connected": False,
            "provider_name": "None",
            "message": "CI/CD / Git integration is not connected. Deployment context requires GitHub, GitLab, or ArgoCD integration.",
        }
        return ContextStatus.INTEGRATION_REQUIRED, data, "NullDeploymentProvider"


class DeploymentContextProvider(ContextProvider):
    """
    Collects deployment context using an extensible DeploymentProvider interface.
    Defaults to NullDeploymentProvider which truthfully returns INTEGRATION_REQUIRED.
    """

    def __init__(self, provider: Optional[DeploymentProvider] = None):
        self.provider = provider or NullDeploymentProvider()

    @property
    def category(self) -> ContextCategory:
        return ContextCategory.DEPLOYMENT

    def collect(
        self,
        incident: Incident,
        events: List[ParsedLog],
        db: Session,
    ) -> ContextResult:
        observed_services = [e.service_name for e in events if e.service_name]
        status, data, source = self.provider.get_deployment_info(observed_services, incident)

        return ContextResult(
            category=self.category,
            status=status,
            data=data,
            source=source,
        )
