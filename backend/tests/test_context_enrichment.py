import io
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.incident import Incident
from app.models.incident_context import IncidentContext
from app.models.incident_event import IncidentEvent
from app.models.log import Log
from app.models.parsed_log import ParsedLog


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure a clean database state before and after each test."""
    db = SessionLocal()
    try:
        db.query(IncidentContext).delete()
        db.query(IncidentEvent).delete()
        db.query(Incident).delete()
        db.query(ParsedLog).delete()
        db.query(Log).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(IncidentContext).delete()
        db.query(IncidentEvent).delete()
        db.query(Incident).delete()
        db.query(ParsedLog).delete()
        db.query(Log).delete()
        db.commit()
    finally:
        db.close()


def _create_sample_incident(client: TestClient) -> int:
    """Helper to upload a multi-service log, parse it, correlate it, and return the incident_id."""
    content = (
        "2026-10-06 12:00:01 ERROR InventoryService: Out of memory reserving inventory [req:tx-999]\n"
        "2026-10-06 12:00:04 ERROR Redis: Connection refused to redis-cluster:6379 [req:tx-999]\n"
        "2026-10-06 12:00:06 ERROR PaymentService: Upstream dependency failure on inventory [req:tx-999]\n"
    )
    upload_res = client.post(
        "/api/v1/logs/upload",
        files={"file": ("test_multi.log", io.BytesIO(content.encode("utf-8")), "text/plain")},
        data={"service_name": "InventoryService", "environment": "production"},
    )
    assert upload_res.status_code == 201
    log_id = upload_res.json()["id"]

    parse_res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert parse_res.status_code == 200

    corr_res = client.post("/api/v1/incidents/correlate", json={"log_id": log_id})
    assert corr_res.status_code == 200
    incidents = corr_res.json()["incidents"]
    assert len(incidents) >= 1
    return incidents[0]["id"]


# 1. Incident context creation
def test_incident_context_creation(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res.status_code == 200
    data = res.json()
    assert data["incident_id"] == incident_id
    assert data["total_categories"] == 6
    assert set(data["contexts"].keys()) == {
        "service",
        "deployment",
        "infrastructure",
        "metrics",
        "history",
        "dependencies",
    }


# 2. Service context derived correctly
def test_service_context_derived_correctly(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res.status_code == 200
    svc_ctx = res.json()["contexts"]["service"]
    assert svc_ctx["status"] == "AVAILABLE"
    assert "InventoryService" in svc_ctx["data"]["services_involved"]
    assert "PaymentService" in svc_ctx["data"]["services_involved"]
    assert "Redis" in svc_ctx["data"]["services_involved"]
    assert svc_ctx["data"]["owner"] is None
    assert svc_ctx["data"]["repository"] is None
    assert svc_ctx["data"]["field_availability"]["owner"] == "NOT_CONNECTED"
    assert svc_ctx["data"]["field_availability"]["repository"] == "NOT_CONNECTED"


# 3. History context derived correctly
def test_history_context_derived_correctly(client: TestClient):
    # Incident 1
    inc1_id = _create_sample_incident(client)
    client.post(f"/api/v1/incidents/{inc1_id}/enrich")

    # Incident 2 with overlapping service
    content_2 = "2026-10-06 12:30:01 ERROR InventoryService: Secondary cache failure [req:tx-888]\n"
    up2 = client.post(
        "/api/v1/logs/upload",
        files={"file": ("test_inc2.log", io.BytesIO(content_2.encode("utf-8")), "text/plain")},
    )
    assert up2.status_code == 201
    log2_id = up2.json()["id"]
    client.post(f"/api/v1/logs/{log2_id}/parse")
    corr2 = client.post("/api/v1/incidents/correlate", json={"log_id": log2_id})
    inc2_id = corr2.json()["incidents"][0]["id"]
    assert inc2_id != inc1_id

    # Enrich Incident 2
    res2 = client.post(f"/api/v1/incidents/{inc2_id}/enrich")
    assert res2.status_code == 200
    hist = res2.json()["contexts"]["history"]
    assert hist["status"] == "AVAILABLE"
    assert hist["data"]["previous_occurrence_count"] >= 1
    assert inc1_id in hist["data"]["previous_incident_ids"]
    assert hist["data"]["recurring"] is True


# 4. Dependency context derived correctly
def test_dependency_context_derived_correctly(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res.status_code == 200
    dep_ctx = res.json()["contexts"]["dependencies"]
    assert dep_ctx["status"] == "AVAILABLE"
    assert "InventoryService" in dep_ctx["data"]["services_involved"]
    assert "PaymentService" in dep_ctx["data"]["services_involved"]
    assert "Redis" in dep_ctx["data"]["services_involved"]
    assert dep_ctx["data"]["causal_graph"] is None
    assert dep_ctx["data"]["causality_status"] == "UNVERIFIED"
    assert "Correlation is NOT causation" in dep_ctx["data"]["correlation_vs_causation_notice"]


# 5. Deployment provider unavailable
def test_deployment_provider_unavailable(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res.status_code == 200
    dep = res.json()["contexts"]["deployment"]
    assert dep["status"] == "INTEGRATION_REQUIRED"
    assert dep["data"]["deployment_version"] is None
    assert dep["data"]["git_commit"] is None
    assert dep["data"]["connected"] is False


# 6. Infrastructure provider unavailable
def test_infrastructure_provider_unavailable(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res.status_code == 200
    infra = res.json()["contexts"]["infrastructure"]
    assert infra["status"] == "NOT_CONNECTED"
    assert infra["data"]["cluster"] is None
    assert infra["data"]["pods"] == []
    assert infra["data"]["connected"] is False


# 7. Metrics provider unavailable
def test_metrics_provider_unavailable(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res.status_code == 200
    met = res.json()["contexts"]["metrics"]
    assert met["status"] == "NOT_CONNECTED"
    assert met["data"]["cpu_usage"] is None
    assert met["data"]["memory_usage"] is None
    assert met["data"]["prometheus"] == "Not connected"
    assert met["data"]["datadog"] == "Not connected"


# 8. Missing incident returns 404
def test_missing_incident_returns_404(client: TestClient):
    res = client.post("/api/v1/incidents/999999/enrich")
    assert res.status_code == 404
    assert "not found" in res.json()["error"]["message"].lower()

    res_get = client.get("/api/v1/incidents/999999/context")
    assert res_get.status_code == 404

    res_cat = client.get("/api/v1/incidents/999999/context/service")
    assert res_cat.status_code == 404


# 9. Repeated enrichment is idempotent
def test_repeated_enrichment_is_idempotent(client: TestClient):
    incident_id = _create_sample_incident(client)

    # First enrichment
    res1 = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res1.status_code == 200

    db = SessionLocal()
    try:
        count_1 = db.query(IncidentContext).filter(IncidentContext.incident_id == incident_id).count()
        assert count_1 == 6
    finally:
        db.close()

    # Second enrichment
    res2 = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res2.status_code == 200

    # Third enrichment
    res3 = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert res3.status_code == 200

    db = SessionLocal()
    try:
        count_after = db.query(IncidentContext).filter(IncidentContext.incident_id == incident_id).count()
        assert count_after == 6, f"Expected exactly 6 rows after repeated enrichment, got {count_after}"
    finally:
        db.close()


# 10. Raw logs remain unchanged
def test_raw_logs_remain_unchanged(client: TestClient):
    raw_content = "2026-10-06 12:00:01 ERROR AuthSvc: Token expired [req:auth-1]\n"
    up = client.post(
        "/api/v1/logs/upload",
        files={"file": ("immut_raw.log", io.BytesIO(raw_content.encode("utf-8")), "text/plain")},
    )
    assert up.status_code == 201
    log_id = up.json()["id"]
    client.post(f"/api/v1/logs/{log_id}/parse")
    corr = client.post("/api/v1/incidents/correlate", json={"log_id": log_id})
    inc_id = corr.json()["incidents"][0]["id"]

    # Enrich
    client.post(f"/api/v1/incidents/{inc_id}/enrich")

    db = SessionLocal()
    try:
        log_row = db.query(Log).filter(Log.id == log_id).first()
        assert log_row.raw_content == raw_content
        assert log_row.content_hash == up.json()["content_hash"]
    finally:
        db.close()


# 11. Parsed logs remain unchanged
def test_parsed_logs_remain_unchanged(client: TestClient):
    raw_content = "2026-10-06 12:00:01 ERROR CartSvc: Checkout failed [req:cart-1]\n"
    up = client.post(
        "/api/v1/logs/upload",
        files={"file": ("immut_parsed.log", io.BytesIO(raw_content.encode("utf-8")), "text/plain")},
    )
    log_id = up.json()["id"]
    client.post(f"/api/v1/logs/{log_id}/parse")

    db = SessionLocal()
    try:
        parsed_before = [
            (p.id, p.message, p.level, p.service_name)
            for p in db.query(ParsedLog).filter(ParsedLog.log_id == log_id).all()
        ]
    finally:
        db.close()

    corr = client.post("/api/v1/incidents/correlate", json={"log_id": log_id})
    inc_id = corr.json()["incidents"][0]["id"]

    client.post(f"/api/v1/incidents/{inc_id}/enrich")

    db = SessionLocal()
    try:
        parsed_after = [
            (p.id, p.message, p.level, p.service_name)
            for p in db.query(ParsedLog).filter(ParsedLog.log_id == log_id).all()
        ]
        assert parsed_before == parsed_after
    finally:
        db.close()


# 12. Incident-event relationships remain unchanged
def test_incident_event_relationships_remain_unchanged(client: TestClient):
    incident_id = _create_sample_incident(client)

    db = SessionLocal()
    try:
        ie_before = [
            (ie.id, ie.parsed_log_id, ie.event_index)
            for ie in db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).all()
        ]
    finally:
        db.close()

    client.post(f"/api/v1/incidents/{incident_id}/enrich")

    db = SessionLocal()
    try:
        ie_after = [
            (ie.id, ie.parsed_log_id, ie.event_index)
            for ie in db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).all()
        ]
        assert ie_before == ie_after
    finally:
        db.close()


# 13. No fake metrics generated
def test_no_fake_metrics_generated(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.get(f"/api/v1/incidents/{incident_id}/context/metrics")
    assert res.status_code == 200
    data = res.json()["data"]
    # CPU usage, memory, etc. must not be fake synthetic numbers
    assert data["cpu_usage"] is None
    assert data["memory_usage"] is None
    assert data["network_usage"] is None
    assert data["request_rate"] is None
    assert data["latency"] is None


# 14. No fake deployment data generated
def test_no_fake_deployment_data_generated(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.get(f"/api/v1/incidents/{incident_id}/context/deployment")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["deployment_version"] is None
    assert data["git_commit"] is None
    assert data["build_number"] is None


# 15. No fake Kubernetes data generated
def test_no_fake_kubernetes_data_generated(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.get(f"/api/v1/incidents/{incident_id}/context/infrastructure")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["cluster"] is None
    assert data["namespace"] is None
    assert data["pods"] == []


# 16. Multiple context categories can coexist
def test_multiple_context_categories_coexist(client: TestClient):
    incident_id = _create_sample_incident(client)
    res = client.get(f"/api/v1/incidents/{incident_id}/context")
    assert res.status_code == 200
    contexts = res.json()["contexts"]
    assert len(contexts) == 6
    for cat in ["service", "deployment", "infrastructure", "metrics", "history", "dependencies"]:
        assert cat in contexts
        assert contexts[cat]["incident_id"] == incident_id


# 17. Context API returns correct structure
def test_context_api_returns_correct_structure(client: TestClient):
    incident_id = _create_sample_incident(client)

    # Test GET /context
    res_all = client.get(f"/api/v1/incidents/{incident_id}/context")
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert "incident_id" in all_data
    assert "incident_title" in all_data
    assert "total_categories" in all_data
    assert "contexts" in all_data
    assert "collected_at" in all_data

    # Test GET /context/{category} for each category
    for cat in ["service", "deployment", "infrastructure", "metrics", "history", "dependencies"]:
        res_cat = client.get(f"/api/v1/incidents/{incident_id}/context/{cat}")
        assert res_cat.status_code == 200
        cat_data = res_cat.json()
        assert cat_data["incident_id"] == incident_id
        assert cat_data["context_category"] == cat
        assert "status" in cat_data
        assert "data" in cat_data
        assert "source" in cat_data
        assert "collected_at" in cat_data
