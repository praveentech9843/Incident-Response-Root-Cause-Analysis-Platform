from typing import Dict, Any
from app.core.config import settings
from app.integrations.base import IntegrationStatus, BaseIntegrationProvider
from app.integrations.deployment import DeploymentProvider, GitHubActionsDeploymentProvider
from app.integrations.source_control import SourceControlProvider, GitHubSourceControlProvider
from app.integrations.infrastructure import InfrastructureProvider, KubernetesInfrastructureProvider
from app.integrations.metrics import MetricsProvider, PrometheusMetricsProvider


def get_deployment_provider() -> DeploymentProvider:
    return GitHubActionsDeploymentProvider()


def get_source_control_provider() -> SourceControlProvider:
    return GitHubSourceControlProvider()


def get_infrastructure_provider() -> InfrastructureProvider:
    return KubernetesInfrastructureProvider()


def get_metrics_provider() -> MetricsProvider:
    return PrometheusMetricsProvider()


def get_all_integrations_status() -> Dict[str, Any]:
    dep_raw = get_deployment_provider().get_status()
    sc_raw = get_source_control_provider().get_status()
    infra_raw = get_infrastructure_provider().get_status()
    met_raw = get_metrics_provider().get_status()

    def normalize_status(raw: Dict[str, Any], default_name: str, configured_flag: bool) -> Dict[str, Any]:
        state_val = raw.get("status") or raw.get("state") or "NOT_CONNECTED"
        return {
            "name": default_name,
            "provider": raw.get("provider", default_name.lower().replace(" ", "_")),
            "state": state_val,
            "status": state_val,
            "configured": configured_flag,
            "message": raw.get("message") or (f"{default_name} is connected" if state_val == "CONNECTED" else f"{default_name} is not configured"),
            "details": {k: v for k, v in raw.items() if k not in ("provider", "status", "state", "message")},
        }

    dep_status = normalize_status(
        dep_raw,
        "GitHub Actions",
        settings.GITHUB_ENABLED and bool(settings.GITHUB_TOKEN) and bool(settings.GITHUB_REPO),
    )
    sc_status = normalize_status(
        sc_raw,
        "GitHub Source Control",
        settings.GITHUB_ENABLED and bool(settings.GITHUB_TOKEN) and bool(settings.GITHUB_REPO),
    )
    infra_status = normalize_status(
        infra_raw,
        "Kubernetes",
        settings.KUBERNETES_ENABLED,
    )
    met_status = normalize_status(
        met_raw,
        "Prometheus",
        settings.PROMETHEUS_ENABLED and bool(settings.PROMETHEUS_URL),
    )

    # Notification providers
    slack_conf = settings.SLACK_ENABLED and bool(settings.SLACK_TOKEN)
    slack_status = {
        "name": "Slack Notifications",
        "provider": "slack",
        "state": "CONNECTED" if slack_conf else "NOT_CONNECTED",
        "status": "CONNECTED" if slack_conf else "NOT_CONNECTED",
        "configured": slack_conf,
        "message": "Slack notifications configured" if slack_conf else "Slack not configured. Set SLACK_ENABLED and SLACK_TOKEN.",
        "details": {"channel": settings.SLACK_DEFAULT_CHANNEL if slack_conf else None},
    }

    pd_conf = settings.PAGERDUTY_ENABLED and bool(settings.PAGERDUTY_TOKEN)
    pd_status = {
        "name": "PagerDuty",
        "provider": "pagerduty",
        "state": "CONNECTED" if pd_conf else "NOT_CONNECTED",
        "status": "CONNECTED" if pd_conf else "NOT_CONNECTED",
        "configured": pd_conf,
        "message": "PagerDuty events API configured" if pd_conf else "PagerDuty not configured. Set PAGERDUTY_ENABLED and PAGERDUTY_TOKEN.",
        "details": {},
    }

    email_conf = settings.EMAIL_ENABLED and bool(settings.SMTP_HOST)
    email_status = {
        "name": "SMTP Email",
        "provider": "email",
        "state": "CONNECTED" if email_conf else "NOT_CONNECTED",
        "status": "CONNECTED" if email_conf else "NOT_CONNECTED",
        "configured": email_conf,
        "message": f"SMTP email configured via {settings.SMTP_HOST}:{settings.SMTP_PORT}" if email_conf else "Email not configured. Set EMAIL_ENABLED and SMTP_HOST.",
        "details": {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT} if email_conf else {},
    }

    integrations_map = {
        "deployment": dep_status,
        "source_control": sc_status,
        "infrastructure": infra_status,
        "metrics": met_status,
        "slack": slack_status,
        "pagerduty": pd_status,
        "email": email_status,
    }

    total = len(integrations_map)
    connected = sum(1 for item in integrations_map.values() if item["state"] == "CONNECTED")
    not_connected = sum(1 for item in integrations_map.values() if item["state"] == "NOT_CONNECTED")
    unavailable = sum(1 for item in integrations_map.values() if item["state"] in ("UNAVAILABLE", "ERROR"))

    return {
        # Top-level direct keys (for backward compatibility with test_integrations.py)
        "deployment": dep_status,
        "source_control": sc_status,
        "infrastructure": infra_status,
        "metrics": met_status,
        "slack": slack_status,
        "pagerduty": pd_status,
        "email": email_status,
        # Grouped dict and summary (for Frontend and Phase 8 E2E verifier)
        "integrations": integrations_map,
        "summary": {
            "total": total,
            "connected": connected,
            "not_connected": not_connected,
            "unavailable": unavailable,
        },
    }
