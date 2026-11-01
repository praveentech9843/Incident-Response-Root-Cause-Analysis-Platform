from sqlalchemy import Column, DateTime, Integer, String, Text, func
from app.core.database import Base


class BackgroundJob(Base):
    """
    Background job tracking for asynchronous and long-running tasks.
    States: QUEUED, RUNNING, COMPLETED, FAILED, RETRYING.
    """
    __tablename__ = "background_jobs"

    id = Column(String(36), primary_key=True, index=True)
    job_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="QUEUED", nullable=False, index=True)  # QUEUED, RUNNING, COMPLETED, FAILED, RETRYING
    payload = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<BackgroundJob id={self.id} type='{self.job_type}' status='{self.status}'>"
