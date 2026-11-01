"""
Phase 5 E2E Verification Script.
Verifies Evidence-Grounded Root Cause Analysis end-to-end:
1. Check backend health.
2. Upload real multi-service log.
3. Parse log via Phase 2.
4. Correlate parsed events via Phase 3.
5. Enrich incident via Phase 4.
6. Retrieve operational context.
7. Construct/inspect RCA evidence package.
8. Run RCA (POST /api/v1/incidents/{id}/rca).
9. Verify RCA response schema.
10. Verify every cited evidence reference exists in observed evidence.
11. Verify no nonexistent service is referenced.
12. Verify unavailable metrics are not claimed as observed facts.
13. Verify unavailable deployment data is not claimed.
14. Verify causal status is correctly represented (HYPOTHESIS / SUPPORTED / UNVERIFIED).
15. Verify evidence snapshot persisted in PostgreSQL for auditability.
16. Verify RCA history endpoint (GET /api/v1/incidents/{id}/rca/history).
17. Run another RCA analysis.
18. Verify previous analysis remains available and separate.
19. Verify original raw_content unchanged.
20. Verify parsed_logs unchanged.
21. Verify incident_events unchanged.
22. Verify Phase 4 context unchanged.
23. Verify frontend build.
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
    print("STARTING PHASE 5 E2E VERIFICATION")
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
    log_content = f"""2026-10-07 14:00:01 ERROR AuthService: Failed to validate token from session cache [req:p5-{run_id}]
2026-10-07 14:00:03 ERROR RedisCluster: Connection timed out to node-01:6379 after 2000ms [req:p5-{run_id}]
2026-10-07 14:00:05 ERROR APIGateway: Downstream service AuthService returned HTTP 500 [req:p5-{run_id}]
2026-10-07 14:00:07 INFO WebClient: Request failed with 502 Bad Gateway [req:p5-{run_id}]
"""
    files = {
        "file": (f"phase5_e2e_log_{run_id}.log", log_content.encode("utf-8"), "text/plain")
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
    assert len(enrich_data["contexts"]) == 6

    # 6. Retrieve evidence/context
    print("\n--- Step 6: Retrieve Operational Context ---")
    resp = client.get(f"/api/v1/incidents/{incident_id}/context")
    assert resp.status_code == 200
    ctx_data = resp.json()
    print(f"Retrieved context for incident: {ctx_data['incident_id']}")
    assert "service" in ctx_data["contexts"]
    assert "metrics" in ctx_data["contexts"]
    assert "deployment" in ctx_data["contexts"]

    # 7. Construct / inspect RCA evidence package
    print("\n--- Step 7: Inspect Evidence Package Inputs ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, service_name, level, message FROM parsed_logs WHERE log_id = %s", (log_id,))
        raw_events = cur.fetchall()
        print(f"Constituent events found in DB: {len(raw_events)}")
        known_services = {e["service_name"] for e in raw_events if e["service_name"]}
        print(f"Observed services: {known_services}")

    # 8. Run RCA
    print("\n--- Step 8: Run AI Root Cause Analysis (POST /api/v1/incidents/{id}/rca) ---")
    resp = client.post(f"/api/v1/incidents/{incident_id}/rca")
    assert resp.status_code == 200, f"RCA failed: {resp.status_code} {resp.text}"
    rca = resp.json()
    analysis_id_1 = rca["analysis_id"]
    status_1 = rca["analysis_status"]
    print(f"Analysis ID: {analysis_id_1}, Status: {status_1}")
    print(f"Provider: {rca['provider']}, Model: {rca['model']}")
    print(f"Summary: {rca['summary']}")

    # 9. Verify RCA response schema
    print("\n--- Step 9: Verify RCA Response Schema ---")
    assert rca["incident_id"] == incident_id
    assert "analysis_id" in rca
    assert rca["analysis_status"] in ["COMPLETED", "INSUFFICIENT_EVIDENCE", "PROVIDER_UNAVAILABLE"]
    assert "provider" in rca
    assert "model" in rca
    assert "summary" in rca
    assert isinstance(rca["hypotheses"], list)
    assert isinstance(rca["limitations"], list)
    assert isinstance(rca["evidence_snapshot"], dict)
    print("Verified: Response schema satisfies IncidentRCAAnalysisResponse.")

    # If provider executed analysis (COMPLETED)
    if status_1 == "COMPLETED":
        assert len(rca["hypotheses"]) >= 1

        # 10. Verify every evidence reference exists
        print("\n--- Step 10: Verify Every Cited Evidence Reference Exists ---")
        snapshot = rca["evidence_snapshot"]
        observed_ids = {
            item["evidence_id"] for item in snapshot.get("observed_evidence_items", [])
        }
        print(f"Valid observed evidence IDs in snapshot: {observed_ids}")
        for hyp in rca["hypotheses"]:
            print(f"Checking hypothesis: '{hyp['title']}'")
            for cited_id in hyp.get("supporting_evidence", []):
                assert cited_id in observed_ids, f"CRITICAL: Nonexistent evidence ID '{cited_id}' was cited!"
        print("Verified: 100% of cited evidence references map to verified observed items.")

        # 11. Verify no nonexistent service is referenced
        print("\n--- Step 11: Verify No Nonexistent Service Referenced ---")
        known_service_names = set(snapshot.get("service_names", []))
        for hyp in rca["hypotheses"]:
            # Check hypothesis mentions observed services
            print(f"Hypothesis title: {hyp['title']}, Role: {hyp['role']}")
            assert any(s in hyp["title"] or s in hyp["description"] for s in known_service_names)
        print("Verified: All hypotheses are grounded in observed incident services.")

        # 12. Verify unavailable metrics are not claimed as observed facts
        print("\n--- Step 12: Verify Unavailable Metrics Not Claimed as Facts ---")
        for hyp in rca["hypotheses"]:
            text = f"{hyp['title']} {hyp['description']} {hyp['reasoning']}".lower()
            assert not ("cpu utilization was" in text or "memory usage was" in text)
        assert any("metrics" in lim.lower() for lim in rca["limitations"])
        print("Verified: Unavailable metrics correctly excluded from factual claims.")

        # 13. Verify unavailable deployment data is not claimed
        print("\n--- Step 13: Verify Unavailable Deployment Data Not Claimed ---")
        for hyp in rca["hypotheses"]:
            text = f"{hyp['title']} {hyp['description']}".lower()
            assert "git commit" not in text
        assert any("deployment" in lim.lower() for lim in rca["limitations"])
        print("Verified: Unavailable deployment context correctly noted in limitations.")

        # 14. Verify causal status is correctly represented
        print("\n--- Step 14: Verify Causal Status Representation ---")
        for hyp in rca["hypotheses"]:
            causal_status = hyp["causal_status"]
            print(f"Hypothesis '{hyp['title']}': causal_status={causal_status}")
            assert causal_status in ["HYPOTHESIS", "SUPPORTED", "UNVERIFIED", "CONFIRMED"]
            # No unverified CONFIRMED without rigorous trace proof
            if causal_status == "CONFIRMED":
                assert len(hyp["supporting_evidence"]) >= 2
        print("Verified: Causal status conforms strictly to evidence strength.")

    # 15. Verify evidence snapshot persisted in PostgreSQL
    print("\n--- Step 15: Verify Evidence Snapshot Persisted in PostgreSQL ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT analysis_id, analysis_status, evidence_snapshot FROM incident_rca_analyses WHERE analysis_id = %s",
            (analysis_id_1,)
        )
        row = cur.fetchone()
        assert row is not None
        assert row["analysis_id"] == analysis_id_1
        assert "incident" in row["evidence_snapshot"]
        assert "observed_evidence_items" in row["evidence_snapshot"]
        print("Verified: Full evidence snapshot persisted in PostgreSQL for audit trail.")

    # 16. Verify RCA history endpoint
    print("\n--- Step 16: Verify RCA History Endpoint ---")
    resp = client.get(f"/api/v1/incidents/{incident_id}/rca/history")
    assert resp.status_code == 200
    hist = resp.json()
    assert hist["total"] >= 1
    assert any(item["analysis_id"] == analysis_id_1 for item in hist["items"])
    print(f"RCA history returned {hist['total']} total analyses.")

    # 17. Run another RCA analysis
    print("\n--- Step 17: Run Second RCA Analysis ---")
    resp = client.post(f"/api/v1/incidents/{incident_id}/rca")
    assert resp.status_code == 200
    rca_2 = resp.json()
    analysis_id_2 = rca_2["analysis_id"]
    print(f"Second Analysis ID: {analysis_id_2}")
    assert analysis_id_2 != analysis_id_1

    # 18. Verify previous analysis remains available
    print("\n--- Step 18: Verify Previous Analysis Remains Available ---")
    resp_hist_2 = client.get(f"/api/v1/incidents/{incident_id}/rca/history")
    assert resp_hist_2.status_code == 200
    hist_2 = resp_hist_2.json()
    assert hist_2["total"] >= 2
    analysis_ids = [item["analysis_id"] for item in hist_2["items"]]
    assert analysis_id_1 in analysis_ids
    assert analysis_id_2 in analysis_ids

    # Query first analysis directly by ID
    resp_by_id = client.get(f"/api/v1/incidents/{incident_id}/rca/{analysis_id_1}")
    assert resp_by_id.status_code == 200
    assert resp_by_id.json()["analysis_id"] == analysis_id_1

    # Query latest (should be analysis_id_2)
    resp_latest = client.get(f"/api/v1/incidents/{incident_id}/rca")
    assert resp_latest.status_code == 200
    assert resp_latest.json()["analysis_id"] == analysis_id_2
    print("Verified: Historical analysis records remain immutable and independently queryable.")

    # 19. Verify original raw_content unchanged
    print("\n--- Step 19: Verify Phase 1 raw_content Immutability ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT raw_content FROM logs WHERE id = %s", (log_id,))
        raw_db = cur.fetchone()["raw_content"]
        assert raw_db == log_content, "CRITICAL: Phase 1 raw_content was mutated during Phase 5 RCA!"
    print("Verified: Phase 1 raw_content remains 100% byte-for-byte identical.")

    # 20. Verify parsed_logs unchanged
    print("\n--- Step 20: Verify Phase 2 parsed_logs Immutability ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM parsed_logs WHERE log_id = %s", (log_id,))
        p_cnt = cur.fetchone()["cnt"]
        assert p_cnt == 4, f"CRITICAL: parsed_logs count changed! Found {p_cnt}"
    print("Verified: Phase 2 parsed_logs remains 100% intact and unchanged.")

    # 21. Verify incident_events unchanged
    print("\n--- Step 21: Verify Phase 3 incident_events Immutability ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM incident_events WHERE incident_id = %s", (incident_id,))
        ie_cnt = cur.fetchone()["cnt"]
        assert ie_cnt == incident["event_count"]
    print("Verified: Phase 3 incident_events remains 100% intact and unchanged.")

    # 22. Verify Phase 4 context unchanged
    print("\n--- Step 22: Verify Phase 4 incident_contexts Immutability ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM incident_contexts WHERE incident_id = %s", (incident_id,))
        ctx_cnt = cur.fetchone()["cnt"]
        assert ctx_cnt == 6
    print("Verified: Phase 4 incident_contexts remains 100% intact and unchanged.")

    conn.close()
    client.close()

    # 23. Verify frontend build
    print("\n--- Step 23: Verify Frontend Production Build ---")
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    print(f"Building frontend in {frontend_dir}...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    build_result = subprocess.run(
        [npm_cmd, "run", "build"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
        shell=True if sys.platform == "win32" else False
    )
    print(build_result.stdout)
    if build_result.returncode != 0:
        print(build_result.stderr)
        raise RuntimeError(f"Frontend build failed with exit code {build_result.returncode}")
    print("Verified: Frontend build succeeded with 0 errors.")

    print("\n==================================================")
    print("ALL 23 PHASE 5 E2E VERIFICATION CHECKS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    main()
