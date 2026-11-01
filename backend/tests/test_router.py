from fastapi.testclient import TestClient


def test_api_v1_router_mounted(client: TestClient):
    """Verify that the API router is correctly mounted at /api/v1."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_nonexistent_route_returns_404(client: TestClient):
    """Verify that a nonexistent route returns a structured 404 error response."""
    response = client.get("/api/v1/nonexistent-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == 404
