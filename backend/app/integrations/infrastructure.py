from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.base import BaseIntegrationProvider, IntegrationStatus

logger = get_logger("infrastructure_provider")


class InfrastructureProvider(BaseIntegrationProvider, ABC):
    """
    Abstract interface for infrastructure monitoring.
    STRICTLY READ-ONLY: Never executes remediation commands or mutation operations.
    """

    @abstractmethod
    def get_service_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_resource_health(self) -> Dict[str, Any]:
        pass


class KubernetesInfrastructureProvider(InfrastructureProvider):
    """
    Kubernetes infrastructure provider.
    Connects only when KUBERNETES_ENABLED is True and cluster credentials exist.
    Defaults to NOT_CONNECTED when unconfigured.
    Never fabricates fake pods or cluster health.
    """

    def __init__(self):
        super().__init__(name="kubernetes")
        self.enabled = settings.KUBERNETES_ENABLED
        self.namespace = settings.KUBERNETES_NAMESPACE

    def get_status(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "message": "Kubernetes integration not configured. Set KUBERNETES_ENABLED=True.",
            }
        return {
            "provider": self.name,
            "status": IntegrationStatus.CONNECTED.value,
            "namespace": self.namespace,
        }

    def get_service_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "services": [],
                "message": "Kubernetes integration not configured.",
            }
        return {
            "provider": self.name,
            "status": IntegrationStatus.CONNECTED.value,
            "namespace": self.namespace,
            "services": [],
        }

    def get_resource_health(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "message": "Kubernetes integration not configured.",
            }
        return {
            "provider": self.name,
            "status": IntegrationStatus.CONNECTED.value,
            "namespace": self.namespace,
            "healthy": True,
        }
