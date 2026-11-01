import hashlib
import json
from pathlib import Path
from typing import Optional, Tuple, List
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings
from app.models.log import Log
from app.repositories.log_repository import LogRepository
from app.schemas.log import LogUploadResponse, LogListItem, LogListResponse

ALLOWED_EXTENSIONS = {".log", ".txt", ".json"}


class LogService:
    """
    Business logic service for Phase 1 Log Ingestion.
    Handles file validation, basic normalization, duplicate detection, and storage.
    Does NOT perform semantic parsing or incident analysis.
    """

    def __init__(self, log_repo: LogRepository):
        self.log_repo = log_repo

    @staticmethod
    def _normalize_metadata_field(val: Optional[str]) -> Optional[str]:
        """Normalize empty or whitespace strings to None (stored as NULL in DB)."""
        if val is None:
            return None
        stripped = val.strip()
        return stripped if stripped else None

    async def ingest_log(
        self,
        file: UploadFile,
        service_name: Optional[str] = None,
        environment: Optional[str] = None,
        source_hint: Optional[str] = None,
    ) -> LogUploadResponse:
        """
        Validate, normalize, and ingest a single log file into PostgreSQL.
        """
        # 1. Filename & Missing File Validation
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing file or invalid filename.",
            )

        # Sanitize filename (prevent path traversal / trust issues)
        original_filename = Path(file.filename).name.strip()
        if not original_filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename cannot be empty.",
            )

        # 2. Extension Validation (Do not trust MIME type alone)
        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file extension '{ext}'. Supported file types: {allowed_str}.",
            )

        file_type = ext.lstrip(".").lower()

        # 3. Read Content and Check File Size Limit
        max_bytes = settings.MAX_LOG_UPLOAD_SIZE_MB * 1024 * 1024
        try:
            raw_bytes = await file.read()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read uploaded file: {str(e)}",
            )

        if len(raw_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File size exceeds maximum allowed limit of {settings.MAX_LOG_UPLOAD_SIZE_MB}MB.",
            )

        if len(raw_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        # 4. Encoding Validation (Safely decode content)
        try:
            decoded_content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                # Fallback to UTF-8 with BOM
                decoded_content = raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file encoding. File content must be valid UTF-8 text.",
                )

        # 5. Basic Normalization (Line endings normalized, preserve content faithfully)
        normalized_content = decoded_content.replace("\r\n", "\n").replace("\r", "\n")

        if not normalized_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty or contains only whitespace.",
            )

        # 6. JSON Syntax Validation (for .json files only)
        if ext == ".json":
            try:
                json.loads(normalized_content)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Malformed JSON syntax: {exc.msg} at line {exc.lineno}, column {exc.colno}.",
                )

        # 7. Normalize Metadata Fields
        clean_service = self._normalize_metadata_field(service_name)
        clean_env = self._normalize_metadata_field(environment)
        clean_hint = self._normalize_metadata_field(source_hint)

        # 8. Deterministic Content Hash (SHA-256)
        content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()

        # 9. Duplicate Upload Protection
        existing_log = self.log_repo.get_by_hash(content_hash)
        if existing_log:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Duplicate log upload: Identical content already exists "
                    f"(Log ID: {existing_log.id}, uploaded at {existing_log.created_at.isoformat()})."
                ),
            )

        # 10. Persist Raw Log Record to PostgreSQL
        created_log = self.log_repo.create(
            original_filename=original_filename,
            file_type=file_type,
            service_name=clean_service,
            environment=clean_env,
            source_hint=clean_hint,
            raw_content=normalized_content,
            content_hash=content_hash,
        )

        return LogUploadResponse(
            id=created_log.id,
            original_filename=created_log.original_filename,
            file_type=created_log.file_type,
            service_name=created_log.service_name,
            environment=created_log.environment,
            source_hint=created_log.source_hint,
            content_hash=created_log.content_hash,
            created_at=created_log.created_at,
            is_duplicate=False,
            message="Log file uploaded and stored successfully.",
        )

    def list_logs(self, limit: int = 50, offset: int = 0) -> LogListResponse:
        """
        Retrieve paginated actual uploaded log records from PostgreSQL.
        """
        logs, total = self.log_repo.list_logs(limit=limit, offset=offset)
        items = [
            LogListItem(
                id=log.id,
                original_filename=log.original_filename,
                file_type=log.file_type,
                service_name=log.service_name,
                environment=log.environment,
                source_hint=log.source_hint,
                content_hash=log.content_hash,
                created_at=log.created_at,
                content_length=len(log.raw_content),
            )
            for log in logs
        ]
        return LogListResponse(items=items, total=total, limit=limit, offset=offset)
