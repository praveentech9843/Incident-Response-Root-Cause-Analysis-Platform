from datetime import timedelta
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import Role, create_access_token
from app.core.test_safety import assert_safe_test_environment
from app.main import app
from app.models.incident import Incident
from app.models.user import User


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    assert_safe_test_environment()
    session = SessionLocal()
    try:
        session.query(Incident).delete()
        session.query(User).delete()
        session.commit()
    finally:
        session.close()
    yield
    assert_safe_test_environment()
    session = SessionLocal()
    try:
        session.query(Incident).delete()
        session.query(User).delete()
        session.commit()
    finally:
        session.close()


def test_unauthenticated_access_strict_mode(client):
    """Verify unauthenticated requests with x-strict-auth are rejected with 401."""
    resp = client.get("/api/v1/auth/me", headers={"x-strict-auth": "true"})
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data["detail"]
    assert data["detail"]["error"]["code"] == "UNAUTHORIZED"


def test_invalid_and_expired_token_rejection(client):
    """Verify invalid or expired tokens are rejected."""
    # Invalid token string
    resp_invalid = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert resp_invalid.status_code == 401
    assert resp_invalid.json()["detail"]["error"]["code"] == "INVALID_TOKEN"

    # Expired token
    expired_token = create_access_token(
        user_id=999,
        username="expired_user",
        role="DEVELOPER",
        expires_delta=timedelta(seconds=-60),
    )
    resp_expired = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp_expired.status_code == 401
    assert resp_expired.json()["detail"]["error"]["code"] == "TOKEN_EXPIRED"


def test_inactive_user_rejection(client):
    """Verify inactive users are rejected."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "inactive_sam",
            "email": "sam@example.com",
            "password": "Password123!",
            "role": "DEVELOPER",
        },
    ).json()

    user_id = reg["user"]["id"]
    token = reg["access_token"]

    # Deactivate user directly in DB
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        user.is_active = False
        session.commit()
    finally:
        session.close()

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"]["code"] == "USER_INACTIVE"


def test_rbac_viewer_forbidden_from_modifications(client):
    """Verify VIEWER role is forbidden from modifying or resolving incidents."""
    # Register admin first
    client.post(
        "/api/v1/auth/register",
        json={"username": "super_admin", "email": "admin@example.com", "password": "Password123!"},
    )

    # Register viewer
    viewer_reg = client.post(
        "/api/v1/auth/register",
        json={"username": "viewer_tim", "email": "tim@example.com", "password": "Password123!", "role": "VIEWER"},
    ).json()

    viewer_token = viewer_reg["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # Attempt to resolve incident as VIEWER
    resp = client.post(
        "/api/v1/incidents/1/resolve",
        headers=viewer_headers,
        json={"resolved_by": "viewer_tim", "resolution_summary": "Attempt by viewer"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"]["code"] == "FORBIDDEN"


def test_identity_spoofing_prevention(client):
    """Verify server derives acting identity from token, preventing identity spoofing."""
    # Register admin first
    client.post(
        "/api/v1/auth/register",
        json={"username": "admin_real", "email": "admin@example.com", "password": "Password123!"},
    )

    # Register developer
    dev_reg = client.post(
        "/api/v1/auth/register",
        json={"username": "dev_john", "email": "john@example.com", "password": "Password123!", "role": "DEVELOPER"},
    ).json()

    dev_token = dev_reg["access_token"]
    dev_headers = {"Authorization": f"Bearer {dev_token}"}

    # Create an incident in DB
    session = SessionLocal()
    inc = Incident(
        incident_key="test-key-spoof",
        title="Test Incident",
        status="OPEN",
        correlation_reason="Test correlation",
    )
    session.add(inc)
    session.commit()
    session.refresh(inc)
    inc_id = inc.id
    session.close()

    # Developer attempts to add note claiming to be "admin_real"
    note_resp = client.post(
        f"/api/v1/incidents/{inc_id}/investigation/notes",
        headers=dev_headers,
        json={"author": "admin_real", "note": "Developer trying to spoof admin"},
    )
    assert note_resp.status_code == 200
    # Server derived author from authenticated user ("dev_john"), overriding payload!
    assert note_resp.json()["author"] == "dev_john"


def test_secret_leakage_prevention(client):
    """Verify health readiness does not leak database credentials or internal URLs."""
    resp = client.get("/health/ready")
    assert resp.status_code in (200, 503)
    text = resp.text
    assert "postgres" not in text.lower() or text == '{"status":"ready","database":"connected","timestamp":' in text.replace(" ", "")
    assert "password" not in text.lower()
    assert "localhost:5432" not in text


def test_request_id_propagation(client):
    """Verify X-Request-ID is preserved if supplied and generated if missing."""
    # Custom request ID preserved
    custom_id = "test-req-trace-abc123"
    resp = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == custom_id

    # Generated request ID when omitted
    resp2 = client.get("/health")
    assert resp2.status_code == 200
    assert "X-Request-ID" in resp2.headers
    assert len(resp2.headers["X-Request-ID"]) > 10
