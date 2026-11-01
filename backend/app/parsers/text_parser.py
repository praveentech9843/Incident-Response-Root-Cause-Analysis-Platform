import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from dateutil import parser as dt_parser

from app.parsers.base import BaseLogParser, ParsedEventData, ParseResult

# Standard normalized levels
KNOWN_LEVELS = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARN": "WARN",
    "WARNING": "WARN",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
    "FATAL": "FATAL",
    "TRACE": "TRACE",
}

# Regex for common timestamp patterns at start of line
# Supports:
# 2026-10-06 12:00:01
# 2026-10-06 12:00:01,123 or .123
# 2026-10-06T12:00:01Z or 2026-10-06T12:00:01.120Z or with offset
# Optional brackets: [2026-10-06 12:00:01]
TIMESTAMP_REGEX = re.compile(
    r"^[\ufeff\s]*\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?"
)

# Regex to detect log level anywhere near the timestamp or start of message
LEVEL_REGEX = re.compile(
    r"\b(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL|TRACE)\b",
    re.IGNORECASE,
)

# Regex for Java stack trace element:
# at com.example.InventoryService.reserve(InventoryService.java:65)
# at InventoryService.java:65
JAVA_FRAME_REGEX = re.compile(
    r"^\s*at\s+(?:(?P<class_prefix>[a-zA-Z0-9_$]+(?:\.[a-zA-Z0-9_$]+)*)\.)?(?P<method>[a-zA-Z0-9_$<>]+|new)\((?P<file>[a-zA-Z0-9_$.-]+\.(?:java|kt|scala|groovy))(?::(?P<line>\d+))?\)",
    re.MULTILINE,
)

# Inline Java reference: NullPointerException at InventoryService.java:65
INLINE_JAVA_LOC_REGEX = re.compile(
    r"\bat\s+(?P<file>[a-zA-Z0-9_$.-]+\.(?:java|kt|scala))(?::(?P<line>\d+))\b"
)

# Regex for Python traceback line:
# File "app/service.py", line 42, in process_order
PYTHON_FRAME_REGEX = re.compile(
    r'File\s+"(?P<file>[^"]+)",\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<method>\w+))?',
    re.MULTILINE,
)

# Regex for Python/Generic Exception header:
# KeyError: 'item_id' or ValueError: invalid literal or NullPointerException: message
EXCEPTION_HEADER_REGEX = re.compile(
    r"\b(?P<type>[a-zA-Z0-9_$.]*(?:Exception|Error|Fault|Failure|Throwable))\b(?::\s*(?P<msg>[^\n\r]+))?",
    re.MULTILINE,
)

# Node/JS stack trace: at Object.handler (/app/src/index.ts:45:12) or at foo (index.js:10:5)
NODE_FRAME_REGEX = re.compile(
    r"^\s*at\s+(?:(?P<method>[a-zA-Z0-9_$.<>]+)\s+)?\(?(?P<file>[a-zA-Z0-9_/\\.-]+\.(?:ts|js|mjs|cjs)):(?P<line>\d+)(?::\d+)?\)?",
    re.MULTILINE,
)

SERVICE_SUFFIXES = (
    "service",
    "gateway",
    "worker",
    "server",
    "client",
    "controller",
    "manager",
    "processor",
    "handler",
    "provider",
    "daemon",
    "microservice",
    "listener",
    "consumer",
    "producer",
    "dispatcher",
)

COMMON_MESSAGE_WORDS = {
    "the", "a", "an", "at", "in", "on", "for", "with", "from", "to", "of",
    "and", "or", "but", "is", "was", "are", "were", "been", "has", "have",
    "had", "failed", "error", "warning", "starting", "stopping", "started",
    "stopped", "received", "sending", "cannot", "could", "unable", "user",
    "connection", "general", "status", "system", "heartbeat", "retrying",
    "retry", "timeout", "request", "response", "thread", "process", "event",
    "exception", "trace", "step", "test", "operation", "action", "task",
    "job", "batch", "message", "payload", "query", "record", "data", "null",
}


def _is_service_token(
    token: str,
    rest_of_line: str,
    default_service: Optional[str] = None,
) -> bool:
    """
    Determine if a space-delimited token after log level represents a service/component name.
    """
    if not token or len(token) > 60:
        return False
    if token.isdigit() or not any(c.isalnum() for c in token):
        return False

    tok_lower = token.lower()

    # 1. Matches upload default_service
    if default_service and tok_lower == default_service.lower():
        return True

    # 2. Key-value pair follower indicates token is the logger/service component:
    # E.g. DatabaseService correlation_id=E2E-RCA-001 ...
    # E.g. OrderDB req_id=123 ...
    has_kv_follower = bool(re.match(r"^[a-zA-Z0-9_.-]+=\S+", rest_of_line.strip()))
    if has_kv_follower and tok_lower not in COMMON_MESSAGE_WORDS:
        return True

    # 3. Known service suffix or naming pattern:
    # E.g. DatabaseService, PaymentService, auth-service, payment_gateway, api-server
    for suffix in SERVICE_SUFFIXES:
        if tok_lower.endswith(suffix) and len(tok_lower) > len(suffix):
            return True
        if tok_lower.endswith(f"-{suffix}") or tok_lower.endswith(f"_{suffix}"):
            return True

    # 4. Specific known component prefixes or suffixes:
    # e.g. *-api, *-app, *-gw, *_api, *_app, *_gw
    if any(tok_lower.endswith(f"{sep}{abbr}") for sep in ("-", "_") for abbr in ("api", "app", "gw", "srv", "svc")):
        return True

    return False


class TextLogParser(BaseLogParser):
    """
    Deterministic parser for standard application text logs.
    Handles single-line logs, multi-line entries with stack traces,
    and partial/unstructured log content without guessing.
    """

    name: str = "text_log_parser"

    def can_parse(self, content: str, file_type: str) -> bool:
        """Text parser handles .log and .txt files, or any plain text stream."""
        stripped = content.lstrip("\ufeff").strip()
        return file_type in {"log", "txt"} or not stripped.startswith("{")

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        """Safely parse a timestamp string into a timezone-aware datetime."""
        try:
            # Replace comma with period for milliseconds
            clean_ts = ts_str.strip("[]").replace(",", ".")
            dt = dt_parser.parse(clean_ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def _extract_exception_and_location(
        self, text: str
    ) -> Tuple[
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[int],
    ]:
        """
        Extract exception type, exception message, class name, method name,
        source file, and line number from log text / stack trace.
        """
        exc_type: Optional[str] = None
        exc_msg: Optional[str] = None
        class_name: Optional[str] = None
        method_name: Optional[str] = None
        source_file: Optional[str] = None
        line_num: Optional[int] = None

        # 1. Exception Type & Message
        exc_match = EXCEPTION_HEADER_REGEX.search(text)
        if exc_match:
            full_type = exc_match.group("type")
            # Strip package prefix if present, e.g. java.lang.NullPointerException -> NullPointerException
            exc_type = full_type.split(".")[-1]
            raw_msg = exc_match.group("msg")
            if raw_msg:
                exc_msg = raw_msg.strip()

        # 2. Java Stack Frame (first frame in trace usually points to the caller/error)
        java_match = JAVA_FRAME_REGEX.search(text)
        if java_match:
            prefix = java_match.group("class_prefix")
            if prefix:
                class_name = prefix.split(".")[-1]
            method_name = java_match.group("method")
            source_file = java_match.group("file")
            line_str = java_match.group("line")
            if line_str:
                line_num = int(line_str)
        else:
            # Check inline Java location: "at InventoryService.java:65"
            inline_loc = INLINE_JAVA_LOC_REGEX.search(text)
            if inline_loc:
                source_file = inline_loc.group("file")
                line_str = inline_loc.group("line")
                if line_str:
                    line_num = int(line_str)
                if not class_name and source_file:
                    class_name = source_file.split(".")[0]

        # 3. Python Stack Frame
        if not source_file:
            # Find the last File "...", line frame in Python trace
            py_matches = list(PYTHON_FRAME_REGEX.finditer(text))
            if py_matches:
                last_frame = py_matches[-1]
                source_file = last_frame.group("file")
                line_str = last_frame.group("line")
                if line_str:
                    line_num = int(line_str)
                method_name = last_frame.group("method")

        # 4. Node / JS Frame
        if not source_file:
            node_match = NODE_FRAME_REGEX.search(text)
            if node_match:
                source_file = node_match.group("file")
                line_str = node_match.group("line")
                if line_str:
                    line_num = int(line_str)
                method_name = node_match.group("method")

        return exc_type, exc_msg, class_name, method_name, source_file, line_num

    def _split_into_raw_entries(self, content: str) -> List[str]:
        """
        Group consecutive lines belonging to the same log entry.
        Lines beginning with a timestamp or level mark a new entry;
        subsequent indented or continuation lines are grouped into the same entry.
        """
        clean_content = content.lstrip("\ufeff")
        lines = clean_content.split("\n")
        entries: List[List[str]] = []
        current_entry: List[str] = []

        for line in lines:
            clean_line = line.lstrip("\ufeff")
            if not clean_line.strip():
                if current_entry:
                    current_entry.append(clean_line)
                continue

            # Check if this line looks like a new entry start:
            # Begins with timestamp, or starts with bracketed/unbracketed level
            has_timestamp = bool(TIMESTAMP_REGEX.match(clean_line.strip()))
            is_continuation = (
                clean_line.startswith(" ")
                or clean_line.startswith("\t")
                or clean_line.strip().startswith("at ")
                or clean_line.strip().startswith("Caused by:")
                or clean_line.strip().startswith("File ")
                or clean_line.strip().startswith("Traceback")
            )

            if has_timestamp or (not is_continuation and not current_entry):
                if current_entry:
                    entries.append(current_entry)
                current_entry = [clean_line]
            elif current_entry and is_continuation:
                current_entry.append(clean_line)
            else:
                # If current_entry exists and the line doesn't have a timestamp,
                # check if line starts with a log level:
                level_match = LEVEL_REGEX.search(clean_line[:30])
                if level_match and not is_continuation:
                    if current_entry:
                        entries.append(current_entry)
                    current_entry = [clean_line]
                else:
                    if current_entry:
                        current_entry.append(clean_line)
                    else:
                        current_entry = [clean_line]

        if current_entry:
            entries.append(current_entry)

        return ["\n".join(entry_lines).strip() for entry_lines in entries if "".join(entry_lines).strip()]

    def _parse_single_entry(
        self, raw_entry: str, event_index: int, default_service: Optional[str]
    ) -> ParsedEventData:
        """Parse a single raw multi-line log entry into a ParsedEventData."""
        clean_raw_entry = raw_entry.lstrip("\ufeff")
        first_line = clean_raw_entry.split("\n")[0].strip()

        timestamp: Optional[datetime] = None
        level: Optional[str] = None
        service_name: Optional[str] = default_service
        message: str = clean_raw_entry

        # 1. Timestamp extraction
        ts_match = TIMESTAMP_REGEX.search(first_line)
        remaining_header = first_line
        if ts_match:
            raw_ts = ts_match.group(1)
            timestamp = self._parse_timestamp(raw_ts)
            remaining_header = first_line[ts_match.end() :].strip()
        else:
            # Fallback timestamp search if not anchored at exact beginning
            fallback_ts = re.search(
                r"\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\]?",
                first_line,
            )
            if fallback_ts and fallback_ts.start() < 30:
                raw_ts = fallback_ts.group(1)
                timestamp = self._parse_timestamp(raw_ts)
                remaining_header = (
                    first_line[: fallback_ts.start()] + " " + first_line[fallback_ts.end() :]
                ).strip()

        # 2. Level extraction
        level_match = LEVEL_REGEX.search(remaining_header)
        if level_match:
            raw_lvl = level_match.group(1).upper()
            level = KNOWN_LEVELS.get(raw_lvl, raw_lvl)
            # Remove level from header to parse service and message
            before_lvl = remaining_header[: level_match.start()].strip(" []-:")
            after_lvl = remaining_header[level_match.end() :].strip(" []-:")

            # Guard: ensure before_lvl is not an unconsumed timestamp
            if before_lvl and re.search(r"\d{4}-\d{2}-\d{2}", before_lvl):
                if timestamp is None:
                    ts_sub = re.search(
                        r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)",
                        before_lvl,
                    )
                    if ts_sub:
                        timestamp = self._parse_timestamp(ts_sub.group(1))
                before_lvl = ""

            # 3. Service name & message extraction
            # Patterns supported:
            # - <ts> <service> <lvl> <msg>
            # - <ts> <lvl> [service] <msg>
            # - <ts> <lvl> service: <msg>
            # - <ts> <lvl> service - <msg>
            # - <ts> <lvl> ServiceName <msg> (validated by _is_service_token)
            service_candidate: Optional[str] = None
            message_extracted: Optional[str] = None
            extra_lines = clean_raw_entry.split("\n")[1:]

            if before_lvl and not before_lvl.startswith("[") and len(before_lvl) < 60:
                service_candidate = before_lvl
                message_extracted = after_lvl
            elif after_lvl:
                bracket_m = re.match(r"^\[([a-zA-Z0-9_.-]+)\]\s*(.*)$", after_lvl)
                colon_m = re.match(r"^([a-zA-Z0-9_.-]+)\s*:\s*(.*)$", after_lvl)
                dash_m = re.match(r"^([a-zA-Z0-9_.-]+)\s+-\s+(.*)$", after_lvl)
                space_m = re.match(r"^([a-zA-Z0-9_.-]+)\s+(.*)$", after_lvl)

                if bracket_m and len(bracket_m.group(1)) < 60:
                    service_candidate = bracket_m.group(1).strip()
                    message_extracted = bracket_m.group(2).strip()
                elif colon_m and len(colon_m.group(1)) < 60 and " " not in colon_m.group(1):
                    service_candidate = colon_m.group(1).strip()
                    message_extracted = colon_m.group(2).strip()
                elif dash_m and len(dash_m.group(1)) < 60 and " " not in dash_m.group(1):
                    service_candidate = dash_m.group(1).strip()
                    message_extracted = dash_m.group(2).strip()
                elif space_m and _is_service_token(space_m.group(1), space_m.group(2), default_service):
                    service_candidate = space_m.group(1).strip()
                    message_extracted = space_m.group(2).strip()
                else:
                    message_extracted = after_lvl

            if service_candidate:
                service_name = service_candidate

            if message_extracted is not None:
                message = (message_extracted + "\n" + "\n".join(extra_lines)).strip() if extra_lines else message_extracted

        # 4. Stack trace / Exception details extraction
        (
            exc_type,
            exc_msg,
            class_name,
            method_name,
            source_file,
            line_num,
        ) = self._extract_exception_and_location(clean_raw_entry)

        # 5. Stack trace preservation
        stack_trace: Optional[str] = None
        if "\n" in clean_raw_entry and (
            "at " in clean_raw_entry
            or "Traceback" in clean_raw_entry
            or "Exception" in clean_raw_entry
            or "Error" in clean_raw_entry
        ):
            stack_trace = clean_raw_entry

        return ParsedEventData(
            event_index=event_index,
            message=message.strip(),
            timestamp=timestamp,
            level=level,
            service_name=service_name,
            exception_type=exc_type,
            exception_message=exc_msg,
            class_name=class_name,
            method_name=method_name,
            source_file=source_file,
            line_number=line_num,
            stack_trace=stack_trace,
        )

    def parse(
        self,
        content: str,
        default_service: Optional[str] = None,
    ) -> ParseResult:
        """Parse text log content into a list of structured events."""
        clean_content = content.lstrip("\ufeff").strip()
        if not clean_content:
            return ParseResult(status="EMPTY", parser_name=self.name, events=[])

        raw_entries = self._split_into_raw_entries(clean_content)
        if not raw_entries:
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

        for idx, entry in enumerate(raw_entries):
            parsed = self._parse_single_entry(entry, idx, default_service)
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
