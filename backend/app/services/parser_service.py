from typing import List, Optional
from fastapi import HTTPException, status

from app.models.log import Log
from app.models.parsed_log import ParsedLog
from app.parsers.base import ParseResult
from app.parsers.parser_registry import ParserRegistry, default_registry
from app.repositories.log_repository import LogRepository
from app.repositories.parsed_log_repository import ParsedLogRepository
from app.schemas.parsed_log import ParsedLogEvent, ParseLogResponse, ParsedLogListResponse


class ParserService:
    """
    Service managing log parsing workflows, idempotency, and database persistence.
    Converts raw logs into structured events without semantic incident reasoning.
    """

    def __init__(
        self,
        log_repo: LogRepository,
        parsed_repo: ParsedLogRepository,
        registry: Optional[ParserRegistry] = None,
    ):
        self.log_repo = log_repo
        self.parsed_repo = parsed_repo
        self.registry = registry or default_registry

    def parse_log(self, log_id: int, reparse: bool = False) -> ParseLogResponse:
        """
        Parse an existing raw log file into structured events and persist in PostgreSQL.
        Maintains idempotency: if already parsed and reparse is False, returns existing events.
        If reparse is True, deletes existing events in a controlled transaction and reparses.
        """
        # 1. Fetch raw log
        log = self.log_repo.get_by_id(log_id)
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Log with ID {log_id} not found.",
            )

        # 2. Check existing parsed records for idempotency
        existing_events = self.parsed_repo.get_by_log_id(log_id)
        if existing_events and not reparse:
            return ParseLogResponse(
                log_id=log.id,
                status="ALREADY_PARSED",
                event_count=len(existing_events),
                parser_used="existing_cache",
                events=[ParsedLogEvent.model_validate(e) for e in existing_events],
            )

        # If reparsing, delete existing events first
        if existing_events and reparse:
            self.parsed_repo.delete_by_log_id(log_id)

        # 3. Select parser from registry
        parser = self.registry.get_parser(log.raw_content, log.file_type)

        # 4. Execute deterministic parsing (pass log metadata service_name as default fallback)
        parse_result: ParseResult = parser.parse(
            content=log.raw_content,
            default_service=log.service_name,
        )

        # 5. Map ParsedEventData to ParsedLog ORM entities
        entities: List[ParsedLog] = []
        for ev in parse_result.events:
            entity = ParsedLog(
                log_id=log.id,
                event_index=ev.event_index,
                timestamp=ev.timestamp,
                level=ev.level,
                service_name=ev.service_name or log.service_name,
                message=ev.message,
                exception_type=ev.exception_type,
                exception_message=ev.exception_message,
                class_name=ev.class_name,
                method_name=ev.method_name,
                source_file=ev.source_file,
                line_number=ev.line_number,
                stack_trace=ev.stack_trace,
            )
            entities.append(entity)

        # 6. Persist structured events to PostgreSQL
        persisted = self.parsed_repo.create_batch(entities)

        return ParseLogResponse(
            log_id=log.id,
            status=parse_result.status,
            event_count=len(persisted),
            parser_used=parser.name,
            events=[ParsedLogEvent.model_validate(e) for e in persisted],
        )

    def get_parsed_logs(self, log_id: int) -> ParsedLogListResponse:
        """
        Retrieve all structured events previously parsed for a raw log.
        """
        log = self.log_repo.get_by_id(log_id)
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Log with ID {log_id} not found.",
            )

        events = self.parsed_repo.get_by_log_id(log_id)
        return ParsedLogListResponse(
            log_id=log.id,
            total=len(events),
            events=[ParsedLogEvent.model_validate(e) for e in events],
        )
