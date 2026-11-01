"""
Phase 7 E2E Verification Script.
Verifies Developer Investigation & Resolution Workflow end-to-end:
1. Select an existing correlated incident (create via real log ingestion/parse/correlate/enrich/RCA/rec pipeline).
2. Retrieve RCA.
3. Retrieve recommendations.
4. Start investigation.
5. Assign developer.
6. Add investigation note.
7. Add investigation action.
8. Reference real evidence.
9. Review recommendation.
10. Create verification steps.
11. Complete verification.
12. Attempt invalid resolution first.
13. Confirm backend rejects invalid resolution.
14. Complete all required verification.
15. Resolve incident.
16. Verify incident status = RESOLVED.
17. Verify resolved_at exists.
18. Verify resolution summary exists.
19. Retrieve timeline.
20. Verify timeline contains actual actions.
21. Reopen incident.
22. Verify status returns to INVESTIGATING.
23. Verify resolved_at is cleared.
24. Verify immutable evidence is unchanged.
"""
import sys
import os
import uuid
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.test_safety import (
    assert_safe_test_environment,
    UnsafeTestDatabaseError,
    TEST_DATABASE_NAME,
    DEV_DATABASE_NAME,
)

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/incident_platform_test"),
)


def get_db_connection():
    assert_safe_test_environment(DB_URL)
    return psycopg2.connect(DB_URL)


def verify_target_backend_safety(client: httpx.Client, base_url: str) -> dict:
    """
    Ensure the target backend is demonstrably connected to the dedicated test database.
    Refuses execution if the backend is running in development or any non-test environment.
    """
    resp = client.get("/health")
    if resp.status_code != 200:
        raise UnsafeTestDatabaseError(
            f"SAFETY GUARD TRIGGERED: Health probe at '{base_url}' failed with status {resp.status_code}. "
            "Cannot verify backend environment. Refusing to execute E2E test."
        )
    health = resp.json()
    target_env = str(health.get("environment", "")).lower()
    if target_env != "test":
        raise UnsafeTestDatabaseError(
            f"SAFETY GUARD TRIGGERED: Target backend at '{base_url}' reported environment='{target_env}'. "
            f"It is NOT demonstrably running in 'test' environment connected to '{TEST_DATABASE_NAME}'. "
            f"Refusing to send mutating requests to avoid polluting development database '{DEV_DATABASE_NAME}'."
        )
    return health


def main():
    print("==================================================")
    print("STARTING PHASE 7 E2E VERIFICATION")
    print("==================================================")

    # Fail-fast safety guard 1: Verify direct DB connection URL is strictly test database
    assert_safe_test_environment(DB_URL)

    run_id = uuid.uuid4().hex[:8]
    client = httpx.Client(base_url=BASE_URL, timeout=20.0)

    # Fail-fast safety guard 2: Verify target backend is demonstrably running in test environment
    print("\n--- Setup: Backend Health Check & Safety Verification ---")
    health = verify_target_backend_safety(client, BASE_URL)
    print(f"Health Status: {health.get('status')} | Target Environment: {health.get('environment')}")
    assert health.get("status") == "ok"

    # Step 1: Ingest, Parse, Correlate real log to obtain correlated incident
    print("\n--- Step 1: Select Real Correlated Incident ---")
    log_content = f"""2026-10-07 16:00:01 ERROR AuthService: Connection pool exhausted [req:p7-{run_id}]
java.sql.SQLException: Connection pool exhausted, max 20 reached
\tat com.auth.DatabasePool.getConnection(DatabasePool.java:42)
2026-10-07 16:00:04 ERROR PaymentGateway: Downstream AuthService timeout [req:p7-{run_id}]
java.util.concurrent.TimeoutException: Timed out waiting for AuthService
\tat com.pay.ServiceClient.call(ServiceClient.java:88)
"""
    files = {
        "file": (f"phase7_e2e_log_{run_id}.log", log_content.encode("utf-8"), "text/plain")
    }
    data = {
        "service_name": "AuthService",
        "environment": "production",
        "source_hint": "k8s-pod-stdout",
    }
    resp = client.post("/api/v1/logs/upload", files=files, data=data)
    assert resp.status_code == 201, f"Upload failed: {resp.status_code} {resp.text}"
    log_id = resp.json()["id"]

    resp = client.post(f"/api/v1/logs/{log_id}/parse")
    assert resp.status_code == 200
    parse_data = resp.json()
    assert parse_data["event_count"] >= 2

    resp = client.post("/api/v1/incidents/correlate", json={"log_id": log_id})
    assert resp.status_code == 200
    corr_data = resp.json()
    assert corr_data["incidents_created"] >= 1
    incident = corr_data["incidents"][0]
    incident_id = incident["id"]
    print(f"Incident Created: ID={incident_id}, Title={incident['title']}, Status={incident['status']}")

    resp = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert resp.status_code == 200

    resp = client.post(f"/api/v1/incidents/{incident_id}/rca")
    assert resp.status_code == 200
    rca_post = resp.json()
    assert rca_post["analysis_status"] == "COMPLETED"

    resp = client.post(f"/api/v1/incidents/{incident_id}/recommendations")
    assert resp.status_code == 200
    rec_post = resp.json()
    assert len(rec_post["recommendations"]) >= 1

    # Snapshot immutable state in DB for Step 24 verification
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT raw_content, content_hash FROM logs WHERE id = %s", (log_id,))
            initial_raw_log = cur.fetchone()
            cur.execute("SELECT id, message, exception_type FROM parsed_logs WHERE log_id = %s ORDER BY id", (log_id,))
            initial_parsed_logs = cur.fetchall()
            cur.execute("SELECT id, parsed_log_id FROM incident_events WHERE incident_id = %s ORDER BY id", (incident_id,))
            initial_incident_events = cur.fetchall()
            cur.execute("SELECT id, context_category, data FROM incident_contexts WHERE incident_id = %s ORDER BY id", (incident_id,))
            initial_contexts = cur.fetchall()
            cur.execute("SELECT id, hypotheses, evidence_snapshot, limitations FROM incident_rca_analyses WHERE incident_id = %s ORDER BY id", (incident_id,))
            initial_rca = cur.fetchall()
            cur.execute("SELECT id, recommendation_id, title, rationale, supporting_evidence FROM incident_recommendations WHERE incident_id = %s ORDER BY id", (incident_id,))
            initial_recommendations = cur.fetchall()

    # Step 2: Retrieve RCA
    print("\n--- Step 2: Retrieve RCA ---")
    resp = client.get(f"/api/v1/incidents/{incident_id}/rca")
    assert resp.status_code == 200
    rca_data = resp.json()
    print(f"RCA retrieved: Summary='{rca_data['summary']}', Confidence={rca_data['confidence']}")
    assert rca_data["analysis_status"] == "COMPLETED"

    # Step 3: Retrieve recommendations
    print("\n--- Step 3: Retrieve Recommendations ---")
    resp = client.get(f"/api/v1/incidents/{incident_id}/recommendations")
    assert resp.status_code == 200
    recs_data = resp.json()
    recommendations = recs_data["recommendations"]
    print(f"Retrieved {len(recommendations)} recommendations.")
    assert len(recommendations) >= 1
    target_rec = recommendations[0]
    rec_id = target_rec["id"]
    rec_str_id = target_rec["recommendation_id"]

    # Step 4: Start investigation
    print("\n--- Step 4: Start Investigation ---")
    resp = client.post(
        f"/api/v1/incidents/{incident_id}/investigation",
        json={"assigned_to": "dev-praveen", "assigned_to_name": "Praveen", "investigation_summary": "Initial triage on pool saturation"},
    )
    assert resp.status_code == 200
    inv_data = resp.json()
    investigation_id = inv_data["id"]
    print(f"Investigation Started: ID={investigation_id}, Status={inv_data['status']}, AssignedTo={inv_data['assigned_to']}")
    assert inv_data["status"] in ("ASSIGNED", "INVESTIGATING")

    # Step 5: Assign developer and set status to INVESTIGATING
    print("\n--- Step 5: Assign Developer ---")
    resp = client.patch(
        f"/api/v1/incidents/{incident_id}/investigation",
        json={"assigned_to": "dev-sarah", "assigned_to_name": "Sarah Chen", "status": "INVESTIGATING"},
    )
    assert resp.status_code == 200
    inv_updated = resp.json()
    print(f"Reassigned to: {inv_updated['assigned_to']} ({inv_updated['assigned_to_name']}), Status={inv_updated['status']}")
    assert inv_updated["assigned_to"] == "dev-sarah"
    assert inv_updated["assigned_to_name"] == "Sarah Chen"
    assert inv_updated["status"] == "INVESTIGATING"

    # Step 6: Add investigation note
    print("\n--- Step 6: Add Investigation Note ---")
    resp = client.post(
        f"/api/v1/incidents/{incident_id}/investigation/notes",
        json={
            "author": "Sarah Chen",
            "note": "Checked logs around 16:00 UTC. PostgreSQL connection pool appears saturated.",
            "evidence_references": ["EVT-1", "EXC-1"],
        },
    )
    assert resp.status_code in (200, 201)
    note_data = resp.json()
    print(f"Note Added: ID={note_data['id']}, Author={note_data['author']}")
    assert note_data["note"].startswith("Checked logs")

    # Step 7: Add investigation action
    print("\n--- Step 7: Add Investigation Action ---")
    resp = client.post(
        f"/api/v1/incidents/{incident_id}/investigation/actions",
        json={
            "action_type": "DIAGNOSTIC_CHECK",
            "description": "Inspected RDS connection pool telemetry in monitoring dashboard.",
            "performed_by": "Sarah Chen",
            "result": "Active connections reached maximum limit of 20 at 16:00:01.",
            "evidence_references": ["EVT-1", "EXC-1", "ST-1"],
        },
    )
    assert resp.status_code in (200, 201)
    action_data = resp.json()
    print(f"Action Recorded: ID={action_data['id']}, Type={action_data['action_type']}")
    assert action_data["action_type"] == "DIAGNOSTIC_CHECK"

    # Step 8: Reference real evidence & reject hallucinated evidence
    print("\n--- Step 8: Evidence Reference Validation ---")
    fake_resp = client.post(
        f"/api/v1/incidents/{incident_id}/investigation/actions",
        json={
            "action_type": "OBSERVATION",
            "description": "Hallucinated reference test",
            "performed_by": "Sarah Chen",
            "result": "Tested observation with non-existent token",
            "evidence_references": ["EVT-HALLUCINATED-999"],
        },
    )
    assert fake_resp.status_code == 400
    print(f"Hallucinated evidence correctly rejected: {fake_resp.json()['detail']}")
    assert "Invalid evidence reference" in fake_resp.json()["detail"]

    # Step 9: Review recommendation
    print("\n--- Step 9: Review Recommendation ---")
    resp = client.post(
        f"/api/v1/incidents/{incident_id}/recommendations/{rec_id}/review",
        json={
            "reviewed_by": "Sarah Chen",
            "decision": "ACCEPTED",
            "reason": "RCA evidence supports database connection exhaustion hypothesis.",
        },
    )
    assert resp.status_code in (200, 201)
    review_data = resp.json()
    print(f"Recommendation Review Recorded: Decision={review_data['decision']}, By={review_data['reviewed_by']}")
    assert review_data["decision"] == "ACCEPTED"

    # Step 10: Create verification steps
    print("\n--- Step 10: Create Verification Steps ---")
    vstep1_resp = client.post(
        f"/api/v1/incidents/{incident_id}/verification",
        json={
            "title": "Confirm active connection pool count is below 50%",
            "description": "Query RDS telemetry to ensure connection saturation has subsided",
            "is_required": True,
            "evidence_references": ["EVT-1"],
        },
    )
    assert vstep1_resp.status_code in (200, 201)
    vstep1 = vstep1_resp.json()

    vstep2_resp = client.post(
        f"/api/v1/incidents/{incident_id}/verification",
        json={
            "title": "Confirm downstream error rate dropped to 0%",
            "description": "Check PaymentGateway HTTP 500 error metric",
            "is_required": True,
        },
    )
    assert vstep2_resp.status_code in (200, 201)
    vstep2 = vstep2_resp.json()
    print(f"Created Verification Steps: Step 1 (ID={vstep1['id']}), Step 2 (ID={vstep2['id']})")

    # Step 11: Partially complete verification (one PASSED, one PENDING)
    print("\n--- Step 11: Partially Complete Verification ---")
    patch1 = client.patch(
        f"/api/v1/incidents/{incident_id}/verification/{vstep1['id']}",
        json={
            "status": "PASSED",
            "result": "Active connections measured at 6 out of 100",
            "verified_by": "Sarah Chen",
        },
    )
    assert patch1.status_code == 200
    assert patch1.json()["status"] == "PASSED"
    print(f"Step 1 verified: {patch1.json()['status']}")

    # Step 12: Attempt invalid resolution first (with pending step 2)
    print("\n--- Step 12: Attempt Invalid Resolution (Pending Step) ---")
    inv_res = client.post(
        f"/api/v1/incidents/{incident_id}/resolve",
        json={
            "resolved_by": "Sarah Chen",
            "resolution_summary": "Premature attempt to resolve while step 2 is pending",
            "root_cause_confirmed": "CONFIRMED",
        },
    )

    # Step 13: Confirm backend rejects invalid resolution
    print("\n--- Step 13: Confirm Backend Rejection ---")
    assert inv_res.status_code == 400
    err_msg = inv_res.json()["detail"]
    print(f"Backend successfully rejected premature resolution: {err_msg}")
    assert "still pending" in err_msg

    # Step 14: Complete all required verification
    print("\n--- Step 14: Complete All Required Verification ---")
    patch2 = client.patch(
        f"/api/v1/incidents/{incident_id}/verification/{vstep2['id']}",
        json={
            "status": "PASSED",
            "result": "Zero HTTP 500 errors recorded in last 15 minutes",
            "verified_by": "Sarah Chen",
        },
    )
    assert patch2.status_code == 200
    assert patch2.json()["status"] == "PASSED"
    print(f"Step 2 verified: {patch2.json()['status']}")

    # Step 15: Resolve incident
    print("\n--- Step 15: Resolve Incident ---")
    resolve_resp = client.post(
        f"/api/v1/incidents/{incident_id}/resolve",
        json={
            "resolved_by": "Sarah Chen",
            "resolution_summary": "AuthService DB connection pool scaled from 20 to 100. Connection saturation resolved and verified.",
            "root_cause_confirmed": "CONFIRMED",
        },
    )
    assert resolve_resp.status_code == 200
    resolve_data = resolve_resp.json()

    # Step 16: Verify incident status = RESOLVED
    print("\n--- Step 16: Verify Status = RESOLVED ---")
    print(f"Resolve Response Status: {resolve_data['status']}")
    assert resolve_data["status"] == "RESOLVED"
    assert resolve_data["investigation_status"] == "RESOLVED"

    detail_resp = client.get(f"/api/v1/incidents/{incident_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["status"] == "RESOLVED"

    # Step 17: Verify resolved_at exists
    print("\n--- Step 17: Verify resolved_at Populated ---")
    print(f"resolved_at: {detail_data['resolved_at']}")
    assert detail_data["resolved_at"] is not None

    # Step 18: Verify resolution summary exists
    print("\n--- Step 18: Verify Resolution Summary Populated ---")
    print(f"resolution_summary: {detail_data['resolution_summary']}")
    assert detail_data["resolution_summary"] == "AuthService DB connection pool scaled from 20 to 100. Connection saturation resolved and verified."
    assert detail_data["resolved_by"] == "Sarah Chen"
    assert detail_data["root_cause_confirmed"] == "CONFIRMED"

    # Step 19: Retrieve timeline
    print("\n--- Step 19: Retrieve Timeline ---")
    timeline_resp = client.get(f"/api/v1/incidents/{incident_id}/timeline")
    assert timeline_resp.status_code == 200
    timeline_data = timeline_resp.json()
    events = timeline_data["events"]
    print(f"Timeline retrieved {len(events)} events.")
    assert len(events) >= 6

    # Step 20: Verify timeline contains actual actions
    print("\n--- Step 20: Verify Timeline Event Types ---")
    event_types = [e["event_type"] for e in events]
    print(f"Event Types: {event_types}")
    assert "INVESTIGATION_STARTED" in event_types
    assert "INCIDENT_ASSIGNED" in event_types
    assert "NOTE_ADDED" in event_types
    assert "ACTION_RECORDED" in event_types
    assert "RECOMMENDATION_REVIEWED" in event_types
    assert "VERIFICATION_CREATED" in event_types
    assert "VERIFICATION_UPDATED" in event_types
    assert "INCIDENT_RESOLVED" in event_types

    # Step 21: Reopen incident
    print("\n--- Step 21: Reopen Incident ---")
    reopen_resp = client.post(
        f"/api/v1/incidents/{incident_id}/reopen",
        json={
            "reopened_by": "Sarah Chen",
            "reason": "Connection spike reappeared during peak load window",
        },
    )
    assert reopen_resp.status_code == 200
    reopen_data = reopen_resp.json()

    # Step 22: Verify status returns to INVESTIGATING
    print("\n--- Step 22: Verify Reopened Status = INVESTIGATING ---")
    print(f"Reopened Incident Status: {reopen_data['status']}")
    assert reopen_data["status"] == "INVESTIGATING"

    reopened_detail = client.get(f"/api/v1/incidents/{incident_id}").json()
    assert reopened_detail["status"] == "INVESTIGATING"

    # Step 23: Verify resolved_at is cleared
    print("\n--- Step 23: Verify resolved_at Cleared ---")
    print(f"reopened_detail resolved_at: {reopened_detail.get('resolved_at')}")
    assert reopened_detail.get("resolved_at") is None

    # Step 24: Verify immutable evidence is unchanged
    print("\n--- Step 24: Verify Immutable Historical Evidence Unchanged ---")
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT raw_content, content_hash FROM logs WHERE id = %s", (log_id,))
            current_raw_log = cur.fetchone()
            assert current_raw_log["raw_content"] == initial_raw_log["raw_content"]
            assert current_raw_log["content_hash"] == initial_raw_log["content_hash"]

            cur.execute("SELECT id, message, exception_type FROM parsed_logs WHERE log_id = %s ORDER BY id", (log_id,))
            current_parsed_logs = cur.fetchall()
            assert len(current_parsed_logs) == len(initial_parsed_logs)
            for i, pl in enumerate(current_parsed_logs):
                assert pl["id"] == initial_parsed_logs[i]["id"]
                assert pl["message"] == initial_parsed_logs[i]["message"]
                assert pl["exception_type"] == initial_parsed_logs[i]["exception_type"]

            cur.execute("SELECT id, parsed_log_id FROM incident_events WHERE incident_id = %s ORDER BY id", (incident_id,))
            current_incident_events = cur.fetchall()
            assert current_incident_events == initial_incident_events

            cur.execute("SELECT id, context_category, data FROM incident_contexts WHERE incident_id = %s ORDER BY id", (incident_id,))
            current_contexts = cur.fetchall()
            assert current_contexts == initial_contexts

            cur.execute("SELECT id, hypotheses, evidence_snapshot, limitations FROM incident_rca_analyses WHERE incident_id = %s ORDER BY id", (incident_id,))
            current_rca = cur.fetchall()
            assert current_rca == initial_rca

            cur.execute("SELECT id, recommendation_id, title, rationale, supporting_evidence FROM incident_recommendations WHERE incident_id = %s ORDER BY id", (incident_id,))
            current_recommendations = cur.fetchall()
            assert current_recommendations == initial_recommendations

    print("Immutability verified: Raw logs, parsed logs, incident events, contexts, RCA snapshot, and recommendations remain untouched.")

    print("\n==================================================")
    print("PHASE 7 E2E VERIFICATION COMPLETED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    main()
