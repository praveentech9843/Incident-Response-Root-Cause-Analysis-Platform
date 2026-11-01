import json
import httpx
from app.core.database import SessionLocal
from app.models.log import Log

BASE = "http://localhost:8000"

def run_e2e():
    print("=== STARTING MANUAL E2E VERIFICATION ===")
    
    with httpx.Client(base_url=BASE, timeout=10.0) as client:
        # Step 1: Health Check
        res = client.get("/health")
        print(f"1. Health check status: {res.status_code} -> {res.json()['status']}")
        assert res.status_code == 200

        # Step 2: Upload a REAL sample .log file
        sample_log = (
            "2026-10-06T15:30:01.120Z [INFO] auth-service: Starting authentication service v2.4.1\n"
            "2026-10-06T15:30:02.345Z [INFO] auth-service: Connected to user directory ldap://ldap.internal:389\n"
            "2026-10-06T15:30:05.678Z [WARN] auth-service: Token refresh took 450ms for user_id=usr_88291\n"
            "2026-10-06T15:30:10.901Z [ERROR] auth-service: Failed to validate signature: key ID key_9921 expired\n"
        )
        files = {"file": ("auth_service.log", sample_log.encode("utf-8"), "text/plain")}
        data = {
            "service_name": "auth-service",
            "environment": "production",
            "source_hint": "k8s-pod-stdout",
        }
        res = client.post("/api/v1/logs/upload", files=files, data=data)
        print(f"2. Upload .log status: {res.status_code}")
        assert res.status_code == 201
        upload_resp = res.json()
        print(f"   Log ID: {upload_resp['id']}")
        print(f"   Filename: {upload_resp['original_filename']}")
        print(f"   Hash: {upload_resp['content_hash']}")
        print(f"   Service: {upload_resp['service_name']}")
        uploaded_id = upload_resp["id"]

        # Step 3: GET /api/v1/logs to verify the upload appears in recent logs
        res = client.get("/api/v1/logs")
        print(f"3. GET /api/v1/logs status: {res.status_code}")
        assert res.status_code == 200
        logs_list = res.json()
        print(f"   Total logs count: {logs_list['total']}")
        assert any(item["id"] == uploaded_id for item in logs_list["items"])
        print("   Verified: uploaded log appears in recent logs list.")

        # Step 4: Refresh and verify it still exists
        res_refresh = client.get(f"/api/v1/logs?limit=50&offset=0")
        assert res_refresh.status_code == 200
        assert any(item["id"] == uploaded_id for item in res_refresh.json()["items"])
        print("4. Refresh verified: log record remains persisted across queries.")

        # Step 5: Query PostgreSQL directly to verify actual database record
        db = SessionLocal()
        try:
            db_record = db.query(Log).filter(Log.id == uploaded_id).one_or_none()
            assert db_record is not None
            print(f"5. PostgreSQL query verified: Log #{db_record.id} found in PostgreSQL")
            print(f"   DB original_filename: '{db_record.original_filename}'")
            print(f"   DB file_type: '{db_record.file_type}'")
            print(f"   DB service_name: '{db_record.service_name}'")
            print(f"   DB environment: '{db_record.environment}'")
            print(f"   DB content_hash: '{db_record.content_hash}'")
            print(f"   DB raw_content lines: {len(db_record.raw_content.splitlines())}")
            assert db_record.raw_content == sample_log
        finally:
            db.close()

        # Step 6: Upload the same file again and verify duplicate handling (409)
        files_dup = {"file": ("auth_service_duplicate.log", sample_log.encode("utf-8"), "text/plain")}
        res_dup = client.post("/api/v1/logs/upload", files=files_dup, data=data)
        print(f"6. Duplicate upload status: {res_dup.status_code}")
        assert res_dup.status_code == 409
        print(f"   Duplicate error response: {res_dup.json()['error']['message']}")

        # Step 7: Upload invalid JSON and verify rejection (400)
        bad_json = '{"timestamp": "2026-10-06", "status": "ERROR", unterminated_json...'
        files_bad_json = {"file": ("corrupt.json", bad_json.encode("utf-8"), "application/json")}
        res_bad_json = client.post("/api/v1/logs/upload", files=files_bad_json)
        print(f"7. Invalid JSON upload status: {res_bad_json.status_code}")
        assert res_bad_json.status_code == 400
        print(f"   Error response: {res_bad_json.json()['error']['message']}")

        # Step 8: Upload unsupported file (.pdf) and verify rejection (400)
        files_unsupported = {"file": ("report.pdf", b"%PDF-1.4 binary content", "application/pdf")}
        res_unsupported = client.post("/api/v1/logs/upload", files=files_unsupported)
        print(f"8. Unsupported file upload status: {res_unsupported.status_code}")
        assert res_unsupported.status_code == 400
        print(f"   Error response: {res_unsupported.json()['error']['message']}")

        # Step 9: Upload empty file (0 bytes) and verify rejection (400)
        files_empty = {"file": ("empty.log", b"", "text/plain")}
        res_empty = client.post("/api/v1/logs/upload", files=files_empty)
        print(f"9. Empty file upload status: {res_empty.status_code}")
        assert res_empty.status_code == 400
        print(f"   Error response: {res_empty.json()['error']['message']}")

        # Step 10: Upload valid .txt file
        txt_content = "2026-10-06 15:45:00 Worker thread pool initialized (size=16)\n"
        files_txt = {"file": ("worker.txt", txt_content.encode("utf-8"), "text/plain")}
        res_txt = client.post("/api/v1/logs/upload", files=files_txt, data={"service_name": "worker-pool"})
        print(f"10. Valid .txt upload status: {res_txt.status_code} -> file_type: {res_txt.json()['file_type']}")
        assert res_txt.status_code == 201

        # Step 11: Upload valid .json file
        valid_json = json.dumps({"timestamp": "2026-10-06T15:45:00Z", "level": "INFO", "message": "Cluster state OK"})
        files_json = {"file": ("cluster.json", valid_json.encode("utf-8"), "application/json")}
        res_json = client.post("/api/v1/logs/upload", files=files_json, data={"service_name": "cluster-manager"})
        print(f"11. Valid .json upload status: {res_json.status_code} -> file_type: {res_json.json()['file_type']}")
        assert res_json.status_code == 201

    print("\nALL MANUAL E2E VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_e2e()
