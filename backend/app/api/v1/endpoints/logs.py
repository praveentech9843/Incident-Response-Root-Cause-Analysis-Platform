from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.log_repository import LogRepository
from app.repositories.parsed_log_repository import ParsedLogRepository
from app.schemas.log import LogListResponse, LogUploadResponse
from app.schemas.parsed_log import ParseLogResponse, ParsedLogListResponse
from app.services.log_service import LogService
from app.services.parser_service import ParserService

router = APIRouter(prefix="/logs", tags=["Logs"])


def get_log_service(db: Session = Depends(get_db)) -> LogService:
    """Dependency provider for LogService."""
    repo = LogRepository(db)
    return LogService(repo)


def get_parser_service(db: Session = Depends(get_db)) -> ParserService:
    """Dependency provider for ParserService."""
    log_repo = LogRepository(db)
    parsed_repo = ParsedLogRepository(db)
    return ParserService(log_repo=log_repo, parsed_repo=parsed_repo)


# ==============================================================================
# Phase 1: Ingestion Endpoints (Static Routes)
# ==============================================================================

@router.post(
    "/upload",
    response_model=LogUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a raw log file",
    description=(
        "Accepts a raw .log, .txt, or .json file along with optional metadata. "
        "Validates syntax, performs basic normalization, verifies duplicate protection, "
        "and faithfully persists content in PostgreSQL."
    ),
)
async def upload_log(
    file: UploadFile = File(..., description="The raw log file (.log, .txt, .json)"),
    service_name: Optional[str] = Form(
        None, description="Optional service name (e.g. auth-service)"
    ),
    environment: Optional[str] = Form(
        None, description="Optional environment (e.g. production, staging)"
    ),
    source_hint: Optional[str] = Form(
        None, description="Optional source hint (e.g. stdout, syslog, k8s)"
    ),
    service: LogService = Depends(get_log_service),
) -> LogUploadResponse:
    """Endpoint to upload and ingest a single log file."""
    return await service.ingest_log(
        file=file,
        service_name=service_name,
        environment=environment,
        source_hint=source_hint,
    )


@router.get(
    "",
    response_model=LogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List ingested log files",
    description="Returns actual uploaded log records from PostgreSQL with pagination support.",
)
def list_logs(
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    service: LogService = Depends(get_log_service),
) -> LogListResponse:
    """Endpoint to retrieve a paginated list of ingested logs."""
    return service.list_logs(limit=limit, offset=offset)


# ==============================================================================
# Phase 2: Parsing Endpoints (Dynamic Routes)
# ==============================================================================

@router.post(
    "/{log_id}/parse",
    response_model=ParseLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Parse an ingested log into structured events",
    description=(
        "Retrieves the raw log from PostgreSQL, parses it deterministically into "
        "structured events (extracting timestamp, level, service, message, exceptions), "
        "and persists the structured records in PostgreSQL."
    ),
)
def parse_log(
    log_id: int,
    reparse: bool = Query(
        False,
        description="If True, re-parse and replace previously extracted events.",
    ),
    service: ParserService = Depends(get_parser_service),
) -> ParseLogResponse:
    """Parse a stored raw log into structured events."""
    return service.parse_log(log_id=log_id, reparse=reparse)


@router.get(
    "/{log_id}/parsed",
    response_model=ParsedLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve structured events for a log",
    description="Returns all previously parsed structured events for the specified log ID.",
)
def get_parsed_logs(
    log_id: int,
    service: ParserService = Depends(get_parser_service),
) -> ParsedLogListResponse:
    """Retrieve structured parsed events for a raw log."""
    return service.get_parsed_logs(log_id=log_id)
