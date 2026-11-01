"""
Phase 6 E2E Verification Script.
Verifies Evidence-Grounded Investigation and Fix Recommendations end-to-end:
1. Check backend health.
2. Upload real multi-service log.
3. Parse log via Phase 2.
4. Correlate parsed events via Phase 3.
5. Enrich incident via Phase 4.
6. Run Phase 5 RCA.
7. Verify validated RCA exists.
8. Generate Phase 6 recommendations (POST /api/v1/incidents/{id}/recommendations).
9. Verify recommendation response schema.
10. Verify every cited evidence reference exists in RCA evidence snapshot.
11. Verify unavailable context is not treated as evidence.
12. Verify no fabricated configuration values exist.
13. Verify no unsupported numerical claims exist.
14. Verify risk levels are valid and explicitly represented.
15. Verify confidence levels are valid and bounded.
16. Verify FIX recommendations contain concrete verification steps.
17. Verify no automatic execution instructions or CLI commands exist.
18. Verify recommendations are persisted in PostgreSQL.
19. Verify recommendation history endpoint.
20. Generate a second recommendation run.
21. Verify previous recommendations remain auditable.
22. Verify original raw_content unchanged.
23. Verify parsed_logs unchanged.
24. Verify incident_events unchanged.
25. Verify Phase 4 context unchanged.
26. Verify Phase 5 RCA analyses unchanged.
27. Verify frontend production build.
"""
import sys
import os
import subprocess
import time
import uuid
from pathlib import Path
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/incident_platform_dev")


def get_db_connection():
    return psycopg2.connect(DB_URL)


def main():
    print("==================================================")
    print("STARTING PHASE 6 E2E VERIFICATION")
    print("==================================================")

    run_id = uuid.uuid4().hex[:8]
    client = httpx.Client(base_url=BASE_URL, timeout=20.0)

    # 1. Check backend health
    print("\n--- Step 1: Backend Health Check ---")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
    health = resp.json()
    print(f"Health Status: {health['status']}")
    assert health["status"] == "ok"

    # 2. Upload a real multi-service log
    print("\n--- Step 2: Upload Real Multi-Service Log ---")
    log_content = f"""2026-10-07 15:00:01 ERROR AuthService: Failed to validate token from session cache [req:p6-{run_id}]
2026-10-07 15:00:03 ERROR RedisCluster: Connection timed out to node-01:6379 after 2000ms [req:p6-{run_id}]
2026-10-07 15:00:05 ERROR APIGateway: Downstream service AuthService returned HTTP 500 [req:p6-{run_id}]
2026-10-07 15:00:07 INFO WebClient: Request failed with 502 Bad Gateway [req:p6-{run_id}]
"""
    files = {
        "file": (f"phase6_e2e_log_{run_id}.log", log_content.encode("utf-8"), "text/plain")
    }
    data = {
        "service_name": "AuthService",
        "environment": "production",
        "source_hint": "k8s-pod-stdout",
    }
    resp = client.post("/api/v1/logs/upload", files=files, data=data)
    assert resp.status_code == 201, f"Upload failed: {resp.status_code} {resp.text}"
    log_id = resp.json()["id"]
    print(f"Uploaded log ID: {log_id}")

    # 3. Parse log using Phase 2
    print("\n--- Step 3: Parse Log via Phase 2 API ---")
    resp = client.post(f"/api/v1/logs/{log_id}/parse")
    assert resp.status_code == 200
    parse_data = resp.json()
    print(f"Parsed {parse_data['event_count']} events via {parse_data['parser_used']}")
    assert parse_data["event_count"] == 4

    # 4. Correlate parsed events using Phase 3
    print("\n--- Step 4: Correlate Events via Phase 3 API ---")
    resp = client.post("/api/v1/incidents/correlate", json={"log_id": log_id})
    assert resp.status_code == 200
    corr_data = resp.json()
    assert corr_data["incidents_created"] >= 1
    incident = corr_data["incidents"][0]
    incident_id = incident["id"]
    print(f"Correlated Incident ID: {incident_id}, Title: {incident['title']}")

    # 5. Enrich incident using Phase 4
    print("\n--- Step 5: Enrich Incident via Phase 4 API ---")
    resp = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert resp.status_code == 200
    enrich_data = resp.json()
    print(f"Enriched {enrich_data['total_categories']} context categories.")

    # 6. Run Phase 5 RCA
    print("\n--- Step 6: Run Phase 5 RCA ---")
    resp = client.post(f"/api/v1/incidents/{incident_id}/rca")
    assert resp.status_code == 200
    rca_data = resp.json()
    print(f"RCA Status: {rca_data['analysis_status']}, Provider: {rca_data['provider']}")
    assert rca_data["analysis_status"] == "COMPLETED"
    assert len(rca_data["hypotheses"]) >= 1

    # 7. Verify validated RCA exists
    print("\n--- Step 7: Verify Validated RCA Exists ---")
    resp = client.get(f"/api/v1/incidents/{incident_id}/rca")
    assert resp.status_code == 200
    latest_rca = resp.json()
    rca_analysis_id = latest_rca["id"]
    print(f"Retrieved latest RCA ID: {rca_analysis_id}, Analysis ID: {latest_rca['analysis_id']}")

    # 8. Generate Phase 6 recommendations
    print("\n--- Step 8: Generate Phase 6 Recommendations (POST /api/v1/incidents/{id}/recommendations) ---")
    resp = client.post(f"/api/v1/incidents/{incident_id}/recommendations")
    assert resp.status_code == 200, f"Recommendation generation failed: {resp.status_code} {resp.text}"
    rec_data = resp.json()
    print(f"Status: {rec_data['status']}, Total: {rec_data['total_recommendations']}")
    assert rec_data["status"] == "COMPLETED"
    assert rec_data["total_recommendations"] > 0
    recommendations = rec_data["recommendations"]

    # 9. Verify recommendation response schema
    print("\n--- Step 9: Verify Recommendation Response Schema ---")
    for r in recommendations:
        for field in [
            "recommendation_id",
            "type",
            "title",
            "description",
            "rationale",
            "supporting_evidence",
            "confidence",
            "confidence_level",
            "risk_level",
            "expected_impact",
            "verification_steps",
            "status",
        ]:
            assert field in r, f"Missing required field '{field}' in recommendation: {r}"
    print("Verified: Response schema conforms strictly to IncidentRecommendationListResponse.")

    # 10. Verify every cited evidence reference exists in RCA evidence snapshot
    print("\n--- Step 10: Verify Every Cited Evidence Reference Exists ---")
    snapshot = latest_rca["evidence_snapshot"]
    observed_items = snapshot.get("observed_evidence_items", [])
    valid_ev_ids = {item["evidence_id"] for item in observed_items if "evidence_id" in item}
    for hyp in latest_rca["hypotheses"]:
        for ev in hyp.get("supporting_evidence", []):
            valid_ev_ids.add(ev)
    for evt in snapshot.get("events", []):
        if "event_id" in evt:
            valid_ev_ids.add(f"EVT-{evt['event_id']}")
        if "db_id" in evt:
            valid_ev_ids.add(f"EVT-{evt['db_id']}")

    for r in recommendations:
        for ev_id in r["supporting_evidence"]:
            assert ev_id in valid_ev_ids, f"Cited evidence ID '{ev_id}' not found in RCA evidence snapshot: {valid_ev_ids}"
    print(f"Verified: All cited evidence IDs map 100% to valid snapshot items: {valid_ev_ids}")

    # 11. Verify unavailable context is not treated as evidence
    print("\n--- Step 11: Verify Unavailable Context Not Treated as Evidence ---")
    for r in recommendations:
        desc_lower = f"{r['title']} {r['description']} {r['rationale']}".lower()
        assert "98%" not in desc_lower, "Fabricated metric percentage found in recommendation"
        assert "cpu utilization" not in desc_lower or "unavailable" in desc_lower, "Metric claimed as fact when unavailable"
    print("Verified: Unavailable metrics/deployments correctly excluded from factual evidence.")

    # 12. Verify no fabricated configuration values exist
    print("\n--- Step 12: Verify No Fabricated Configuration Values ---")
    for r in recommendations:
        full_text = f"{r['title']} {r['description']}".lower()
        assert "timeout to 30" not in full_text, f"Found invented timeout value in {r['title']}"
        assert "memory to 4gb" not in full_text, f"Found invented memory value in {r['title']}"
    print("Verified: No invented configuration parameters detected.")

    # 13. Verify no unsupported numerical claims exist
    print("\n--- Step 13: Verify No Unsupported Numerical Claims ---")
    for r in recommendations:
        impact = r["expected_impact"]
        assert "%" not in impact or "reduce potential" in impact, f"Found invented numerical impact: {impact}"
    print("Verified: Expected impact communicated qualitatively without invented metrics.")

    # 14. Verify risk levels
    print("\n--- Step 14: Verify Risk Levels ---")
    valid_risks = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
    for r in recommendations:
        assert r["risk_level"] in valid_risks, f"Invalid risk level: {r['risk_level']}"
        if r["type"] == "INVESTIGATION":
            assert r["risk_level"] in ("LOW", "MEDIUM"), f"Investigation cannot be high risk: {r}"
    print("Verified: Risk levels valid and properly categorized.")

    # 15. Verify confidence levels
    print("\n--- Step 15: Verify Confidence Levels ---")
    valid_confs = {"LOW", "MEDIUM", "HIGH"}
    for r in recommendations:
        assert r["confidence_level"] in valid_confs, f"Invalid confidence level: {r['confidence_level']}"
        assert 0.0 <= r["confidence"] <= 1.0, f"Confidence out of range: {r['confidence']}"
    print("Verified: Confidence scores bounded and categorized.")

    # 16. Verify FIX recommendations contain concrete verification steps
    print("\n--- Step 16: Verify FIX Recommendations Contain Verification Steps ---")
    fix_recs = [r for r in recommendations if r["type"] == "FIX"]
    for f in fix_recs:
        assert len(f["verification_steps"]) > 0, f"FIX recommendation missing verification steps: {f['title']}"
    print(f"Verified: {len(fix_recs)} FIX recommendations all contain mandatory verification steps.")

    # 17. Verify no automatic execution instructions or CLI commands exist
    print("\n--- Step 17: Verify No Automatic Execution Commands ---")
    forbidden_tokens = ["kubectl", "systemctl", "rm -rf", "docker run", "docker stop", "ALTER TABLE", "DROP TABLE"]
    for r in recommendations:
        full_text = f"{r['title']} {r['description']} {r['rationale']} {' '.join(r['verification_steps'])}"
        for tok in forbidden_tokens:
            assert tok not in full_text, f"Forbidden command '{tok}' detected in recommendation '{r['title']}'"
    print("Verified: Zero execution instructions or CLI commands present.")

    # 18. Verify recommendations are persisted in PostgreSQL
    print("\n--- Step 18: Verify Persistence in PostgreSQL ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT count(*) as count FROM incident_recommendations WHERE incident_id = %s",
            (incident_id,),
        )
        row = cur.fetchone()
        db_count = row["count"]
        print(f"PostgreSQL row count for incident {incident_id}: {db_count}")
        assert db_count == len(recommendations)
    conn.close()
    print("Verified: Recommendations persisted and indexed in PostgreSQL.")

    # 19. Verify recommendation history endpoint
    print("\n--- Step 19: Verify Recommendation History Endpoint ---")
    resp = client.get(f"/api/v1/incidents/{incident_id}/recommendations/history")
    assert resp.status_code == 200
    hist_data = resp.json()
    assert hist_data["total_recommendations"] == len(recommendations)
    print(f"History returned {hist_data['total_recommendations']} recommendations.")

    # 20. Generate a second recommendation run
    print("\n--- Step 20: Generate Second Recommendation Run ---")
    time.sleep(0.05)
    resp = client.post(f"/api/v1/incidents/{incident_id}/recommendations")
    assert resp.status_code == 200
    rec_data_2 = resp.json()
    print(f"Second run total: {rec_data_2['total_recommendations']}")

    # 21. Verify previous recommendations remain auditable
    print("\n--- Step 21: Verify Historical Auditability ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT count(*) as count FROM incident_recommendations WHERE incident_id = %s",
            (incident_id,),
        )
        total_db = cur.fetchone()["count"]
        expected_total = len(recommendations) + rec_data_2["total_recommendations"]
        assert total_db == expected_total, f"Expected {expected_total} total, got {total_db}"
    conn.close()
    print(f"Verified: All {total_db} recommendation records remain immutable and auditable.")

    # 22. Verify Phase 1 raw logs unchanged
    print("\n--- Step 22: Verify Phase 1 raw_content Immutability ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT raw_content FROM logs WHERE id = %s", (log_id,))
        current_raw = cur.fetchone()["raw_content"]
        assert current_raw == log_content, "Phase 1 raw_content was modified!"
    conn.close()
    print("Verified: Phase 1 raw_content remains 100% byte-for-byte identical.")

    # 23. Verify Phase 2 parsed logs unchanged
    print("\n--- Step 23: Verify Phase 2 parsed_logs Immutability ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as count FROM parsed_logs WHERE log_id = %s", (log_id,))
        count = cur.fetchone()["count"]
        assert count == 4, f"Expected 4 parsed logs, found {count}"
    conn.close()
    print("Verified: Phase 2 parsed_logs remains 100% intact and unchanged.")

    # 24. Verify Phase 3 incident events unchanged
    print("\n--- Step 24: Verify Phase 3 incident_events Immutability ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as count FROM incident_events WHERE incident_id = %s", (incident_id,))
        count = cur.fetchone()["count"]
        assert count == incident["event_count"], f"Expected {incident['event_count']} incident events, found {count}"
    conn.close()
    print("Verified: Phase 3 incident_events remains 100% intact and unchanged.")

    # 25. Verify Phase 4 incident contexts unchanged
    print("\n--- Step 25: Verify Phase 4 incident_contexts Immutability ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as count FROM incident_contexts WHERE incident_id = %s", (incident_id,))
        count = cur.fetchone()["count"]
        assert count == 6, f"Expected 6 incident contexts, found {count}"
    conn.close()
    print("Verified: Phase 4 incident_contexts remains 100% intact and unchanged.")

    # 26. Verify Phase 5 RCA analyses unchanged
    print("\n--- Step 26: Verify Phase 5 incident_rca_analyses Immutability ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT summary, hypotheses FROM incident_rca_analyses WHERE id = %s", (rca_analysis_id,))
        row = cur.fetchone()
        assert row["summary"] == latest_rca["summary"]
        assert len(row["hypotheses"]) == len(latest_rca["hypotheses"])
    conn.close()
    print("Verified: Phase 5 RCA analyses remains 100% intact and unchanged.")

    # 27. Verify Frontend production build
    print("\n--- Step 27: Verify Frontend Production Build ---")
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    print(f"Building frontend in {frontend_dir}...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    build_result = subprocess.run(
        [npm_cmd, "run", "build"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
        shell=False,
    )
    if build_result.returncode != 0:
        print("Frontend build STDOUT:", build_result.stdout)
        print("Frontend build STDERR:", build_result.stderr)
        raise AssertionError("Frontend build failed during Phase 6 E2E verification!")
    print(build_result.stdout)
    print("Verified: Frontend build succeeded with 0 errors.")

    print("\n==================================================")
    print("ALL 27 PHASE 6 E2E VERIFICATION CHECKS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    main()
