from typing import List
from sqlalchemy import asc, func
from sqlalchemy.orm import Session
from app.models.parsed_log import ParsedLog


class ParsedLogRepository:
    """Repository responsible for persisting and querying structured parsed_logs in PostgreSQL."""

    def __init__(self, db: Session):
        self.db = db

    def create_batch(self, events: List[ParsedLog]) -> List[ParsedLog]:
        """Persist a batch of parsed log event entities within a transaction."""
        if not events:
            return []
        self.db.add_all(events)
        self.db.commit()
        for event in events:
            self.db.refresh(event)
        return events

    def get_by_log_id(self, log_id: int) -> List[ParsedLog]:
        """Retrieve all parsed events for a source log ordered by event_index."""
        return (
            self.db.query(ParsedLog)
            .filter(ParsedLog.log_id == log_id)
            .order_by(asc(ParsedLog.event_index), asc(ParsedLog.id))
            .all()
        )

    def count_by_log_id(self, log_id: int) -> int:
        """Count the number of parsed events for a source log."""
        return (
            self.db.query(func.count(ParsedLog.id))
            .filter(ParsedLog.log_id == log_id)
            .scalar()
            or 0
        )

    def delete_by_log_id(self, log_id: int) -> int:
        """Delete all parsed events for a log ID (used during re-parse)."""
        deleted_count = (
            self.db.query(ParsedLog)
            .filter(ParsedLog.log_id == log_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted_count
