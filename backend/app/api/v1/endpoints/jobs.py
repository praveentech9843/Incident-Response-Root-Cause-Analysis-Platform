from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.job import BackgroundJob
from app.models.user import User
from app.schemas.job import BackgroundJobListResponse, BackgroundJobResponse

router = APIRouter()


@router.get("", response_model=BackgroundJobListResponse)
def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    job_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List background jobs with status tracking and pagination."""
    query = db.query(BackgroundJob)
    if status_filter:
        query = query.filter(BackgroundJob.status == status_filter.upper())
    if job_type:
        query = query.filter(BackgroundJob.job_type == job_type)

    total = query.count()
    jobs = query.order_by(BackgroundJob.created_at.desc()).offset(offset).limit(limit).all()

    return BackgroundJobListResponse(
        total=total,
        jobs=[BackgroundJobResponse.model_validate(j) for j in jobs],
    )


@router.get("/{job_id}", response_model=BackgroundJobResponse)
def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get single background job details."""
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found"}},
        )
    return BackgroundJobResponse.model_validate(job)
