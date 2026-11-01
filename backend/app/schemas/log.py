from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LogUploadResponse(BaseModel):
    """Response returned upon successful upload of a log file."""

    id: int
    original_filename: str
    file_type: str
    service_name: Optional[str] = None
    environment: Optional[str] = None
    source_hint: Optional[str] = None
    content_hash: str
    created_at: datetime
    is_duplicate: bool = False
    message: str = "Log file uploaded and stored successfully."

    model_config = ConfigDict(from_attributes=True)


class LogListItem(BaseModel):
    """Summary item for a stored log file in the logs list."""

    id: int
    original_filename: str
    file_type: str
    service_name: Optional[str] = None
    environment: Optional[str] = None
    source_hint: Optional[str] = None
    content_hash: str
    created_at: datetime
    content_length: int = Field(
        ..., description="Size of the raw log content in characters."
    )

    model_config = ConfigDict(from_attributes=True)


class LogListResponse(BaseModel):
    """Paginated response containing actual uploaded log records."""

    items: List[LogListItem]
    total: int
    limit: int
    offset: int
