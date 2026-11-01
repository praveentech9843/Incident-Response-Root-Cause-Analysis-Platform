from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
import uuid
from sqlalchemy.orm import Session
from app.models.job import BackgroundJob


def create_job(
    db: Session,
    job_type: str,
    payload: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
) -> BackgroundJob:
    job = BackgroundJob(
        id=str(uuid.uuid4()),
        job_type=job_type,
        status="QUEUED",
        payload=json.dumps(payload) if payload else None,
        max_retries=max_retries,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def start_job(db: Session, job_id: str) -> Optional[BackgroundJob]:
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    if job:
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
    return job


def complete_job(
    db: Session,
    job_id: str,
    result: Optional[Dict[str, Any]] = None,
) -> Optional[BackgroundJob]:
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    if job:
        job.status = "COMPLETED"
        job.completed_at = datetime.now(timezone.utc)
        job.result = json.dumps(result) if result else None
        db.commit()
        db.refresh(job)
    return job


def fail_job(
    db: Session,
    job_id: str,
    error: str,
) -> Optional[BackgroundJob]:
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    if job:
        job.error = error
        if job.retry_count < job.max_retries:
            job.status = "RETRYING"
            job.retry_count += 1
        else:
            job.status = "FAILED"
            job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
    return job
