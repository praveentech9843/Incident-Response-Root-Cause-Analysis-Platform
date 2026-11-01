from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.core.database import Base


class ParsedLog(Base):
    """
    SQLAlchemy model representing a structured log event extracted from a raw log.
    Maintains a foreign key reference to the parent raw log record.
    """

    __tablename__ = "parsed_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    log_id = Column(
        Integer,
        ForeignKey("logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_index = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=True, index=True)
    level = Column(String(32), nullable=True, index=True)
    service_name = Column(String(128), nullable=True, index=True)
    message = Column(Text, nullable=False)
    exception_type = Column(String(128), nullable=True)
    exception_message = Column(Text, nullable=True)
    class_name = Column(String(255), nullable=True)
    method_name = Column(String(128), nullable=True)
    source_file = Column(String(255), nullable=True)
    line_number = Column(Integer, nullable=True)
    stack_trace = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationship back to raw log with ON DELETE CASCADE support
    raw_log = relationship(
        "Log",
        backref=backref("parsed_events", cascade="all, delete-orphan", passive_deletes=True),
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_parsed_logs_log_id_event_index", "log_id", "event_index"),
    )

    def __repr__(self) -> str:
        return (
            f"<ParsedLog(id={self.id}, log_id={self.log_id}, "
            f"event_index={self.event_index}, level='{self.level}')>"
        )
