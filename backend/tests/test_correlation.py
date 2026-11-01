import io
import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.log import Log
from app.models.parsed_log import ParsedLog


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure a clean database state before and after each test."""
    db = SessionLocal()
    try:
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
        db.query(IncidentEvent).delete()
        db.query(Incident).delete()
        db.query(ParsedLog).delete()
        db.query(Log).delete()
        db.commit()
    finally:
        db.close()


def _upload_and_parse(client: TestClient, filename: str, content: str, service_name: str = None) -> int:
    """Helper to upload a raw log and parse it, returning the log_id."""
    data = {}
    if service_name:
        data["service_name"] = service_name
    upload_res = client.post(
        "/api/v1/logs/upload",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")},
        data=data,
    )
    assert upload_res.status_code == 201
    log_id = upload_res.json()["id"]

    parse_res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert parse_res.status_code == 200
    return log_id


# 1. Single error event becomes an incident when eligible
def test_single_error_event_creates_incident(client: TestClient):
    content = "2026-10-06 12:00:01 ERROR InventoryService: Out of memory exception\n"
    log_id = _upload_and_parse(client, "single_error.log", content)

    res = client.post("/api/v1/incidents/correlate")
    assert res.status_code == 200
    data = res.json()
    assert data["events_considered"] == 1
    assert data["incidents_created"] == 1
    assert len(data["incidents"]) == 1
    inc = data["incidents"][0]
    assert inc["event_count"] == 1
    assert inc["service_count"] == 1
    assert "InventoryService" in inc["title"]


# 2. Multiple temporally related events correlate
def test_multiple_temporally_related_events_correlate(client: TestClient):
    content = (
        "2026-10-06 12:00:01 ERROR InventoryService: DB timeout\n"
        "2026-10-06 12:00:04 ERROR Redis: Connection refused\n"
        "2026-10-06 12:00:08 ERROR PaymentService: Upstream failure\n"
    )
    _upload_and_parse(client, "temporal_cluster.log", content)

    res = client.post("/api/v1/incidents/correlate")
    assert res.status_code == 200
    data = res.json()
    assert data["incidents_created"] == 1
    inc = data["incidents"][0]
    assert inc["event_count"] == 3
    assert inc["service_count"] == 3
    assert "InventoryService" in inc["title"]
    assert "Redis" in inc["title"]
    assert "PaymentService" in inc["title"]


# 3. Events outside correlation window do not correlate
def test_events_outside_window_do_not_correlate(client: TestClient):
    # Default window is 30 seconds. These events are 10 minutes (600s) apart.
    content = (
        "2026-10-06 12:00:01 ERROR ServiceA: Database locked\n"
        "2026-10-06 12:10:01 ERROR ServiceB: Timeout waiting for response\n"
    )
    _upload_and_parse(client, "outside_window.log", content)

    res = client.post("/api/v1/incidents/correlate")
    assert res.status_code == 200
    data = res.json()
    assert data["incidents_created"] == 2
    assert len(data["incidents"]) == 2
    assert data["incidents"][0]["event_count"] == 1
    assert data["incidents"][1]["event_count"] == 1


# 4. Multiple independent incidents remain separate
def test_multiple_independent_incidents_remain_separate(client: TestClient):
    content = (
        "2026-10-06 12:00:01 ERROR ServiceA: Failure in cluster 1\n"
        "2026-10-06 12:00:03 ERROR ServiceB: Cascading failure in cluster 1\n"
        "2026-10-06 12:45:00 ERROR ServiceC: Network partition in cluster 2\n"
        "2026-10-06 12:45:05 ERROR ServiceD: Host unreachable in cluster 2\n"
    )
    _upload_and_parse(client, "multi_incidents.log", content)

    res = client.post("/api/v1/incidents/correlate")
    assert res.status_code == 200
    data = res.json()
    assert data["incidents_created"] == 2
    assert data["incidents"][0]["event_count"] == 2
    assert data["incidents"][1]["event_count"] == 2


# 5. Shared correlation ID strongly correlates events
def test_shared_correlation_id_strongly_correlates(client: TestClient):
    content = (
        "2026-10-06 12:00:01 ERROR OrderService: Failed order [req:req-9821]\n"
        "2026-10-06 12:05:00 ERROR PaymentService: Gateway rejected [req:req-9821]\n"
    )
    _upload_and_parse(client, "corr_id.log", content)

    res = client.post("/api/v1/incidents/correlate")
    assert res.status_code == 200
    data = res.json()
    assert data["incidents_created"] == 1
    inc = data["incidents"][0]
    assert inc["event_count"] == 2
    assert "req-9821" in inc["correlation_reason"]
    assert inc["correlation_confidence"] == 0.95


# 6. Different correlation IDs remain separate
def test_different_correlation_ids_remain_separate(client: TestClient):
    # Both events are far apart in time and have distinct correlation IDs
    content = (
        "2026-10-06 12:00:01 ERROR ServiceA: Order err [req:order-111]\n"
        "2026-10-06 12:30:00 ERROR ServiceB: Auth err [req:auth-222]\n"
    )
    _upload_and_parse(client, "diff_corr.log", content)

    res = client.post("/api/v1/incidents/correlate")
    data = res.json()
    assert data["incidents_created"] == 2


# 7. INFO-only events do not create arbitrary incidents
def test_info_only_events_do_not_create_incidents(client: TestClient):
    content = (
        "2026-10-06 12:00:01 INFO AuthService: User logged in successfully\n"
        "2026-10-06 12:00:03 INFO OrderService: Order #123 created\n"
        "2026-10-06 12:00:05 INFO BillingService: Invoice generated\n"
    )
    _upload_and_parse(client, "info_only.log", content)

    res = client.post("/api/v1/incidents/correlate")
    assert res.status_code == 200
    data = res.json()
    assert data["events_considered"] == 3
    assert data["incidents_created"] == 0
    assert len(data["incidents"]) == 0


# 8. INFO event correlated with an error is handled correctly
def test_info_event_correlated_with_error_included(client: TestClient):
    content = (
        "2026-10-06 12:00:01 INFO AuthService: Validating token [trace:trace-555]\n"
        "2026-10-06 12:00:02 ERROR AuthService: Signature verification failed [trace:trace-555]\n"
    )
    _upload_and_parse(client, "info_and_error.log", content)

    res = client.post("/api/v1/incidents/correlate")
    assert res.status_code == 200
    data = res.json()
    assert data["incidents_created"] == 1
    assert data["incidents"][0]["event_count"] == 2


# 9. Incident event ordering is deterministic (chronological)
def test_incident_event_ordering_deterministic(client: TestClient):
    # Provide events in reverse chronological order in log
    content = (
        "2026-10-06 12:00:10 ERROR Service3: Third error\n"
        "2026-10-06 12:00:01 ERROR Service1: First error\n"
        "2026-10-06 12:00:05 ERROR Service2: Second error\n"
    )
    _upload_and_parse(client, "reverse_events.log", content)

    corr_res = client.post("/api/v1/incidents/correlate")
    inc_id = corr_res.json()["incidents"][0]["id"]

    detail_res = client.get(f"/api/v1/incidents/{inc_id}")
    assert detail_res.status_code == 200
    events = detail_res.json()["events"]
    assert len(events) == 3
    assert events[0]["service_name"] == "Service1"
    assert events[1]["service_name"] == "Service2"
    assert events[2]["service_name"] == "Service3"


# 10. Incident-event relationship persists in PostgreSQL
def test_incident_event_relationship_persists(client: TestClient):
    content = (
        "2026-10-06 12:00:01 ERROR InventoryService: DB Error\n"
        "2026-10-06 12:00:04 ERROR OrderService: Upstream Error\n"
    )
    _upload_and_parse(client, "persist.log", content)

    client.post("/api/v1/incidents/correlate")

    db = SessionLocal()
    try:
        incidents = db.query(Incident).all()
        assert len(incidents) == 1
        inc = incidents[0]
        links = db.query(IncidentEvent).filter(IncidentEvent.incident_id == inc.id).all()
        assert len(links) == 2
        assert links[0].event_index == 0
        assert links[1].event_index == 1
    finally:
        db.close()


# 11 & 12. Incident deduplication works & repeated correlation does not create duplicates
def test_repeated_correlation_idempotent(client: TestClient):
    content = (
        "2026-10-06 12:00:01 ERROR ServiceA: Timeout\n"
        "2026-10-06 12:00:05 ERROR ServiceB: Connection closed\n"
    )
    _upload_and_parse(client, "dedup.log", content)

    # First run
    res1 = client.post("/api/v1/incidents/correlate")
    data1 = res1.json()
    assert data1["incidents_created"] == 1
    assert data1["incidents_existing"] == 0
    inc1_id = data1["incidents"][0]["id"]

    # Second run
    res2 = client.post("/api/v1/incidents/correlate")
    data2 = res2.json()
    assert data2["incidents_created"] == 0
    assert data2["incidents_existing"] == 1
    assert data2["incidents"][0]["id"] == inc1_id

    # Verify directly in PostgreSQL
    db = SessionLocal()
    try:
        count = db.query(Incident).count()
        assert count == 1
    finally:
        db.close()


# 13 & 14. Incident count and service count are correct
def test_incident_and_service_counts(client: TestClient):
    content = (
        "2026-10-06 12:00:01 ERROR Auth: Auth failure\n"
        "2026-10-06 12:00:02 ERROR Auth: Second auth failure\n"
        "2026-10-06 12:00:03 ERROR Gateway: Gateway 502\n"
    )
    _upload_and_parse(client, "counts.log", content)

    res = client.post("/api/v1/incidents/correlate")
    inc = res.json()["incidents"][0]
    assert inc["event_count"] == 3
    assert inc["service_count"] == 2


# 15 & 16. Correlation reason stored and confidence score deterministic
def test_correlation_reason_and_confidence(client: TestClient):
    content = (
        "2026-10-06 12:00:01 ERROR Svc1: Fail [run:run_123]\n"
        "2026-10-06 12:00:03 ERROR Svc2: Fail [run:run_123]\n"
    )
    _upload_and_parse(client, "reason.log", content)

    res = client.post("/api/v1/incidents/correlate")
    inc = res.json()["incidents"][0]
    assert "run_123" in inc["correlation_reason"]
    assert inc["correlation_confidence"] == 0.95


# 17 & 18. Foreign key constraints and cascade delete behavior
def test_cascade_delete_behavior(client: TestClient):
    content = "2026-10-06 12:00:01 ERROR ServiceA: Fail\n"
    log_id = _upload_and_parse(client, "cascade.log", content)

    client.post("/api/v1/incidents/correlate")

    db = SessionLocal()
    try:
        inc = db.query(Incident).first()
        assert inc is not None
        assert db.query(IncidentEvent).count() == 1

        # Delete incident directly -> incident_events should cascade delete
        db.delete(inc)
        db.commit()
        assert db.query(IncidentEvent).count() == 0

        # Raw log and parsed log should still exist
        assert db.query(Log).filter(Log.id == log_id).count() == 1
        assert db.query(ParsedLog).filter(ParsedLog.log_id == log_id).count() == 1
    finally:
        db.close()


# 21 & 22. Raw logs and parsed logs remain completely unchanged
def test_raw_logs_and_parsed_logs_remain_unchanged(client: TestClient):
    content = "2026-10-06 12:00:01 ERROR ServiceA: NullPointerException\n"
    log_id = _upload_and_parse(client, "immutability.log", content)

    db = SessionLocal()
    try:
        raw_before = db.query(Log).filter(Log.id == log_id).one().raw_content
        parsed_before = [
            (p.message, p.level, p.timestamp)
            for p in db.query(ParsedLog).filter(ParsedLog.log_id == log_id).all()
        ]
    finally:
        db.close()

    # Correlate
    client.post("/api/v1/incidents/correlate")

    db = SessionLocal()
    try:
        raw_after = db.query(Log).filter(Log.id == log_id).one().raw_content
        parsed_after = [
            (p.message, p.level, p.timestamp)
            for p in db.query(ParsedLog).filter(ParsedLog.log_id == log_id).all()
        ]
        assert raw_after == raw_before
        assert parsed_after == parsed_before
    finally:
        db.close()


# 23. API tests for POST /api/v1/incidents/correlate
def test_api_post_correlate_options(client: TestClient):
    content = "2026-10-06 12:00:01 ERROR ServiceA: Error A\n"
    log_id = _upload_and_parse(client, "api_test.log", content)

    # Test via JSON body with log_id filter
    payload = {"log_id": log_id, "time_window_seconds": 45}
    res = client.post("/api/v1/incidents/correlate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["incidents_created"] == 1


# 24. API tests for GET /api/v1/incidents
def test_api_get_incidents_list(client: TestClient):
    content = "2026-10-06 12:00:01 ERROR ServiceA: Error A\n"
    _upload_and_parse(client, "get_list.log", content)
    client.post("/api/v1/incidents/correlate")

    res = client.get("/api/v1/incidents?limit=10&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "OPEN"

    # Status filter check
    res_resolved = client.get("/api/v1/incidents?status=RESOLVED")
    assert res_resolved.status_code == 200
    assert res_resolved.json()["total"] == 0


# 25. API tests for GET /api/v1/incidents/{incident_id}
def test_api_get_incident_detail(client: TestClient):
    content = "2026-10-06 12:00:01 ERROR InventoryService: DB Error\n"
    _upload_and_parse(client, "detail.log", content)
    corr_res = client.post("/api/v1/incidents/correlate")
    inc_id = corr_res.json()["incidents"][0]["id"]

    res = client.get(f"/api/v1/incidents/{inc_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == inc_id
    assert len(detail["events"]) == 1
    assert detail["events"][0]["service_name"] == "InventoryService"

    # Nonexistent incident returns 404
    res_404 = client.get("/api/v1/incidents/999999")
    assert res_404.status_code == 404
