from enum import Enum
from typing import Any, Dict


class IntegrationStatus(str, Enum):
    CONNECTED = "CONNECTED"
    NOT_CONNECTED = "NOT_CONNECTED"
    UNAVAILABLE = "UNAVAILABLE"
    INTEGRATION_REQUIRED = "INTEGRATION_REQUIRED"
    ERROR = "ERROR"


class BaseIntegrationProvider:
    """Base class for all real external integration providers."""

    def __init__(self, name: str):
        self.name = name

    def get_status(self) -> Dict[str, Any]:
        raise NotImplementedError
