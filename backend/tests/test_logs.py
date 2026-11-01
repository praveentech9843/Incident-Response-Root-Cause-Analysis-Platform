import hashlib
import io
import json
from unittest import mock
import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.log import Log


@pytest.fixture(autouse=True)
def clean_logs():
    """Clean the logs table before and after each test for test isolation."""
    db = SessionLocal()
    try:
        db.query(Log).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(Log).delete()
        db.commit()
    finally:
        db.close()


# 1. Valid .log upload
def test_valid_log_upload(client: TestClient):
    """Test 1: Valid .log upload returns 201 with full metadata and hash."""
    content = "2026-10-06 12:00:00 [INFO] Order created successfully: id=9821\n"
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("service.log", io.BytesIO(content.encode("utf-8")), "text/plain")},
        data={"service_name": "order-service", "environment": "staging", "source_hint": "k8s"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["original_filename"] == "service.log"
    assert data["file_type"] == "log"
    assert data["service_name"] == "order-service"
    assert data["environment"] == "staging"
    assert data["source_hint"] == "k8s"
    assert data["is_duplicate"] is False
    assert data["content_hash"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert "created_at" in data


# 2. Valid .txt upload
def test_valid_txt_upload(client: TestClient):
    """Test 2: Valid .txt upload returns 201."""
    content = "System restart initiated by admin.\nSystem ready.\n"
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("audit.txt", io.BytesIO(content.encode("utf-8")), "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "audit.txt"
    assert data["file_type"] == "txt"
    assert data["service_name"] is None
    assert data["environment"] is None


# 3. Valid .json upload
def test_valid_json_upload(client: TestClient):
    """Test 3: Valid .json upload succeeds and validates syntax without semantic parsing."""
    json_content = json.dumps({"timestamp": "2026-10-06T12:00:00Z", "level": "WARN", "msg": "High latency"})
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("events.json", io.BytesIO(json_content.encode("utf-8")), "application/json")},
        data={"service_name": "event-bus"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["file_type"] == "json"
    assert data["original_filename"] == "events.json"


# 4. Invalid JSON rejection
def test_invalid_json_rejection(client: TestClient):
    """Test 4: Malformed JSON file is rejected with 400 Bad Request."""
    bad_json = '{"level": "ERROR", "msg": "Unterminated JSON'
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("bad.json", io.BytesIO(bad_json.encode("utf-8")), "application/json")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "Malformed JSON" in data["error"]["message"]


# 5. Unsupported extension rejection
def test_unsupported_extension_rejection(client: TestClient):
    """Test 5: Unsupported file extensions (.csv, .exe, .sh) are rejected with 400."""
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("script.py", io.BytesIO(b"print('hello')"), "text/x-python")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "Unsupported file extension" in data["error"]["message"]


# 6. Empty file rejection
def test_empty_file_rejection(client: TestClient):
    """Test 6: 0-byte file is rejected with 400 Bad Request."""
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("empty.log", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "empty" in data["error"]["message"].lower()


# 7. Oversized file rejection
def test_oversized_file_rejection(client: TestClient):
    """Test 7: File exceeding MAX_LOG_UPLOAD_SIZE_MB is rejected with 413."""
    # Temporarily set MAX_LOG_UPLOAD_SIZE_MB to 1 MB and send 1.5 MB
    with mock.patch.object(settings, "MAX_LOG_UPLOAD_SIZE_MB", 1):
        big_content = b"A" * (1024 * 1024 + 512)  # Just over 1MB
        response = client.post(
            "/api/v1/logs/upload",
            files={"file": ("large.log", io.BytesIO(big_content), "text/plain")},
        )
        assert response.status_code == 413
        data = response.json()
        assert "error" in data
        assert "exceeds" in data["error"]["message"].lower()


# 8. Metadata persistence
def test_metadata_persistence(client: TestClient):
    """Test 8: Metadata fields are correctly stored and retrieved."""
    content = "Sample log entry for metadata test\n"
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("meta.log", io.BytesIO(content.encode("utf-8")), "text/plain")},
        data={
            "service_name": "checkout-api",
            "environment": "production",
            "source_hint": "ecs-firelens",
        },
    )
    assert response.status_code == 201
    log_id = response.json()["id"]

    db = SessionLocal()
    try:
        record = db.query(Log).filter(Log.id == log_id).first()
        assert record is not None
        assert record.service_name == "checkout-api"
        assert record.environment == "production"
        assert record.source_hint == "ecs-firelens"
    finally:
        db.close()


# 9. Raw content persistence & line-ending normalization
def test_raw_content_persistence(client: TestClient):
    """Test 9: Raw content is faithfully preserved with normalized line endings."""
    windows_crlf_content = "Line 1\r\nLine 2 with special chars: <>&'\"\r\nLine 3\r\n"
    expected_content = "Line 1\nLine 2 with special chars: <>&'\"\nLine 3\n"
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("crlf.log", io.BytesIO(windows_crlf_content.encode("utf-8")), "text/plain")},
    )
    assert response.status_code == 201
    log_id = response.json()["id"]

    db = SessionLocal()
    try:
        record = db.query(Log).filter(Log.id == log_id).first()
        assert record is not None
        assert record.raw_content == expected_content
    finally:
        db.close()


# 10. Content hash generation
def test_content_hash_generation(client: TestClient):
    """Test 10: Deterministic SHA-256 hash is computed from normalized content."""
    content = "Unique content line for hash testing 12345\n"
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("hash.log", io.BytesIO(content.encode("utf-8")), "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["content_hash"] == expected_hash


# 11. Duplicate upload handling
def test_duplicate_upload_handling(client: TestClient):
    """Test 11: Identical content uploaded a second time is rejected with 409 Conflict."""
    content = "Deterministic repeated log content 9999\n"
    files = {"file": ("dup.log", io.BytesIO(content.encode("utf-8")), "text/plain")}

    # First upload: success
    res1 = client.post("/api/v1/logs/upload", files=files)
    assert res1.status_code == 201

    # Second upload of exact same content: rejected with 409
    files2 = {"file": ("dup_copy.log", io.BytesIO(content.encode("utf-8")), "text/plain")}
    res2 = client.post("/api/v1/logs/upload", files=files2)
    assert res2.status_code == 409
    data2 = res2.json()
    assert "error" in data2
    assert "duplicate" in data2["error"]["message"].lower()

    # Verify only 1 record exists in DB
    db = SessionLocal()
    try:
        count = db.query(Log).count()
        assert count == 1
    finally:
        db.close()


# 12. GET /api/v1/logs
def test_get_logs_endpoint(client: TestClient):
    """Test 12: GET /api/v1/logs returns actual database records with pagination."""
    # Upload 2 different logs
    c1 = "Log file A content\n"
    c2 = "Log file B content\n"
    client.post("/api/v1/logs/upload", files={"file": ("a.log", io.BytesIO(c1.encode("utf-8")), "text/plain")})
    client.post("/api/v1/logs/upload", files={"file": ("b.log", io.BytesIO(c2.encode("utf-8")), "text/plain")})

    response = client.get("/api/v1/logs?limit=10&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["limit"] == 10
    assert data["offset"] == 0

    # Ensure items contain required fields
    filenames = [item["original_filename"] for item in data["items"]]
    assert "a.log" in filenames
    assert "b.log" in filenames


# 13. PostgreSQL persistence direct query
def test_postgresql_persistence_direct_query(client: TestClient):
    """Test 13: Direct SQLAlchemy query confirms row is written into PostgreSQL."""
    content = "Postgres persistence direct verification\n"
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("db_test.log", io.BytesIO(content.encode("utf-8")), "text/plain")},
        data={"service_name": "pg-service", "environment": "production"},
    )
    assert response.status_code == 201
    log_id = response.json()["id"]

    db = SessionLocal()
    try:
        row = db.query(Log).filter(Log.id == log_id).one_or_none()
        assert row is not None
        assert row.original_filename == "db_test.log"
        assert row.service_name == "pg-service"
        assert row.environment == "production"
        assert row.raw_content == content
        assert row.created_at is not None
    finally:
        db.close()


# 14. Invalid encoding rejection
def test_invalid_encoding_rejection(client: TestClient):
    """Test 14: Non UTF-8 binary file content is rejected with 400 Bad Request."""
    invalid_bytes = b"\x80\x81\xff\xfe\x00"
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("corrupt.log", io.BytesIO(invalid_bytes), "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "encoding" in data["error"]["message"].lower()


# 15. Metadata empty normalization
def test_metadata_empty_normalization(client: TestClient):
    """Test 15: Blank or whitespace metadata is normalized to None (NULL)."""
    content = "Log content with blank metadata\n"
    response = client.post(
        "/api/v1/logs/upload",
        files={"file": ("blank_meta.log", io.BytesIO(content.encode("utf-8")), "text/plain")},
        data={"service_name": "  ", "environment": "", "source_hint": ""},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["service_name"] is None
    assert data["environment"] is None
    assert data["source_hint"] is None
