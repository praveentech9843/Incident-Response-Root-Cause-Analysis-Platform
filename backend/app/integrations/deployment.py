from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.base import BaseIntegrationProvider, IntegrationStatus

logger = get_logger("deployment_provider")


class DeploymentProvider(BaseIntegrationProvider, ABC):
    """Abstract interface for deployment status and history providers."""

    @abstractmethod
    def get_recent_deployments(self, limit: int = 10) -> Dict[str, Any]:
        """Fetch list of recent deployments."""
        pass

    @abstractmethod
    def get_deployment_details(self, deployment_id: str) -> Dict[str, Any]:
        """Fetch details of a single deployment run."""
        pass


class GitHubActionsDeploymentProvider(DeploymentProvider):
    """
    Real GitHub Actions deployment provider.
    Connects only when GITHUB_TOKEN and GITHUB_REPO are configured.
    Never fabricates fake deployment records.
    """

    def __init__(self):
        super().__init__(name="github_actions")
        self.token = settings.GITHUB_TOKEN
        self.repo = settings.GITHUB_REPO
        self.enabled = settings.GITHUB_ENABLED and bool(self.token) and bool(self.repo)

    def get_status(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "message": "GitHub Actions not configured. Set GITHUB_TOKEN and GITHUB_REPO to connect.",
            }
        try:
            # Quick connectivity check
            url = f"https://api.github.com/repos/{self.repo}"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Incident-Response-Platform",
            }
            with httpx.Client(timeout=5.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 200:
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.CONNECTED.value,
                        "repository": self.repo,
                    }
                elif res.status_code in (401, 403):
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.ERROR.value,
                        "message": f"GitHub authentication failed (HTTP {res.status_code})",
                    }
                else:
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.UNAVAILABLE.value,
                        "message": f"GitHub returned HTTP {res.status_code}",
                    }
        except httpx.RequestError as exc:
            logger.warning("GitHub Actions connectivity check failed: %s", exc)
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "message": f"Connection error: {str(exc)}",
            }

    def get_recent_deployments(self, limit: int = 10) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "deployments": [],
                "message": "Integration not configured.",
            }
        url = f"https://api.github.com/repos/{self.repo}/actions/runs"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Incident-Response-Platform",
        }
        params = {"per_page": min(limit, 30)}
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    runs = res.json().get("workflow_runs", [])
                    deployments = [
                        {
                            "id": str(r["id"]),
                            "name": r.get("name"),
                            "status": r.get("status"),
                            "conclusion": r.get("conclusion"),
                            "created_at": r.get("created_at"),
                            "updated_at": r.get("updated_at"),
                            "head_branch": r.get("head_branch"),
                            "head_sha": r.get("head_sha"),
                            "html_url": r.get("html_url"),
                        }
                        for r in runs
                    ]
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.CONNECTED.value,
                        "deployments": deployments,
                    }
                return {
                    "provider": self.name,
                    "status": IntegrationStatus.ERROR.value,
                    "deployments": [],
                    "message": f"GitHub API error HTTP {res.status_code}",
                }
        except httpx.RequestError as exc:
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "deployments": [],
                "message": f"Connection failure: {str(exc)}",
            }

    def get_deployment_details(self, deployment_id: str) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "message": "Integration not configured.",
            }
        url = f"https://api.github.com/repos/{self.repo}/actions/runs/{deployment_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Incident-Response-Platform",
        }
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.CONNECTED.value,
                        "details": data,
                    }
                return {
                    "provider": self.name,
                    "status": IntegrationStatus.ERROR.value,
                    "message": f"GitHub API error HTTP {res.status_code}",
                }
        except httpx.RequestError as exc:
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "message": str(exc),
            }
