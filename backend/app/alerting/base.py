from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Tuple


class NotificationStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    NOT_CONNECTED = "NOT_CONNECTED"


class NotificationProvider(ABC):
    """Abstract interface for external notification delivery."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def send_notification(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Dict[str, Any],
    ) -> Tuple[NotificationStatus, str]:
        """
        Sends notification and returns (NotificationStatus, response_or_error_message).
        """
        pass
