from typing import List, Optional
from app.parsers.base import BaseLogParser
from app.parsers.json_parser import JsonLogParser
from app.parsers.text_parser import TextLogParser


class ParserRegistry:
    """Registry managing available log parsers and selecting the best match."""

    def __init__(self):
        self._parsers: List[BaseLogParser] = [
            JsonLogParser(),
            TextLogParser(),
        ]

    def get_parser(self, content: str, file_type: str) -> BaseLogParser:
        """Find the most appropriate parser for the provided log content."""
        clean_content = content.strip()
        # Fast path: JSON files or content starting with JSON braces
        if file_type == "json" or clean_content.startswith("{") or clean_content.startswith("["):
            json_parser = self._parsers[0]
            if json_parser.can_parse(content, file_type):
                return json_parser

        # Check all registered parsers
        for parser in self._parsers:
            if parser.can_parse(content, file_type):
                return parser

        # Fallback to TextLogParser
        return self._parsers[1]


# Global singleton registry
default_registry = ParserRegistry()
