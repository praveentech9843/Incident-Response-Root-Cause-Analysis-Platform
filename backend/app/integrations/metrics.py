from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.base import BaseIntegrationProvider, IntegrationStatus

logger = get_logger("metrics_provider")


class MetricsProvider(BaseIntegrationProvider, ABC):
    """Abstract interface for metrics provider."""

    @abstractmethod
    def query_metric(
        self,
        query: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        step: str = "15s",
    ) -> Dict[str, Any]:
        pass


class PrometheusMetricsProvider(MetricsProvider):
    """
    Real Prometheus metrics provider.
    Connects to real Prometheus instance when PROMETHEUS_ENABLED and PROMETHEUS_URL are configured.
    Defaults to NOT_CONNECTED when unconfigured.
    Never manufactures fake telemetry or metric data.
    """

    def __init__(self):
        super().__init__(name="prometheus")
        self.url = settings.PROMETHEUS_URL.rstrip("/") if settings.PROMETHEUS_URL else ""
        self.enabled = settings.PROMETHEUS_ENABLED and bool(self.url)

    def get_status(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "message": "Prometheus integration not configured. Set PROMETHEUS_URL and PROMETHEUS_ENABLED.",
            }
        try:
            # Query Prometheus buildinfo or healthy endpoint
            with httpx.Client(timeout=4.0) as client:
                res = client.get(f"{self.url}/-/healthy")
                if res.status_code == 200:
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.CONNECTED.value,
                        "url": self.url,
                    }
                return {
                    "provider": self.name,
                    "status": IntegrationStatus.UNAVAILABLE.value,
                    "message": f"Prometheus returned HTTP {res.status_code}",
                }
        except httpx.RequestError as exc:
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "message": f"Prometheus connection failed: {str(exc)}",
            }

    def query_metric(
        self,
        query: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        step: str = "15s",
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "results": [],
                "message": "Prometheus not configured.",
            }
        try:
            with httpx.Client(timeout=6.0) as client:
                if start_time and end_time:
                    url = f"{self.url}/api/v1/query_range"
                    params = {
                        "query": query,
                        "start": start_time,
                        "end": end_time,
                        "step": step,
                    }
                else:
                    url = f"{self.url}/api/v1/query"
                    params = {"query": query}
                res = client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.CONNECTED.value,
                        "results": data.get("data", {}).get("result", []),
                    }
                return {
                    "provider": self.name,
                    "status": IntegrationStatus.ERROR.value,
                    "results": [],
                    "message": f"Query returned HTTP {res.status_code}",
                }
        except httpx.RequestError as exc:
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "results": [],
                "message": str(exc),
            }
