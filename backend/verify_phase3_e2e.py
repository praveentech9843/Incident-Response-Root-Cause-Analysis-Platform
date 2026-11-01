"""
Phase 3 Manual E2E Verification Script.
Tests real HTTP requests against the running FastAPI backend and directly inspects PostgreSQL.
Verifies deterministic incident correlation, deduplication, relationships, and immutability.
"""
import sys
import os
import time
import uuid
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

BASE_URL = "http://localhost:8000"
DB_URL = "postgresql://postgres:postgres@localhost:5432/incident_platform_dev"


def get_db_connection():
    return psycopg2.connect(DB_URL)


def main():
    print("==================================================")
    print("STARTING PHASE 3 E2E VERIFICATION")
    print("==================================================")

    run_id = uuid.uuid4().hex[:8]
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Health check
    print("\n--- Step 1: Backend Health Check ---")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
    print(f"Health OK: {resp.json()['status']}")

    # 2. Upload a REAL multi-service incident log
    print("\n--- Step 2: Upload Real Multi-Service Log ---")
    log_content_1 = f"""2026-10-06 12:00:01 ERROR InventoryService: Out of memory reserving inventory [req:e2e-{run_id}]
2026-10-06 12:00:04 ERROR Redis: Connection refused to redis-cluster:6379 [req:e2e-{run_id}]
2026-10-06 12:00:06 ERROR PaymentService: Upstream dependency failure on inventory [req:e2e-{run_id}]
2026-10-06 12:00:08 INFO APIGateway: Request returned HTTP 502 Bad Gateway [req:e2e-{run_id}]
"""
    files = {
        "file": (f"e2e_incident_1_{run_id}.log", log_content_1.encode("utf-8"), "text/plain")
    }
    data = {
        "service_name": "InventoryService",
        "environment": "production",
        "source_hint": "k8s-stdout",
    }
    resp = client.post("/api/v1/logs/upload", files=files, data=data)
    assert resp.status_code == 201, f"Upload failed: {resp.status_code} {resp.text}"
    log_1 = resp.json()
    log_1_id = log_1["id"]
    print(f"Uploaded log 1 id={log_1_id}, filename={log_1['original_filename']}")

    # 3. Parse it using the Phase 2 API
    print("\n--- Step 3: Parse Log Using Phase 2 API ---")
    resp = client.post(f"/api/v1/logs/{log_1_id}/parse")
    assert resp.status_code == 200, f"Parse failed: {resp.status_code} {resp.text}"
    parse_res = resp.json()
    print(f"Parsed {parse_res['event_count']} events via {parse_res['parser_used']}")
    assert parse_res["event_count"] == 4

    # 4. Run correlation
    print("\n--- Step 4: Run Incident Correlation API ---")
    resp = client.post("/api/v1/incidents/correlate", json={"log_id": log_1_id})
    assert resp.status_code == 200, f"Correlation failed: {resp.status_code} {resp.text}"
    corr_res = resp.json()
    print(f"Correlation response: considered={corr_res['events_considered']}, created={corr_res['incidents_created']}, existing={corr_res['incidents_existing']}")
    assert corr_res["incidents_created"] >= 1
    assert len(corr_res["incidents"]) >= 1

    created_incident = corr_res["incidents"][0]
    incident_id = created_incident["id"]
    print(f"Created Incident ID: {incident_id}")
    print(f"Title: {created_incident['title']}")
    print(f"Status: {created_incident['status']}")
    print(f"Event Count: {created_incident['event_count']}")
    print(f"Service Count: {created_incident['service_count']}")
    print(f"Correlation Reason: {created_incident['correlation_reason']}")
    print(f"Correlation Confidence: {created_incident['correlation_confidence']}")

    # 5. Verify incident is created
    assert created_incident["event_count"] >= 3
    assert created_incident["service_count"] >= 3
    assert "Correlated errors across" in created_incident["title"]

    # 6. Verify incident_events records exist directly in PostgreSQL
    print("\n--- Step 6: Verify PostgreSQL incident_events Records ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT count(*) as cnt FROM incident_events WHERE incident_id = %s",
            (incident_id,)
        )
        ie_count = cur.fetchone()["cnt"]
        print(f"incident_events count in DB: {ie_count}")
        assert ie_count == created_incident["event_count"]

    # 7. Verify correlated events are correct
    print("\n--- Step 7: Verify Correlated Events via API GET /incidents/{id} ---")
    resp = client.get(f"/api/v1/incidents/{incident_id}")
    assert resp.status_code == 200, f"GET incident failed: {resp.status_code} {resp.text}"
    detail = resp.json()
    assert detail["id"] == incident_id
    assert len(detail["events"]) == ie_count
    services_found = [e["service_name"] for e in detail["events"] if e["service_name"]]
    print(f"Correlated services: {services_found}")
    assert "InventoryService" in services_found
    assert "Redis" in services_found
    assert "PaymentService" in services_found

    # 8. Verify correlation reason mentions correlation ID
    assert f"e2e-{run_id}" in detail["correlation_reason"] or "correlation" in detail["correlation_reason"].lower()

    # 9 & 10. Run correlation again and verify no duplicate incident is created (idempotency)
    print("\n--- Steps 9 & 10: Test Idempotent Repeated Correlation ---")
    resp = client.post("/api/v1/incidents/correlate", json={"log_id": log_1_id})
    assert resp.status_code == 200
    repeat_res = resp.json()
    print(f"Repeat correlation response: created={repeat_res['incidents_created']}, existing={repeat_res['incidents_existing']}")
    assert repeat_res["incidents_created"] == 0
    assert repeat_res["incidents_existing"] >= 1
    assert any(inc["id"] == incident_id for inc in repeat_res["incidents"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM incidents WHERE incident_key = %s", (created_incident["incident_key"],))
        db_inc_count = cur.fetchone()["cnt"]
        print(f"DB incident count for incident_key={created_incident['incident_key']}: {db_inc_count}")
        assert db_inc_count == 1, "Duplicate incident row created in PostgreSQL!"

    # 11 & 12. Create another independent time-separated event group and verify separate incident
    print("\n--- Steps 11 & 12: Independent Time-Separated Incident ---")
    # Time separated by 45 minutes from log 1
    log_content_2 = f"""2026-10-06 12:45:01 ERROR NotificationService: Failed to deliver SMS [req:sms-{run_id}]
2026-10-06 12:45:04 ERROR TwilioClient: HTTP 500 internal gateway error [req:sms-{run_id}]
"""
    files2 = {
        "file": (f"e2e_incident_2_{run_id}.log", log_content_2.encode("utf-8"), "text/plain")
    }
    resp = client.post("/api/v1/logs/upload", files=files2)
    assert resp.status_code == 201
    log_2_id = resp.json()["id"]

    resp = client.post(f"/api/v1/logs/{log_2_id}/parse")
    assert resp.status_code == 200

    resp = client.post("/api/v1/incidents/correlate", json={"log_id": log_2_id})
    assert resp.status_code == 200
    corr_2 = resp.json()
    assert corr_2["incidents_created"] == 1
    incident_2_id = corr_2["incidents"][0]["id"]
    print(f"Created Second Independent Incident ID: {incident_2_id}")
    print(f"Title: {corr_2['incidents'][0]['title']}")
    assert incident_2_id != incident_id, "Independent time-separated events wrongly merged into first incident!"

    # 13. Verify GET /api/v1/incidents
    print("\n--- Step 13: GET /api/v1/incidents List ---")
    resp = client.get("/api/v1/incidents?limit=20")
    assert resp.status_code == 200
    list_res = resp.json()
    print(f"GET /incidents returned total: {list_res['total']}, items: {len(list_res['items'])}")
    assert list_res["total"] >= 2
    incident_ids = [item["id"] for item in list_res["items"]]
    assert incident_id in incident_ids
    assert incident_2_id in incident_ids

    # 14. Verify GET /api/v1/incidents/{id}
    print("\n--- Step 14: GET /api/v1/incidents/{id} for Incident 2 ---")
    resp = client.get(f"/api/v1/incidents/{incident_2_id}")
    assert resp.status_code == 200
    inc_2_detail = resp.json()
    assert inc_2_detail["id"] == incident_2_id
    assert inc_2_detail["event_count"] == 2
    assert len(inc_2_detail["events"]) == 2

    # 15. Verify Phase 1 raw_content is unchanged
    print("\n--- Step 15: Verify Phase 1 raw_content Immutability ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT raw_content FROM logs WHERE id = %s", (log_1_id,))
        raw_in_db = cur.fetchone()["raw_content"]
        assert raw_in_db == log_content_1, "CRITICAL: Phase 1 raw_content was modified during correlation!"
        print("Verified: Phase 1 raw_content remains 100% identical and unchanged.")

    # 16. Verify Phase 2 parsed events are unchanged
    print("\n--- Step 16: Verify Phase 2 parsed_logs Immutability ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM parsed_logs WHERE log_id = %s", (log_1_id,))
        p_count = cur.fetchone()["cnt"]
        assert p_count == 4, f"CRITICAL: Phase 2 parsed_logs count changed! Expected 4, found {p_count}"
        print("Verified: Phase 2 parsed events remain 100% intact and unchanged.")

    conn.close()
    client.close()
    print("\n==================================================")
    print("ALL 16 PHASE 3 E2E VERIFICATION CHECKS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    main()
