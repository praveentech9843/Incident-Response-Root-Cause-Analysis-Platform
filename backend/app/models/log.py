from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class Log(Base):
    """
    SQLAlchemy model representing an ingested raw log file.
    Stores the raw file content faithfully without semantic parsing.
    """

    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(32), nullable=False)
    service_name = Column(String(128), nullable=True, index=True)
    environment = Column(String(64), nullable=True, index=True)
    source_hint = Column(String(255), nullable=True)
    raw_content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Log(id={self.id}, filename='{self.original_filename}', type='{self.file_type}')>"
