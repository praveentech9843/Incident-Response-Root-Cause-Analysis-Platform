"""
Phase 2 Manual E2E Verification Script.
Tests real HTTP requests against the running FastAPI backend and directly inspects PostgreSQL.
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
    print("STARTING PHASE 2 E2E VERIFICATION")
    print("==================================================")

    run_id = uuid.uuid4().hex[:8]
    client = httpx.Client(base_url=BASE_URL, timeout=10.0)

    # 1. Backend Health Check
    print("\n--- Step 1: Backend Health Check ---")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Health check failed: {resp.status_code} {resp.text}"
    print(f"Health OK: {resp.json()}")

    # 2. Upload a Multi-line Java Log with Stack Trace
    print("\n--- Step 2: Upload Java Log with Stack Trace ---")
    java_log_content = f"""2026-10-06 12:00:01 ERROR InventoryService: NullPointerException [run:{run_id}]
    at InventoryService.reserve(InventoryService.java:65)
    at OrderService.create(OrderService.java:120)
2026-10-06 12:00:05 INFO OrderService: Order #9821 processed successfully
"""
    files = {
        "file": (f"e2e_inventory_{run_id}.log", java_log_content.encode("utf-8"), "text/plain")
    }
    data = {
        "service_name": "InventoryService",
        "environment": "production",
        "source_hint": "k8s-pod"
    }
    resp = client.post("/api/v1/logs/upload", files=files, data=data)
    assert resp.status_code == 201, f"Upload failed: {resp.status_code} {resp.text}"
    java_log = resp.json()
    java_log_id = java_log["id"]
    print(f"Uploaded log id={java_log_id}, filename={java_log['original_filename']}")

    # 3. Parse Java Log (POST /api/v1/logs/{id}/parse)
    print("\n--- Step 3: Parse Java Log via API ---")
    resp = client.post(f"/api/v1/logs/{java_log_id}/parse")
    assert resp.status_code == 200, f"Parse failed: {resp.status_code} {resp.text}"
    parse_result = resp.json()
    print(f"Parse result: status={parse_result['status']}, events={parse_result['event_count']}, parser={parse_result['parser_used']}")
    assert parse_result["event_count"] == 2, f"Expected 2 events, got {parse_result['event_count']}"
    assert parse_result["status"] == "SUCCESS"

    evt0 = parse_result["events"][0]
    print(f"Event 0: timestamp={evt0['timestamp']}, level={evt0['level']}, service={evt0['service_name']}")
    print(f"         exception_type={evt0['exception_type']}, source_file={evt0['source_file']}, line={evt0['line_number']}, method={evt0['method_name']}")
    assert evt0["level"] == "ERROR"
    assert evt0["service_name"] == "InventoryService"
    assert evt0["exception_type"] == "NullPointerException"
    assert evt0["source_file"] == "InventoryService.java"
    assert evt0["line_number"] == 65
    assert evt0["method_name"] == "reserve"
    assert evt0["stack_trace"] is not None

    evt1 = parse_result["events"][1]
    print(f"Event 1: timestamp={evt1['timestamp']}, level={evt1['level']}, service={evt1['service_name']}, msg={evt1['message']}")
    assert evt1["level"] == "INFO"
    assert evt1["service_name"] == "OrderService"

    # 4. Fetch Parsed Logs (GET /api/v1/logs/{id}/parsed)
    print("\n--- Step 4: Retrieve Parsed Events (GET) ---")
    resp = client.get(f"/api/v1/logs/{java_log_id}/parsed")
    assert resp.status_code == 200, f"GET parsed failed: {resp.status_code} {resp.text}"
    get_result = resp.json()
    assert get_result["total"] == 2
    print(f"GET /parsed returned {get_result['total']} events")

    # 5. Test Idempotency (Repeat POST parse without reparse)
    print("\n--- Step 5: Test Idempotency (Repeat Parse) ---")
    resp = client.post(f"/api/v1/logs/{java_log_id}/parse")
    assert resp.status_code == 200
    repeat_result = resp.json()
    assert repeat_result["event_count"] == 2

    # Check database row count directly in PostgreSQL
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM parsed_logs WHERE log_id = %s", (java_log_id,))
        count_in_db = cur.fetchone()["cnt"]
        print(f"Database row count in parsed_logs for log_id={java_log_id}: {count_in_db}")
        assert count_in_db == 2, f"Expected 2 rows in DB, found {count_in_db}"

    # 6. Test Explicit Re-parse (POST with reparse=true)
    print("\n--- Step 6: Test Controlled Re-parse (reparse=true) ---")
    resp = client.post(f"/api/v1/logs/{java_log_id}/parse?reparse=true")
    assert resp.status_code == 200
    reparse_result = resp.json()
    assert reparse_result["event_count"] == 2
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT count(*) as cnt FROM parsed_logs WHERE log_id = %s", (java_log_id,))
        count_in_db_after = cur.fetchone()["cnt"]
        print(f"Database row count in parsed_logs after reparse=true: {count_in_db_after}")
        assert count_in_db_after == 2, f"Expected 2 rows in DB after reparse, found {count_in_db_after}"

    # 7. Upload and Parse JSON Log
    print("\n--- Step 7: Upload and Parse Structured JSON Log ---")
    json_log_content = f"""[
  {{
    "time": "2026-10-06T14:30:00Z",
    "severity": "WARNING",
    "service": "payment-gateway",
    "msg": "Webhook response timeout after 5000ms [run:{run_id}]",
    "file": "webhook.go",
    "line": 88
  }},
  {{
    "time": "2026-10-06T14:30:02Z",
    "severity": "CRITICAL",
    "service": "payment-gateway",
    "msg": "Circuit breaker OPEN for stripe-api"
  }}
]"""
    files = {
        "file": (f"e2e_payment_{run_id}.json", json_log_content.encode("utf-8"), "application/json")
    }
    resp = client.post("/api/v1/logs/upload", files=files)
    assert resp.status_code == 201, f"JSON upload failed: {resp.status_code} {resp.text}"
    json_log_id = resp.json()["id"]

    resp = client.post(f"/api/v1/logs/{json_log_id}/parse")
    assert resp.status_code == 200, f"JSON parse failed: {resp.status_code} {resp.text}"
    json_parse_result = resp.json()
    print(f"JSON Parse result: parser={json_parse_result['parser_used']}, count={json_parse_result['event_count']}")
    assert json_parse_result["parser_used"] == "json_log_parser"
    assert json_parse_result["event_count"] == 2
    # Verify level normalization WARNING -> WARN
    assert json_parse_result["events"][0]["level"] == "WARN"
    assert json_parse_result["events"][0]["service_name"] == "payment-gateway"
    assert json_parse_result["events"][0]["line_number"] == 88
    assert json_parse_result["events"][0]["source_file"] == "webhook.go"
    assert json_parse_result["events"][1]["level"] == "CRITICAL"

    # 8. Upload and Parse Malformed / Unsupported Format Log
    print("\n--- Step 8: Upload and Parse Unsupported Format Log ---")
    plain_content = f"Just some arbitrary text without timestamp or recognizable structure. [run:{run_id}]"
    files = {
        "file": (f"e2e_unstructured_{run_id}.txt", plain_content.encode("utf-8"), "text/plain")
    }
    resp = client.post("/api/v1/logs/upload", files=files)
    assert resp.status_code == 201
    plain_log_id = resp.json()["id"]

    resp = client.post(f"/api/v1/logs/{plain_log_id}/parse")
    assert resp.status_code == 200
    plain_result = resp.json()
    print(f"Unstructured Parse result: status={plain_result['status']}, count={plain_result['event_count']}")
    assert plain_result["status"] in ("UNSUPPORTED_FORMAT", "PARTIAL")
    assert plain_result["events"][0]["timestamp"] is None
    assert plain_result["events"][0]["level"] is None
    assert plain_result["events"][0]["message"] == plain_content

    # 9. Verify Raw Log Immutability in PostgreSQL
    print("\n--- Step 9: Verify Raw Log Content Unchanged in PostgreSQL ---")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT raw_content FROM logs WHERE id = %s", (java_log_id,))
        db_raw = cur.fetchone()["raw_content"]
        assert db_raw == java_log_content, "CRITICAL: Raw log content was modified!"
        print("Verified: Phase 1 raw_content in PostgreSQL remains 100% IDENTICAL and UNCHANGED!")

    conn.close()
    client.close()
    print("\n==================================================")
    print("ALL PHASE 2 E2E VERIFICATION CHECKS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    main()
