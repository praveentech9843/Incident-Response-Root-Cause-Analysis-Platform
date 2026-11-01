from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.parsed_log import ParsedLog


class ContextCategory(str, Enum):
    """Supported context enrichment categories."""

    SERVICE = "service"
    DEPLOYMENT = "deployment"
    INFRASTRUCTURE = "infrastructure"
    METRICS = "metrics"
    HISTORY = "history"
    DEPENDENCIES = "dependencies"

    @classmethod
    def normalize(cls, category_name: str) -> Optional["ContextCategory"]:
        """Normalize category name handling singular/plural aliases."""
        clean = category_name.strip().lower()
        if clean in ("dependency", "dependencies"):
            return cls.DEPENDENCIES
        for member in cls:
            if member.value == clean:
                return member
        return None


class ContextStatus(str, Enum):
    """Explicit availability status for operational context."""

    AVAILABLE = "AVAILABLE"
    NOT_CONNECTED = "NOT_CONNECTED"
    UNAVAILABLE = "UNAVAILABLE"
    INTEGRATION_REQUIRED = "INTEGRATION_REQUIRED"


@dataclass
class ContextResult:
    """Standardized result of a context collection execution."""

    category: ContextCategory
    status: ContextStatus
    data: Dict[str, Any]
    source: str


class ContextProvider(ABC):
    """Base interface for an operational context category collector."""

    @property
    @abstractmethod
    def category(self) -> ContextCategory:
        """Category handled by this provider."""
        pass

    @abstractmethod
    def collect(
        self,
        incident: Incident,
        events: List[ParsedLog],
        db: Session,
    ) -> ContextResult:
        """
        Collect operational context for the specified incident.
        Strictly evidence-only; never fabricates data or infers root cause.
        """
        pass


class DeploymentProvider(ABC):
    """
    Interface for CI/CD and Version Control system integrations (e.g., GitHub, GitLab, ArgoCD).
    Implementations must return real, verified deployment metadata or explicit unavailable status.
    """

    @abstractmethod
    def get_deployment_info(
        self,
        services: List[str],
        incident: Incident,
    ) -> Tuple[ContextStatus, Dict[str, Any], str]:
        """Fetch deployment and commit evidence for the given services."""
        pass


class InfrastructureProvider(ABC):
    """
    Interface for container orchestrator and cloud infrastructure integrations (e.g., Kubernetes, ECS, AWS).
    Implementations must return real cluster/pod topology or explicit unavailable status.
    """

    @abstractmethod
    def get_infrastructure_info(
        self,
        services: List[str],
        incident: Incident,
    ) -> Tuple[ContextStatus, Dict[str, Any], str]:
        """Fetch infrastructure and container topology evidence for the given services."""
        pass


class MetricsProvider(ABC):
    """
    Interface for time-series metrics and APM systems (e.g., Prometheus, Datadog).
    Implementations must return real telemetry samples or explicit unavailable status.
    """

    @abstractmethod
    def get_metrics(
        self,
        services: List[str],
        incident: Incident,
    ) -> Tuple[ContextStatus, Dict[str, Any], str]:
        """Fetch real operational metrics for the services during the incident window."""
        pass
