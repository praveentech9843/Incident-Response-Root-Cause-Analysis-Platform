from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class BackgroundJobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    payload: Optional[str]
    result: Optional[str]
    error: Optional[str]
    retry_count: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class BackgroundJobListResponse(BaseModel):
    total: int
    jobs: List[BackgroundJobResponse]
