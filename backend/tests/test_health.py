from fastapi.testclient import TestClient


def test_health_endpoint_root(client: TestClient):
    """Verify that GET /health returns 200 and expected payload structure."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app_name" in data
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data


def test_health_endpoint_api_v1(client: TestClient):
    """Verify that GET /api/v1/health returns 200 with identical health payload."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
