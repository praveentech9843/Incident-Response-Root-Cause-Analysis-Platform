from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.context.base import (
    ContextProvider,
    ContextCategory,
    ContextStatus,
    ContextResult,
    MetricsProvider,
)
from app.models.incident import Incident
from app.models.parsed_log import ParsedLog


class NullMetricsProvider(MetricsProvider):
    """
    Default provider when no telemetry, APM, or time-series system is connected.
    Explicitly reports NOT_CONNECTED and strictly forbids generating synthetic metrics.
    """

    def get_metrics(
        self,
        services: List[str],
        incident: Incident,
    ) -> Tuple[ContextStatus, Dict[str, Any], str]:
        data = {
            "cpu_usage": None,
            "memory_usage": None,
            "network_usage": None,
            "request_rate": None,
            "error_rate": None,
            "latency": None,
            "p95": None,
            "p99": None,
            "prometheus": "Not connected",
            "datadog": "Not connected",
            "connected": False,
            "message": "Metrics backend not connected. No synthetic metrics generated. Real integration with Prometheus or Datadog required.",
        }
        return ContextStatus.NOT_CONNECTED, data, "NullMetricsProvider"


class MetricsContextProvider(ContextProvider):
    """
    Collects metrics context using an extensible MetricsProvider interface.
    Defaults to NullMetricsProvider which truthfully returns NOT_CONNECTED.
    """

    def __init__(self, provider: Optional[MetricsProvider] = None):
        self.provider = provider or NullMetricsProvider()

    @property
    def category(self) -> ContextCategory:
        return ContextCategory.METRICS

    def collect(
        self,
        incident: Incident,
        events: List[ParsedLog],
        db: Session,
    ) -> ContextResult:
        observed_services = [e.service_name for e in events if e.service_name]
        status, data, source = self.provider.get_metrics(observed_services, incident)

        return ContextResult(
            category=self.category,
            status=status,
            data=data,
            source=source,
        )
