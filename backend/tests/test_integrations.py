from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations import (
    get_all_integrations_status,
    get_deployment_provider,
    get_infrastructure_provider,
    get_metrics_provider,
    get_source_control_provider,
)
from app.integrations.base import IntegrationStatus
from app.integrations.deployment import GitHubActionsDeploymentProvider
from app.integrations.source_control import GitHubSourceControlProvider
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_unconfigured_integrations_return_not_connected():
    """Verify all integrations return explicit NOT_CONNECTED when credentials are unset."""
    status_dict = get_all_integrations_status()

    assert status_dict["deployment"]["status"] in (
        IntegrationStatus.NOT_CONNECTED.value,
        IntegrationStatus.UNAVAILABLE.value,
    )
    assert status_dict["source_control"]["status"] in (
        IntegrationStatus.NOT_CONNECTED.value,
        IntegrationStatus.UNAVAILABLE.value,
    )
    assert status_dict["infrastructure"]["status"] in (
        IntegrationStatus.NOT_CONNECTED.value,
        IntegrationStatus.UNAVAILABLE.value,
    )
    assert status_dict["metrics"]["status"] in (
        IntegrationStatus.NOT_CONNECTED.value,
        IntegrationStatus.UNAVAILABLE.value,
    )


def test_deployment_provider_mock_success():
    """Test deployment provider when real GitHub API returns successful runs."""
    provider = GitHubActionsDeploymentProvider()
    provider.enabled = True
    provider.token = "dummy-token"
    provider.repo = "owner/repo"

    mock_runs = {
        "workflow_runs": [
            {
                "id": 12345,
                "name": "Production Deploy",
                "status": "completed",
                "conclusion": "success",
                "created_at": "2026-10-07T10:00:00Z",
                "updated_at": "2026-10-07T10:05:00Z",
                "head_branch": "main",
                "head_sha": "abc123def456",
                "html_url": "https://github.com/owner/repo/actions/runs/12345",
            }
        ]
    }

    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_runs)
        res = provider.get_recent_deployments(limit=5)
        assert res["status"] == IntegrationStatus.CONNECTED.value
        assert len(res["deployments"]) == 1
        assert res["deployments"][0]["id"] == "12345"
        assert res["deployments"][0]["conclusion"] == "success"


def test_deployment_provider_timeout_handling():
    """Test deployment provider bounded timeout handling."""
    provider = GitHubActionsDeploymentProvider()
    provider.enabled = True
    provider.token = "dummy-token"
    provider.repo = "owner/repo"

    with patch("httpx.Client.get", side_effect=httpx.RequestError("Connection timeout")):
        res = provider.get_recent_deployments(limit=5)
        assert res["status"] == IntegrationStatus.UNAVAILABLE.value
        assert "Connection failure" in res["message"]
        assert len(res["deployments"]) == 0


def test_source_control_provider_mock_and_read_only():
    """Verify source control provider reads commits and has no mutation methods."""
    provider = GitHubSourceControlProvider()
    provider.enabled = True
    provider.token = "dummy-token"
    provider.repo = "owner/repo"

    mock_commits = [
        {
            "sha": "9876543210abcdef",
            "commit": {
                "author": {"name": "Developer Alex", "date": "2026-10-07T09:00:00Z"},
                "message": "fix: increase db connection pool size",
            },
            "html_url": "https://github.com/owner/repo/commit/9876543210abcdef",
        }
    ]

    with patch("httpx.Client.get") as mock_get:
        mock_get.return_value = httpx.Response(200, json=mock_commits)
        res = provider.get_recent_commits(limit=5)
        assert res["status"] == IntegrationStatus.CONNECTED.value
        assert len(res["commits"]) == 1
        assert res["commits"][0]["author"] == "Developer Alex"

    # Enforce Architectural Boundary: Provider has NO push, commit, or merge methods
    assert not hasattr(provider, "push_commit")
    assert not hasattr(provider, "create_pull_request")
    assert not hasattr(provider, "merge_pull_request")


def test_integrations_api_status_endpoint(client):
    """Test GET /api/v1/integrations/status returns explicit statuses without crashing."""
    resp = client.get("/api/v1/integrations/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "deployment" in data
    assert "source_control" in data
    assert "infrastructure" in data
    assert "metrics" in data
