from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Verify that GET / returns 200 with application metadata and no sensitive data."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app_name" in data
    assert "version" in data
    assert "environment" in data
    assert "timestamp" in data
    # Verify no secrets or credentials exposed
    response_text = response.text.lower()
    assert "password" not in response_text
    assert "secret" not in response_text
    assert "neon.tech" not in response_text
    assert "postgresql://" not in response_text


def test_favicon_endpoint(client: TestClient):
    """Verify that GET /favicon.ico returns 204 No Content without logging 404."""
    response = client.get("/favicon.ico")
    assert response.status_code == 204


def test_docs_endpoints(client: TestClient):
    """Verify that API documentation is accessible at standard URLs."""
    # Swagger UI
    res_docs = client.get("/docs")
    assert res_docs.status_code == 200
    assert "swagger" in res_docs.text.lower() or "html" in res_docs.headers.get("content-type", "")

    # OpenAPI schema
    res_openapi = client.get("/openapi.json")
    assert res_openapi.status_code == 200
    schema = res_openapi.json()
    assert "openapi" in schema
    assert "paths" in schema
    assert "/" in schema["paths"]
    assert "/health" in schema["paths"]

    # ReDoc
    res_redoc = client.get("/redoc")
    assert res_redoc.status_code == 200


def test_legacy_docs_redirects(client: TestClient):
    """Verify that legacy /api/v1/docs prefixed routes redirect to standard URLs."""
    res_legacy_docs = client.get("/api/v1/docs", follow_redirects=False)
    assert res_legacy_docs.status_code == 307
    assert res_legacy_docs.headers["location"] == "/docs"

    res_legacy_openapi = client.get("/api/v1/openapi.json", follow_redirects=False)
    assert res_legacy_openapi.status_code == 307
    assert res_legacy_openapi.headers["location"] == "/openapi.json"

    res_legacy_redoc = client.get("/api/v1/redoc", follow_redirects=False)
    assert res_legacy_redoc.status_code == 307
    assert res_legacy_redoc.headers["location"] == "/redoc"


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
