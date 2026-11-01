import io
import json
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.log import Log
from app.models.parsed_log import ParsedLog


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure a clean database state before and after each test."""
    db = SessionLocal()
    try:
        db.query(ParsedLog).delete()
        db.query(Log).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(ParsedLog).delete()
        db.query(Log).delete()
        db.commit()
    finally:
        db.close()


def _upload_raw_log(client: TestClient, filename: str, content: str, service_name: str = None) -> int:
    """Helper to upload a raw log and return its ID."""
    data = {}
    if service_name:
        data["service_name"] = service_name
    res = client.post(
        "/api/v1/logs/upload",
        files={"file": (filename, io.BytesIO(content.encode("utf-8")), "text/plain")},
        data=data,
    )
    assert res.status_code == 201
    return res.json()["id"]


# 1. Simple text log parsing
def test_simple_text_log_parsing(client: TestClient):
    """Test 1: Simple text log parses and extracts basic structure."""
    content = "2026-10-06 12:00:01 INFO InventoryService: Database connection established\n"
    log_id = _upload_raw_log(client, "simple.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["event_count"] == 1
    event = data["events"][0]
    assert event["level"] == "INFO"
    assert event["service_name"] == "InventoryService"
    assert event["message"] == "Database connection established"


# 2. Timestamp extraction
def test_timestamp_extraction(client: TestClient):
    """Test 2: Valid ISO and standard timestamps are accurately extracted into datetime."""
    content = "2026-10-06T14:30:15.500Z WARN OrderService: Payment timeout detected\n"
    log_id = _upload_raw_log(client, "timestamp.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.status_code == 200
    event = res.json()["events"][0]
    assert event["timestamp"] is not None
    dt = datetime.fromisoformat(event["timestamp"])
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 6
    assert dt.hour == 14
    assert dt.minute == 30


# 3. Log level extraction & normalization
def test_log_level_extraction_and_normalization(client: TestClient):
    """Test 3: Log levels are extracted and normalized (e.g. WARNING -> WARN)."""
    content = "2026-10-06 10:00:00 WARNING CacheService: Cache miss rate high\n"
    log_id = _upload_raw_log(client, "level.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.status_code == 200
    event = res.json()["events"][0]
    assert event["level"] == "WARN"


# 4. Service extraction
def test_service_extraction(client: TestClient):
    """Test 4: Service name is extracted from log text or falls back to upload metadata."""
    # Extracted from line:
    content = "2026-10-06 11:00:00 ERROR BillingService: Charge failed\n"
    log_id = _upload_raw_log(client, "service1.log", content)
    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.json()["events"][0]["service_name"] == "BillingService"

    # Fallback to upload metadata when line doesn't specify service:
    content2 = "2026-10-06 11:00:00 INFO Connection pool restarted\n"
    log_id2 = _upload_raw_log(client, "service2.log", content2, service_name="auth-service")
    res2 = client.post(f"/api/v1/logs/{log_id2}/parse")
    assert res2.json()["events"][0]["service_name"] == "auth-service"


# 5. Message extraction
def test_message_extraction(client: TestClient):
    """Test 5: Log message body is extracted cleanly."""
    content = "2026-10-06 12:00:00 INFO AuthService: User user_981 logged in successfully\n"
    log_id = _upload_raw_log(client, "msg.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    event = res.json()["events"][0]
    assert event["message"] == "User user_981 logged in successfully"


# 6. Exception extraction
def test_exception_extraction(client: TestClient):
    """Test 6: Exception type and exception message are extracted."""
    content = (
        "2026-10-06 12:00:01 ERROR InventoryService: NullPointerException: Item reference is null\n"
        "    at InventoryService.reserve(InventoryService.java:65)\n"
    )
    log_id = _upload_raw_log(client, "exc.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    event = res.json()["events"][0]
    assert event["exception_type"] == "NullPointerException"
    assert "Item reference is null" in (event["exception_message"] or "")


# 7 & 8 & 9. Source file, line number, method, class extraction (Java)
def test_java_stack_trace_frame_extraction(client: TestClient):
    """Test 7, 8, 9: Extracts source_file, line_number, class_name, and method_name from Java trace."""
    content = (
        "2026-10-06 12:00:01 ERROR InventoryService: NullPointerException\n"
        "    at com.example.InventoryService.reserve(InventoryService.java:65)\n"
        "    at com.example.OrderService.create(OrderService.java:120)\n"
    )
    log_id = _upload_raw_log(client, "java_stack.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    event = res.json()["events"][0]
    assert event["source_file"] == "InventoryService.java"
    assert event["line_number"] == 65
    assert event["method_name"] == "reserve"
    assert event["class_name"] == "InventoryService"
    assert event["exception_type"] == "NullPointerException"


# 10. Multi-line stack trace parsing (single event)
def test_multiline_stack_trace_grouped_as_single_event(client: TestClient):
    """Test 10: Multi-line stack trace is treated as one logical event, not multiple events."""
    content = (
        "2026-10-06 12:00:01 ERROR PaymentService: Traceback (most recent call last):\n"
        '    File "payment/processor.py", line 42, in process_charge\n'
        "        gateway.charge(amount)\n"
        "KeyError: 'gateway_token'\n"
    )
    log_id = _upload_raw_log(client, "python_trace.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    data = res.json()
    assert data["event_count"] == 1
    event = data["events"][0]
    assert event["source_file"] == "payment/processor.py"
    assert event["line_number"] == 42
    assert event["method_name"] == "process_charge"
    assert event["exception_type"] == "KeyError"
    assert event["stack_trace"] is not None


# 11. JSON log parsing
def test_json_log_parsing(client: TestClient):
    """Test 11: Valid JSON log object is mapped to structured log fields."""
    json_data = {
        "timestamp": "2026-10-06T12:00:01Z",
        "level": "ERROR",
        "service": "InventoryService",
        "message": "Database connection failed",
        "file": "db.py",
        "line": 88,
    }
    log_id = _upload_raw_log(client, "json_log.json", json.dumps(json_data))

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    event = data["events"][0]
    assert event["level"] == "ERROR"
    assert event["service_name"] == "InventoryService"
    assert event["message"] == "Database connection failed"
    assert event["source_file"] == "db.py"
    assert event["line_number"] == 88


# 12. JSON field aliases
def test_json_field_aliases(client: TestClient):
    """Test 12: JSON parser recognizes standard aliases (severity, msg, app, etc.)."""
    json_data = {
        "time": "2026-10-06T15:00:00Z",
        "severity": "WARNING",
        "app": "notification-worker",
        "msg": "Queue capacity threshold exceeded",
        "err_type": "QueueFullException",
        "lineno": 105,
    }
    log_id = _upload_raw_log(client, "aliases.json", json.dumps(json_data))

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    event = res.json()["events"][0]
    assert event["level"] == "WARN"
    assert event["service_name"] == "notification-worker"
    assert event["message"] == "Queue capacity threshold exceeded"
    assert event["exception_type"] == "QueueFullException"
    assert event["line_number"] == 105


# 13. Unknown/missing fields return NULL
def test_unknown_missing_fields_return_null(client: TestClient):
    """Test 13: When fields are not present in log, they are stored as None / NULL."""
    content = "2026-10-06 12:00:00 INFO General status heartbeat\n"
    log_id = _upload_raw_log(client, "missing.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    event = res.json()["events"][0]
    assert event["exception_type"] is None
    assert event["exception_message"] is None
    assert event["class_name"] is None
    assert event["method_name"] is None
    assert event["source_file"] is None
    assert event["line_number"] is None
    assert event["stack_trace"] is None


# 14. Unsupported format handling
def test_unsupported_format_handling(client: TestClient):
    """Test 14: Unstructured or unknown log format returns PARTIAL or UNSUPPORTED_FORMAT without crashing."""
    raw_text = "Random unstructured telemetry dump without header or timestamp"
    log_id = _upload_raw_log(client, "unstructured.log", raw_text)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in {"UNSUPPORTED_FORMAT", "PARTIAL"}
    assert data["event_count"] >= 1
    event = data["events"][0]
    assert event["message"] == raw_text
    assert event["level"] is None
    assert event["timestamp"] is None


# 15. Multiple events in one file
def test_multiple_events_in_one_file(client: TestClient):
    """Test 15: Multiple distinct log entries in a single file produce multiple structured events."""
    content = (
        "2026-10-06 12:00:01 INFO AuthService: User login request\n"
        "2026-10-06 12:00:02 WARN AuthService: Rate limit warning\n"
        "2026-10-06 12:00:03 ERROR AuthService: Password check failed\n"
    )
    log_id = _upload_raw_log(client, "multi.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.status_code == 200
    data = res.json()
    assert data["event_count"] == 3
    assert [e["level"] for e in data["events"]] == ["INFO", "WARN", "ERROR"]


# 16. Parsed event ordering using event_index
def test_parsed_event_ordering_by_event_index(client: TestClient):
    """Test 16: Parsed events are ordered strictly by event_index (0, 1, 2...)."""
    content = (
        "2026-10-06 10:00:01 INFO S1: First\n"
        "2026-10-06 10:00:02 INFO S1: Second\n"
        "2026-10-06 10:00:03 INFO S1: Third\n"
    )
    log_id = _upload_raw_log(client, "ordered.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    events = res.json()["events"]
    assert len(events) == 3
    assert [e["event_index"] for e in events] == [0, 1, 2]
    assert events[0]["message"] == "First"
    assert events[1]["message"] == "Second"
    assert events[2]["message"] == "Third"


# 17. Parsed log persistence in PostgreSQL
def test_parsed_log_persistence_in_postgresql(client: TestClient):
    """Test 17: Structured events are persisted in PostgreSQL table parsed_logs."""
    content = "2026-10-06 12:00:01 ERROR DBService: Connection refused\n"
    log_id = _upload_raw_log(client, "persist.log", content)

    client.post(f"/api/v1/logs/{log_id}/parse")

    db = SessionLocal()
    try:
        rows = db.query(ParsedLog).filter(ParsedLog.log_id == log_id).all()
        assert len(rows) == 1
        assert rows[0].level == "ERROR"
        assert rows[0].service_name == "DBService"
        assert rows[0].message == "Connection refused"
        assert rows[0].event_index == 0
    finally:
        db.close()


# 18. Foreign key relationship with logs
def test_foreign_key_relationship_and_cascade(client: TestClient):
    """Test 18: Foreign key constraint links parsed_logs to logs, and cascade on delete works."""
    content = "2026-10-06 12:00:01 INFO FKService: OK\n"
    log_id = _upload_raw_log(client, "fk.log", content)

    client.post(f"/api/v1/logs/{log_id}/parse")

    db = SessionLocal()
    try:
        # Verify FK points to valid Log
        parsed_row = db.query(ParsedLog).filter(ParsedLog.log_id == log_id).first()
        assert parsed_row is not None
        assert parsed_row.raw_log.id == log_id

        # Delete parent log and verify cascade removes parsed events
        parent_log = db.query(Log).filter(Log.id == log_id).first()
        db.delete(parent_log)
        db.commit()

        remaining_parsed = db.query(ParsedLog).filter(ParsedLog.log_id == log_id).count()
        assert remaining_parsed == 0
    finally:
        db.close()


# 19. Repeated parse does not duplicate records
def test_repeated_parse_idempotency(client: TestClient):
    """Test 19: Calling parse multiple times does not duplicate records in PostgreSQL."""
    content = "2026-10-06 12:00:01 ERROR DupService: Timeout\n"
    log_id = _upload_raw_log(client, "idempotent.log", content)

    # First call
    res1 = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res1.status_code == 200
    assert res1.json()["event_count"] == 1

    # Second call (without reparse)
    res2 = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res2.status_code == 200
    assert res2.json()["status"] == "ALREADY_PARSED"
    assert res2.json()["event_count"] == 1

    # Third call with reparse=true
    res3 = client.post(f"/api/v1/logs/{log_id}/parse?reparse=true")
    assert res3.status_code == 200
    assert res3.json()["event_count"] == 1

    # Total rows in DB must still be exactly 1
    db = SessionLocal()
    try:
        count = db.query(ParsedLog).filter(ParsedLog.log_id == log_id).count()
        assert count == 1
    finally:
        db.close()


# 20. Raw Phase 1 content remains unchanged
def test_raw_phase1_content_remains_unchanged(client: TestClient):
    """Test 20: Parsing does NOT alter the raw_content stored in the logs table."""
    raw_content = "2026-10-06 12:00:01 ERROR UntouchedService: Error string\n"
    log_id = _upload_raw_log(client, "audit_raw.log", raw_content)

    client.post(f"/api/v1/logs/{log_id}/parse")

    db = SessionLocal()
    try:
        parent = db.query(Log).filter(Log.id == log_id).first()
        assert parent.raw_content == raw_content
    finally:
        db.close()


# 21. GET parsed logs endpoint
def test_get_parsed_logs_endpoint(client: TestClient):
    """Test 21: GET /api/v1/logs/{log_id}/parsed returns actual database records."""
    content = (
        "2026-10-06 10:00:00 INFO ServiceA: Step 1\n"
        "2026-10-06 10:00:01 INFO ServiceA: Step 2\n"
    )
    log_id = _upload_raw_log(client, "get_parsed.log", content)

    # Call GET before parse -> returns 0 events
    res_before = client.get(f"/api/v1/logs/{log_id}/parsed")
    assert res_before.status_code == 200
    assert res_before.json()["total"] == 0

    # Parse
    client.post(f"/api/v1/logs/{log_id}/parse")

    # Call GET after parse -> returns 2 events
    res_after = client.get(f"/api/v1/logs/{log_id}/parsed")
    assert res_after.status_code == 200
    data = res_after.json()
    assert data["total"] == 2
    assert len(data["events"]) == 2
    assert data["events"][0]["message"] == "Step 1"
    assert data["events"][1]["message"] == "Step 2"


# 22. Regression: e2e_database.log format with UTF-8 BOM and consecutive events
def test_regression_e2e_database_log_format(client: TestClient):
    """
    Regression Test 22:
    Validates parsing of e2e_database.log format:
    - Leading UTF-8 BOM must not cause timestamp to be NULL on event 0.
    - service_name must not contain timestamp text on event 0.
    - message must not retain timestamp or ERROR prefix.
    - Space-delimited service 'DatabaseService' must be correctly extracted on all consecutive events.
    - correlation_id must be preserved in message.
    """
    content = (
        "\ufeff2026-10-09 10:00:01 ERROR DatabaseService correlation_id=E2E-RCA-001 Database connection timeout\n"
        "2026-10-09 10:00:03 ERROR DatabaseService correlation_id=E2E-RCA-001 Connection pool acquisition failed\n"
    )
    log_id = _upload_raw_log(client, "e2e_database.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["event_count"] == 2

    ev0 = data["events"][0]
    assert ev0["timestamp"] is not None
    assert ev0["timestamp"].startswith("2026-10-09T10:00:01")
    assert ev0["level"] == "ERROR"
    assert ev0["service_name"] == "DatabaseService"
    assert ev0["message"] == "correlation_id=E2E-RCA-001 Database connection timeout"

    ev1 = data["events"][1]
    assert ev1["timestamp"] is not None
    assert ev1["timestamp"].startswith("2026-10-09T10:00:03")
    assert ev1["level"] == "ERROR"
    assert ev1["service_name"] == "DatabaseService"
    assert ev1["message"] == "correlation_id=E2E-RCA-001 Connection pool acquisition failed"


# 23. Regression: e2e_payment.log format with consecutive events and correlation_id
def test_regression_e2e_payment_log_format(client: TestClient):
    """
    Regression Test 23:
    Validates parsing of e2e_payment.log format:
    - Service 'PaymentService' correctly extracted without delimiter symbols.
    - Consecutive events parsed consistently.
    - correlation_id preserved in message.
    """
    content = (
        "\ufeff2026-10-09 10:00:02 ERROR PaymentService correlation_id=E2E-RCA-001 Payment processing failed due to database connectivity\n"
        "2026-10-09 10:00:04 ERROR PaymentService correlation_id=E2E-RCA-001 Payment transaction could not complete\n"
    )
    log_id = _upload_raw_log(client, "e2e_payment.log", content)

    res = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["event_count"] == 2

    ev0 = data["events"][0]
    assert ev0["timestamp"] is not None
    assert ev0["timestamp"].startswith("2026-10-09T10:00:02")
    assert ev0["level"] == "ERROR"
    assert ev0["service_name"] == "PaymentService"
    assert ev0["message"] == "correlation_id=E2E-RCA-001 Payment processing failed due to database connectivity"

    ev1 = data["events"][1]
    assert ev1["timestamp"] is not None
    assert ev1["timestamp"].startswith("2026-10-09T10:00:04")
    assert ev1["level"] == "ERROR"
    assert ev1["service_name"] == "PaymentService"
    assert ev1["message"] == "correlation_id=E2E-RCA-001 Payment transaction could not complete"


# 24. Regression: Reparse persists corrected fields into PostgreSQL
def test_regression_reparse_persists_corrected_fields(client: TestClient):
    """
    Regression Test 24:
    Verifies that calling POST /api/v1/logs/{id}/parse?reparse=true:
    - Updates database records in parsed_logs with corrected fields.
    - Preserves raw log content in logs table.
    """
    content = (
        "\ufeff2026-10-09 10:00:01 ERROR DatabaseService correlation_id=E2E-RCA-001 Database connection timeout\n"
        "2026-10-09 10:00:03 ERROR DatabaseService correlation_id=E2E-RCA-001 Connection pool acquisition failed\n"
    )
    log_id = _upload_raw_log(client, "reparse_test.log", content)

    # Initial parse
    res1 = client.post(f"/api/v1/logs/{log_id}/parse")
    assert res1.status_code == 200
    assert res1.json()["event_count"] == 2

    # Explicit reparse
    res_reparse = client.post(f"/api/v1/logs/{log_id}/parse?reparse=true")
    assert res_reparse.status_code == 200
    reparse_data = res_reparse.json()
    assert reparse_data["event_count"] == 2
    assert reparse_data["status"] == "SUCCESS"

    # Verify directly from PostgreSQL session
    db = SessionLocal()
    try:
        raw_log = db.query(Log).filter(Log.id == log_id).first()
        assert raw_log is not None
        # Raw content must remain completely untouched
        assert raw_log.raw_content == content

        parsed_rows = (
            db.query(ParsedLog)
            .filter(ParsedLog.log_id == log_id)
            .order_by(ParsedLog.event_index)
            .all()
        )
        assert len(parsed_rows) == 2

        # Row 0
        assert parsed_rows[0].event_index == 0
        assert parsed_rows[0].timestamp is not None
        assert parsed_rows[0].timestamp.year == 2026
        assert parsed_rows[0].timestamp.month == 10
        assert parsed_rows[0].timestamp.day == 9
        assert parsed_rows[0].timestamp.hour == 10
        assert parsed_rows[0].timestamp.minute == 0
        assert parsed_rows[0].timestamp.second == 1
        assert parsed_rows[0].level == "ERROR"
        assert parsed_rows[0].service_name == "DatabaseService"
        assert parsed_rows[0].message == "correlation_id=E2E-RCA-001 Database connection timeout"

        # Row 1
        assert parsed_rows[1].event_index == 1
        assert parsed_rows[1].timestamp is not None
        assert parsed_rows[1].timestamp.year == 2026
        assert parsed_rows[1].timestamp.month == 10
        assert parsed_rows[1].timestamp.day == 9
        assert parsed_rows[1].timestamp.hour == 10
        assert parsed_rows[1].timestamp.minute == 0
        assert parsed_rows[1].timestamp.second == 3
        assert parsed_rows[1].level == "ERROR"
        assert parsed_rows[1].service_name == "DatabaseService"
        assert parsed_rows[1].message == "correlation_id=E2E-RCA-001 Connection pool acquisition failed"
    finally:
        db.close()

