from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ParsedLogEvent(BaseModel):
    """Structured representation of a single log event."""

    id: int
    log_id: int
    event_index: int
    timestamp: Optional[datetime] = None
    level: Optional[str] = None
    service_name: Optional[str] = None
    message: str
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    stack_trace: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParseLogResponse(BaseModel):
    """Response returned upon parsing a raw log file."""

    log_id: int
    status: str = Field(
        ...,
        description="Parsing outcome: SUCCESS, PARTIAL, UNSUPPORTED_FORMAT, or ALREADY_PARSED",
    )
    event_count: int
    parser_used: str
    events: List[ParsedLogEvent]

    model_config = ConfigDict(from_attributes=True)


class ParsedLogListResponse(BaseModel):
    """Response returned when fetching parsed log events for a log."""

    log_id: int
    total: int
    events: List[ParsedLogEvent]

    model_config = ConfigDict(from_attributes=True)
