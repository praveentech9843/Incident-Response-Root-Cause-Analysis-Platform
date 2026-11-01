import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dateutil import parser as dt_parser

from app.parsers.base import BaseLogParser, ParsedEventData, ParseResult
from app.parsers.text_parser import KNOWN_LEVELS

# Supported alias mappings
TIMESTAMP_ALIASES = ["timestamp", "time", "@timestamp", "ts", "datetime", "date"]
LEVEL_ALIASES = ["level", "severity", "log_level", "status", "lvl"]
SERVICE_ALIASES = ["service", "service_name", "app", "application", "component"]
MESSAGE_ALIASES = ["message", "msg", "log", "text", "description", "event"]
EXCEPTION_TYPE_ALIASES = ["exception_type", "error_type", "exception", "error", "err_type"]
EXCEPTION_MSG_ALIASES = ["exception_message", "error_message", "err_msg"]
STACK_TRACE_ALIASES = ["stack_trace", "stack", "traceback", "exc_info", "stacktrace"]
FILE_ALIASES = ["source_file", "file", "filename", "src_file"]
LINE_ALIASES = ["line_number", "line", "lineno"]
CLASS_ALIASES = ["class_name", "class", "logger", "logger_name"]
METHOD_ALIASES = ["method_name", "method", "func", "function"]


class JsonLogParser(BaseLogParser):
    """
    Deterministic parser for JSON structured log objects, JSON arrays,
    and newline-delimited JSON (NDJSON).
    """

    name: str = "json_log_parser"

    def can_parse(self, content: str, file_type: str) -> bool:
        """Return True if file_type is 'json' or content begins with JSON delimiter."""
        stripped = content.lstrip("\ufeff").strip()
        if file_type == "json":
            return True
        return stripped.startswith("{") or stripped.startswith("[")

    def _get_field(self, obj: Dict[str, Any], aliases: List[str]) -> Optional[Any]:
        """Retrieve the first matching value from aliases dictionary lookup."""
        for alias in aliases:
            if alias in obj and obj[alias] is not None:
                val = obj[alias]
                # Return string or basic scalar; if empty string return None
                if isinstance(val, str) and not val.strip():
                    continue
                return val
        return None

    def _parse_timestamp(self, raw_val: Any) -> Optional[datetime]:
        """Safely parse various JSON timestamp representations into UTC datetime."""
        if not raw_val:
            return None
        try:
            if isinstance(raw_val, (int, float)):
                # Unix timestamp (seconds or milliseconds)
                if raw_val > 1e11:  # Milliseconds
                    return datetime.fromtimestamp(raw_val / 1000.0, tz=timezone.utc)
                return datetime.fromtimestamp(raw_val, tz=timezone.utc)
            if isinstance(raw_val, str):
                dt = dt_parser.parse(raw_val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        except Exception:
            return None
        return None

    def _parse_json_object(
        self, obj: Dict[str, Any], event_index: int, default_service: Optional[str]
    ) -> ParsedEventData:
        """Map a single JSON object to a ParsedEventData instance."""
        # 1. Timestamp
        raw_ts = self._get_field(obj, TIMESTAMP_ALIASES)
        timestamp = self._parse_timestamp(raw_ts)

        # 2. Level
        raw_level = self._get_field(obj, LEVEL_ALIASES)
        level: Optional[str] = None
        if isinstance(raw_level, str):
            clean_lvl = raw_level.strip().upper()
            level = KNOWN_LEVELS.get(clean_lvl, clean_lvl)

        # 3. Service
        raw_service = self._get_field(obj, SERVICE_ALIASES)
        service_name: Optional[str] = default_service
        if isinstance(raw_service, str) and raw_service.strip():
            service_name = raw_service.strip()

        # 4. Message
        raw_msg = self._get_field(obj, MESSAGE_ALIASES)
        if raw_msg is not None:
            message = str(raw_msg).strip()
        else:
            # Fallback: full JSON serialized representation
            message = json.dumps(obj)

        # 5. Exception Details
        raw_exc_type = self._get_field(obj, EXCEPTION_TYPE_ALIASES)
        exception_type: Optional[str] = None
        if isinstance(raw_exc_type, str):
            exception_type = raw_exc_type.strip()
        elif isinstance(raw_exc_type, dict):
            # Nested error object, e.g. {"name": "TypeError", "message": "..."}
            exception_type = raw_exc_type.get("type") or raw_exc_type.get("name")

        raw_exc_msg = self._get_field(obj, EXCEPTION_MSG_ALIASES)
        exception_message: Optional[str] = None
        if isinstance(raw_exc_msg, str):
            exception_message = raw_exc_msg.strip()
        elif isinstance(raw_exc_type, dict) and "message" in raw_exc_type:
            exception_message = str(raw_exc_type["message"]).strip()

        # 6. Stack Trace
        raw_stack = self._get_field(obj, STACK_TRACE_ALIASES)
        stack_trace: Optional[str] = None
        if isinstance(raw_stack, str) and raw_stack.strip():
            stack_trace = raw_stack.strip()
        elif isinstance(raw_stack, list):
            stack_trace = "\n".join(str(item) for item in raw_stack)

        # 7. File & Line
        raw_file = self._get_field(obj, FILE_ALIASES)
        source_file = str(raw_file).strip() if raw_file else None

        raw_line = self._get_field(obj, LINE_ALIASES)
        line_number: Optional[int] = None
        if raw_line is not None:
            try:
                line_number = int(raw_line)
            except (ValueError, TypeError):
                line_number = None

        # 8. Class & Method
        raw_class = self._get_field(obj, CLASS_ALIASES)
        class_name = str(raw_class).strip() if raw_class else None

        raw_method = self._get_field(obj, METHOD_ALIASES)
        method_name = str(raw_method).strip() if raw_method else None

        return ParsedEventData(
            event_index=event_index,
            message=message,
            timestamp=timestamp,
            level=level,
            service_name=service_name,
            exception_type=exception_type,
            exception_message=exception_message,
            class_name=class_name,
            method_name=method_name,
            source_file=source_file,
            line_number=line_number,
            stack_trace=stack_trace,
        )

    def parse(
        self,
        content: str,
        default_service: Optional[str] = None,
    ) -> ParseResult:
        """Parse JSON text into structured events."""
        clean_content = content.lstrip("\ufeff").strip()
        if not clean_content:
            return ParseResult(status="EMPTY", parser_name=self.name, events=[])

        parsed_objects: List[Dict[str, Any]] = []

        # Attempt 1: Full JSON parse (single object or array)
        try:
            full_json = json.loads(clean_content)
            if isinstance(full_json, dict):
                parsed_objects.append(full_json)
            elif isinstance(full_json, list):
                for item in full_json:
                    if isinstance(item, dict):
                        parsed_objects.append(item)
        except json.JSONDecodeError:
            # Attempt 2: Newline-delimited JSON (NDJSON)
            for line in clean_content.splitlines():
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    obj = json.loads(line_str)
                    if isinstance(obj, dict):
                        parsed_objects.append(obj)
                except json.JSONDecodeError:
                    pass

        if not parsed_objects:
            return ParseResult(
                status="UNSUPPORTED_FORMAT",
                parser_name=self.name,
                events=[
                    ParsedEventData(
                        event_index=0,
                        message=clean_content,
                        service_name=default_service,
                    )
                ],
            )

        events: List[ParsedEventData] = []
        structured_count = 0

        for idx, obj in enumerate(parsed_objects):
            parsed = self._parse_json_object(obj, idx, default_service)
            if parsed.timestamp or parsed.level or parsed.exception_type:
                structured_count += 1
            events.append(parsed)

        if structured_count == len(events):
            status = "SUCCESS"
        elif structured_count > 0:
            status = "PARTIAL"
        else:
            status = "UNSUPPORTED_FORMAT"

        return ParseResult(status=status, parser_name=self.name, events=events)
