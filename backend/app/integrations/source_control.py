from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.base import BaseIntegrationProvider, IntegrationStatus

logger = get_logger("source_control_provider")


class SourceControlProvider(BaseIntegrationProvider, ABC):
    """
    Abstract interface for source control integration.
    STRICTLY READ-ONLY: Never executes automatic commits, PRs, or file changes.
    """

    @abstractmethod
    def get_repository_info(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_recent_commits(self, limit: int = 10) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_pull_requests(self, state: str = "open", limit: int = 10) -> Dict[str, Any]:
        pass


class GitHubSourceControlProvider(SourceControlProvider):
    """
    Real GitHub source control provider (Read-Only).
    Connects only when GITHUB_TOKEN and GITHUB_REPO are configured.
    Never fabricates commits, PRs, or diffs.
    """

    def __init__(self):
        super().__init__(name="github_source_control")
        self.token = settings.GITHUB_TOKEN
        self.repo = settings.GITHUB_REPO
        self.enabled = settings.GITHUB_ENABLED and bool(self.token) and bool(self.repo)

    def get_status(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "message": "GitHub Source Control not configured. Set GITHUB_TOKEN and GITHUB_REPO.",
            }
        try:
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
                        "read_only": True,
                    }
                elif res.status_code in (401, 403):
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.ERROR.value,
                        "message": "GitHub credentials unauthorized",
                    }
                else:
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.UNAVAILABLE.value,
                        "message": f"GitHub returned HTTP {res.status_code}",
                    }
        except httpx.RequestError as exc:
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "message": str(exc),
            }

    def get_repository_info(self) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "message": "Not configured",
            }
        url = f"https://api.github.com/repos/{self.repo}"
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
                        "name": data.get("name"),
                        "full_name": data.get("full_name"),
                        "default_branch": data.get("default_branch"),
                        "html_url": data.get("html_url"),
                    }
                return {
                    "provider": self.name,
                    "status": IntegrationStatus.ERROR.value,
                    "message": f"HTTP {res.status_code}",
                }
        except httpx.RequestError as exc:
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "message": str(exc),
            }

    def get_recent_commits(self, limit: int = 10) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "commits": [],
                "message": "Integration not configured.",
            }
        url = f"https://api.github.com/repos/{self.repo}/commits"
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
                    raw_commits = res.json()
                    commits = [
                        {
                            "sha": c.get("sha"),
                            "author": c.get("commit", {}).get("author", {}).get("name"),
                            "date": c.get("commit", {}).get("author", {}).get("date"),
                            "message": c.get("commit", {}).get("message"),
                            "html_url": c.get("html_url"),
                        }
                        for c in raw_commits
                    ]
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.CONNECTED.value,
                        "commits": commits,
                    }
                return {
                    "provider": self.name,
                    "status": IntegrationStatus.ERROR.value,
                    "commits": [],
                    "message": f"GitHub returned HTTP {res.status_code}",
                }
        except httpx.RequestError as exc:
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "commits": [],
                "message": str(exc),
            }

    def get_pull_requests(self, state: str = "open", limit: int = 10) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "provider": self.name,
                "status": IntegrationStatus.NOT_CONNECTED.value,
                "pull_requests": [],
                "message": "Integration not configured.",
            }
        url = f"https://api.github.com/repos/{self.repo}/pulls"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Incident-Response-Platform",
        }
        params = {"state": state, "per_page": min(limit, 30)}
        try:
            with httpx.Client(timeout=8.0) as client:
                res = client.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    raw_prs = res.json()
                    prs = [
                        {
                            "id": p.get("id"),
                            "number": p.get("number"),
                            "title": p.get("title"),
                            "state": p.get("state"),
                            "user": p.get("user", {}).get("login"),
                            "created_at": p.get("created_at"),
                            "updated_at": p.get("updated_at"),
                            "html_url": p.get("html_url"),
                        }
                        for p in raw_prs
                    ]
                    return {
                        "provider": self.name,
                        "status": IntegrationStatus.CONNECTED.value,
                        "pull_requests": prs,
                    }
                return {
                    "provider": self.name,
                    "status": IntegrationStatus.ERROR.value,
                    "pull_requests": [],
                    "message": f"GitHub returned HTTP {res.status_code}",
                }
        except httpx.RequestError as exc:
            return {
                "provider": self.name,
                "status": IntegrationStatus.UNAVAILABLE.value,
                "pull_requests": [],
                "message": str(exc),
            }
