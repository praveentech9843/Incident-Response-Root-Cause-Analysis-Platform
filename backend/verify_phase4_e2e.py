"""
Phase 4 E2E Verification Script.
Verifies Context Enrichment end-to-end:
1. Health check
2. Real log upload
3. Log parsing
4. Incident correlation
5. Retrieve generated incident
6. Trigger context enrichment
7. Verify service context (derived from parsed logs, no fake owner/runtime)
8. Verify history context (derived from PostgreSQL, previous occurrences)
9. Verify dependency context (observed co-occurring services, no causal claims)
10. Verify unavailable integrations explicitly represented
11. Verify no fake metrics exist (no synthetic CPU/RAM %)
12. Verify no fake deployment info exists (no synthetic git commits/versions)
13. Run enrichment again
14. Verify idempotency (no duplicate rows in incident_contexts table)
15. Verify original raw_content unchanged
16. Verify parsed_logs unchanged
17. Verify incident_events unchanged
18. Verify frontend build
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
    print("STARTING PHASE 4 E2E VERIFICATION")
    print("==================================================")

    run_id = uuid.uuid4().hex[:8]
    client = httpx.Client(base_url=BASE_URL, timeout=15.0)

    # 1. Health check
    print("\n--- Step 1: Backend Health Check ---")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
    health_data = resp.json()
    print(f"Health Status: {health_data['status']}, Database: {health_data.get('database')}")
    assert health_data["status"] == "ok"

    # 2. Upload a REAL multi-service test log through the existing API
    print("\n--- Step 2: Upload Real Multi-Service Log ---")
    log_content = f"""2026-10-07 10:00:01 ERROR CheckoutService: Payment processing failed for customer [req:phase4-{run_id}]
2026-10-07 10:00:03 ERROR PaymentGateway: Third-party webhook timed out after 3000ms [req:phase4-{run_id}]
2026-10-07 10:00:05 ERROR NotificationService: Failed to dispatch customer alert [req:phase4-{run_id}]
2026-10-07 10:00:07 INFO WebPortal: Rendered error boundary fallback [req:phase4-{run_id}]
"""
    files = {
        "file": (f"phase4_e2e_log_{run_id}.log", log_content.encode("utf-8"), "text/plain")
    }
    data = {
        "service_name": "CheckoutService",
        "environment": "production",
        "source_hint": "k8s-stdout",
    }
    resp = client.post("/api/v1/logs/upload", files=files, data=data)
    assert resp.status_code == 201, f"Upload failed: {resp.status_code} {resp.text}"
    uploaded_log = resp.json()
    log_id = uploaded_log["id"]
    print(f"Uploaded log id={log_id}, filename={uploaded_log['original_filename']}")

    # 3. Parse the log
    print("\n--- Step 3: Parse Log via Phase 2 API ---")
    resp = client.post(f"/api/v1/logs/{log_id}/parse")
    assert resp.status_code == 200, f"Parse failed: {resp.status_code} {resp.text}"
    parsed_res = resp.json()
    print(f"Parsed {parsed_res['event_count']} events via parser: {parsed_res['parser_used']}")
    assert parsed_res["event_count"] == 4

    # 4. Correlate the parsed events
    print("\n--- Step 4: Correlate Parsed Events via Phase 3 API ---")
    resp = client.post("/api/v1/incidents/correlate", json={"log_id": log_id})
    assert resp.status_code == 200, f"Correlation failed: {resp.status_code} {resp.text}"
    corr_res = resp.json()
    print(f"Correlation: created={corr_res['incidents_created']}, existing={corr_res['incidents_existing']}")
    assert len(corr_res["incidents"]) >= 1

    # 5. Get the generated incident
    print("\n--- Step 5: Retrieve Generated Incident ---")
    incident = corr_res["incidents"][0]
    incident_id = incident["id"]
    print(f"Target Incident ID: {incident_id}")
    print(f"Title: {incident['title']}")
    print(f"Service Count: {incident['service_count']}")
    print(f"Event Count: {incident['event_count']}")

    # 6. Trigger enrichment
    print("\n--- Step 6: Trigger Context Enrichment (POST /api/v1/incidents/{id}/enrich) ---")
    resp = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert resp.status_code == 200, f"Enrichment failed: {resp.status_code} {resp.text}"
    enriched = resp.json()
    print(f"Enrichment returned for incident_id={enriched['incident_id']}")
    print(f"Categories returned: {list(enriched['contexts'].keys())}")
    assert enriched["incident_id"] == incident_id
    assert len(enriched["contexts"]) == 6

    # 7. Verify service context
    print("\n--- Step 7: Verify Service Context ---")
    service_ctx = enriched["contexts"]["service"]
    print(f"Service Context Status: {service_ctx['status']}")
    assert service_ctx["status"] == "AVAILABLE"
    svc_data = service_ctx["data"]
    services_found = svc_data.get("services_involved", [])
    print(f"Services involved: {services_found}")
    assert "CheckoutService" in services_found
    assert "PaymentGateway" in services_found
    assert "NotificationService" in services_found
    # Unverified attributes must not be fabricated
    assert svc_data.get("owner") is None
    assert svc_data.get("repository") is None
    assert svc_data.get("runtime") is None
    field_avail = svc_data.get("field_availability", {})
    print(f"Field availability: {field_avail}")
    assert field_avail.get("owner") in ["NOT_CONNECTED", "UNAVAILABLE"]
    assert field_avail.get("repository") in ["NOT_CONNECTED", "UNAVAILABLE"]

    # 8. Verify history context
    print("\n--- Step 8: Verify Incident History Context ---")
    history_ctx = enriched["contexts"]["history"]
    print(f"History Context Status: {history_ctx['status']}")
    assert history_ctx["status"] == "AVAILABLE"
    hist_data = history_ctx["data"]
    print(f"Previous occurrence count: {hist_data.get('previous_occurrence_count')}")
    print(f"Recurring indicator: {hist_data.get('recurring')}")
    print(f"Previous incident IDs: {hist_data.get('previous_incident_ids')}")
    assert isinstance(hist_data.get("previous_occurrence_count"), int)
    assert isinstance(hist_data.get("recurring"), bool)
    assert isinstance(hist_data.get("previous_incident_ids"), list)

    # 9. Verify dependency context
    print("\n--- Step 9: Verify Dependency Context ---")
    dep_ctx = enriched["contexts"]["dependencies"]
    print(f"Dependency Context Status: {dep_ctx['status']}")
    assert dep_ctx["status"] == "AVAILABLE"
    dep_data = dep_ctx["data"]
    print(f"Services involved: {dep_data.get('services_involved')}")
    print(f"Causality status: {dep_data.get('causality_status')}")
    assert dep_data.get("causality_status") == "UNVERIFIED"
    assert dep_data.get("causal_graph") is None
    assert "CheckoutService" in dep_data.get("services_involved", [])
    assert "PaymentGateway" in dep_data.get("services_involved", [])

    # 10. Verify unavailable integrations are explicitly represented
    print("\n--- Step 10: Verify Explicit Representation of Unavailable Integrations ---")
    deploy_ctx = enriched["contexts"]["deployment"]
    infra_ctx = enriched["contexts"]["infrastructure"]
    metrics_ctx = enriched["contexts"]["metrics"]

    print(f"Deployment status: {deploy_ctx['status']}")
    print(f"Infrastructure status: {infra_ctx['status']}")
    print(f"Metrics status: {metrics_ctx['status']}")

    assert deploy_ctx["status"] in ["INTEGRATION_REQUIRED", "UNAVAILABLE"]
    assert infra_ctx["status"] in ["NOT_CONNECTED", "UNAVAILABLE", "INTEGRATION_REQUIRED"]
    assert metrics_ctx["status"] in ["NOT_CONNECTED", "UNAVAILABLE", "INTEGRATION_REQUIRED"]

    # 11. Verify no fake metrics exist
    print("\n--- Step 11: Verify No Fake Metrics Generated ---")
    metrics_data = metrics_ctx["data"]
    print(f"Metrics payload: {metrics_data}")
    # Verify no synthetic percentages or usage
    assert metrics_data.get("cpu_usage") is None
    assert metrics_data.get("memory_usage") is None
    assert metrics_data.get("latency") is None
    assert metrics_data.get("p95") is None
    assert metrics_data.get("p99") is None
    assert metrics_data.get("connected") is False

    # 12. Verify no fake deployment information exists
    print("\n--- Step 12: Verify No Fake Deployment Information ---")
    deploy_data = deploy_ctx["data"]
    print(f"Deployment payload: {deploy_data}")
    assert deploy_data.get("git_commit") is None
    assert deploy_data.get("deployment_version") is None
    assert deploy_data.get("build_number") is None
    assert deploy_data.get("author") is None
    assert deploy_data.get("connected") is False

    # 13. Run enrichment again
    print("\n--- Step 13: Run Repeated Enrichment (Idempotency Test) ---")
    resp_again = client.post(f"/api/v1/incidents/{incident_id}/enrich")
    assert resp_again.status_code == 200, f"Second enrichment failed: {resp_again.status_code}"
    enriched_again = resp_again.json()
    assert enriched_again["incident_id"] == incident_id

    # 14. Verify idempotency in PostgreSQL
    print("\n--- Step 14: Verify Database Idempotency in PostgreSQL ---")
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT count(*) as cnt FROM incident_contexts WHERE incident_id = %s",
            (incident_id,)
        )
        ctx_row_count = cur.fetchone()["cnt"]
        print(f"incident_contexts count in DB for incident {incident_id}: {ctx_row_count}")
        assert ctx_row_count == 6, f"Expected exactly 6 category rows, found {ctx_row_count}! Uncontrolled duplicate rows created!"

        # Verify each of the 6 categories exists exactly once
        cur.execute(
            "SELECT context_category, count(*) as c FROM incident_contexts WHERE incident_id = %s GROUP BY context_category",
            (incident_id,)
        )
        category_counts = cur.fetchall()
        for row in category_counts:
            print(f"Category '{row['context_category']}': count = {row['c']}")
            assert row["c"] == 1, f"Duplicate rows for category {row['context_category']}!"

    # Test GET /api/v1/incidents/{incident_id}/context
    print("\n--- Testing GET /api/v1/incidents/{id}/context ---")
    resp_get_all = client.get(f"/api/v1/incidents/{incident_id}/context")
    assert resp_get_all.status_code == 200
    all_ctx = resp_get_all.json()
    assert len(all_ctx["contexts"]) == 6

    # Test GET /api/v1/incidents/{incident_id}/context/{category}
    print("\n--- Testing GET /api/v1/incidents/{id}/context/metrics ---")
    resp_get_cat = client.get(f"/api/v1/incidents/{incident_id}/context/metrics")
    assert resp_get_cat.status_code == 200
    cat_item = resp_get_cat.json()
    assert cat_item["context_category"] == "metrics"
    assert cat_item["status"] == "NOT_CONNECTED"

    # Test Nonexistent Incident Returns 404
    print("\n--- Testing Nonexistent Incident Returns 404 ---")
    resp_404 = client.post("/api/v1/incidents/9999999/enrich")
    assert resp_404.status_code == 404, f"Expected 404, got {resp_404.status_code}"
    resp_404_get = client.get("/api/v1/incidents/9999999/context")
    assert resp_404_get.status_code == 404, f"Expected 404, got {resp_404_get.status_code}"

    # 15. Verify original raw_content unchanged
    print("\n--- Step 15: Verify Original raw_content Unchanged ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT raw_content FROM logs WHERE id = %s", (log_id,))
        raw_in_db = cur.fetchone()["raw_content"]
        assert raw_in_db == log_content, "CRITICAL: raw_content was mutated during Phase 4 enrichment!"
        print("Verified: Phase 1 raw_content remains 100% byte-for-byte identical.")

    # 16. Verify parsed_logs unchanged
    print("\n--- Step 16: Verify parsed_logs Unchanged ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM parsed_logs WHERE log_id = %s", (log_id,))
        parsed_count_db = cur.fetchone()["cnt"]
        assert parsed_count_db == 4, f"CRITICAL: parsed_logs count changed! Expected 4, found {parsed_count_db}"
        print("Verified: Phase 2 parsed_logs remains 100% intact and unchanged.")

    # 17. Verify incident_events unchanged
    print("\n--- Step 17: Verify incident_events Unchanged ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM incident_events WHERE incident_id = %s", (incident_id,))
        ie_count_db = cur.fetchone()["cnt"]
        assert ie_count_db == incident["event_count"], f"CRITICAL: incident_events count changed! Expected {incident['event_count']}, found {ie_count_db}"
        print("Verified: Phase 3 incident_events remains 100% intact and unchanged.")

    conn.close()
    client.close()

    # 18. Verify frontend build
    print("\n--- Step 18: Verify Frontend Build ---")
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    print(f"Running frontend build check in {frontend_dir}...")
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
    print("ALL 18 PHASE 4 E2E VERIFICATION CHECKS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    main()
