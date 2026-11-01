from typing import List, Optional, Tuple
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from app.models.log import Log


class LogRepository:
    """Repository layer responsible solely for Log persistence and retrieval in PostgreSQL."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, log_id: int) -> Optional[Log]:
        """Retrieve a log record by its primary key ID."""
        return self.db.query(Log).filter(Log.id == log_id).first()

    def get_by_hash(self, content_hash: str) -> Optional[Log]:
        """Retrieve a log record by its deterministic SHA-256 content hash."""
        return self.db.query(Log).filter(Log.content_hash == content_hash).first()

    def create(
        self,
        original_filename: str,
        file_type: str,
        service_name: Optional[str],
        environment: Optional[str],
        source_hint: Optional[str],
        raw_content: str,
        content_hash: str,
    ) -> Log:
        """Persist a new log record to the database."""
        log_record = Log(
            original_filename=original_filename,
            file_type=file_type,
            service_name=service_name,
            environment=environment,
            source_hint=source_hint,
            raw_content=raw_content,
            content_hash=content_hash,
        )
        self.db.add(log_record)
        self.db.commit()
        self.db.refresh(log_record)
        return log_record

    def list_logs(self, limit: int = 50, offset: int = 0) -> Tuple[List[Log], int]:
        """Retrieve a paginated list of logs ordered newest-first, along with total count."""
        total = self.db.query(func.count(Log.id)).scalar() or 0
        items = (
            self.db.query(Log)
            .order_by(desc(Log.created_at), desc(Log.id))
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total
