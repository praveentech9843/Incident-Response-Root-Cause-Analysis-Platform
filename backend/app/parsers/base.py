from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ParsedEventData:
    """Internal data representation of an extracted log event."""

    event_index: int
    message: str
    timestamp: Optional[datetime] = None
    level: Optional[str] = None
    service_name: Optional[str] = None
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    stack_trace: Optional[str] = None


@dataclass
class ParseResult:
    """Result of parsing raw log content."""

    status: str  # "SUCCESS", "PARTIAL", "UNSUPPORTED_FORMAT"
    parser_name: str
    events: List[ParsedEventData] = field(default_factory=list)


class BaseLogParser(ABC):
    """Abstract base class for all log parsers."""

    name: str = "base_parser"

    @abstractmethod
    def can_parse(self, content: str, file_type: str) -> bool:
        """Return True if this parser can interpret the given content or file type."""
        pass

    @abstractmethod
    def parse(
        self,
        content: str,
        default_service: Optional[str] = None,
    ) -> ParseResult:
        """Parse raw content into structured events."""
        pass
