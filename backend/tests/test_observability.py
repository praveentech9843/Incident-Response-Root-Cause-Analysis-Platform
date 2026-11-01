import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.test_safety import assert_safe_test_environment
from app.main import app
from app.models.job import BackgroundJob
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.job_service import complete_job, create_job, fail_job, start_job


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_jobs():
    assert_safe_test_environment()
    session = SessionLocal()
    try:
        session.query(BackgroundJob).delete()
        session.query(User).delete()
        session.commit()
    finally:
        session.close()
    yield
    assert_safe_test_environment()
    session = SessionLocal()
    try:
        session.query(BackgroundJob).delete()
        session.query(User).delete()
        session.commit()
    finally:
        session.close()


def test_health_liveness_and_readiness(client):
    """Test /health/live and /health/ready endpoints."""
    # Liveness
    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "alive"

    live_v1 = client.get("/api/v1/health/live")
    assert live_v1.status_code == 200
    assert live_v1.json()["status"] == "alive"

    # Readiness
    ready_resp = client.get("/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"
    assert ready_resp.json()["database"] == "connected"


def test_background_job_lifecycle(client):
    """Test creating, starting, and completing a background job."""
    session = SessionLocal()
    job = create_job(session, job_type="LOG_PARSING", payload={"log_id": 10})
    job_id = job.id
    assert job.status == "QUEUED"

    # Start job
    started = start_job(session, job_id)
    assert started.status == "RUNNING"
    assert started.started_at is not None

    # Complete job
    completed = complete_job(session, job_id, result={"events_parsed": 50})
    assert completed.status == "COMPLETED"
    assert completed.completed_at is not None
    session.close()

    # Query via API
    resp = client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == job_id
    assert data["status"] == "COMPLETED"
    assert data["job_type"] == "LOG_PARSING"


def test_background_job_failure_and_retry():
    """Test job retry on transient failure and final failed state."""
    session = SessionLocal()
    job = create_job(session, job_type="ALERT_DELIVERY", max_retries=1)
    job_id = job.id

    # First failure -> RETRYING
    f1 = fail_job(session, job_id, error="Transient network glitch")
    assert f1.status == "RETRYING"
    assert f1.retry_count == 1

    # Second failure -> FAILED
    f2 = fail_job(session, job_id, error="Permanent connection refusal")
    assert f2.status == "FAILED"
    assert f2.completed_at is not None
    session.close()


def test_audit_logs_recording_and_admin_query(client):
    """Test audit log creation and Admin query endpoint."""
    session = SessionLocal()
    log_audit_event(
        db=session,
        actor="lead_dev",
        action="INCIDENT_RESOLVE",
        target_entity="INCIDENT",
        target_id="101",
        request_id="req-obs-123",
        metadata={"resolution": "Fixed memory leak"},
    )
    session.close()

    # Register admin to query audit logs
    admin_reg = client.post(
        "/api/v1/auth/register",
        json={"username": "audit_admin", "email": "audit_admin@example.com", "password": "Password123!", "role": "ADMIN"},
    ).json()
    admin_headers = {"Authorization": f"Bearer {admin_reg['access_token']}"}

    resp = client.get("/api/v1/audit/logs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    actions = [l["action"] for l in data["logs"]]
    assert "INCIDENT_RESOLVE" in actions
