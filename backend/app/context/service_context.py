from typing import List
from sqlalchemy.orm import Session

from app.context.base import (
    ContextProvider,
    ContextCategory,
    ContextStatus,
    ContextResult,
)
from app.models.incident import Incident
from app.models.parsed_log import ParsedLog


class ServiceContextProvider(ContextProvider):
    """
    Derives service context strictly from existing parsed and correlated log data.
    Does NOT invent service owners, repositories, runtimes, or languages.
    """

    @property
    def category(self) -> ContextCategory:
        return ContextCategory.SERVICE

    def collect(
        self,
        incident: Incident,
        events: List[ParsedLog],
        db: Session,
    ) -> ContextResult:
        # Extract unique service names observed across correlated events
        observed_services = set()
        for e in events:
            if e.service_name and e.service_name.strip():
                observed_services.add(e.service_name.strip())

        service_list = sorted(list(observed_services))
        primary_service = service_list[0] if service_list else None

        # Check if any service was discovered
        status = ContextStatus.AVAILABLE if service_list else ContextStatus.UNAVAILABLE

        data = {
            "service_name": primary_service,
            "services_involved": service_list,
            "service_count": len(service_list),
            "language": None,
            "framework": None,
            "owner": None,
            "team": None,
            "repository": None,
            "runtime": None,
            "field_availability": {
                "service_name": ContextStatus.AVAILABLE.value if primary_service else ContextStatus.UNAVAILABLE.value,
                "language": ContextStatus.UNAVAILABLE.value,
                "framework": ContextStatus.UNAVAILABLE.value,
                "owner": ContextStatus.NOT_CONNECTED.value,
                "team": ContextStatus.NOT_CONNECTED.value,
                "repository": ContextStatus.NOT_CONNECTED.value,
                "runtime": ContextStatus.UNAVAILABLE.value,
            },
            "source_details": "Derived strictly from constituent parsed log event service_name fields",
        }

        return ContextResult(
            category=self.category,
            status=status,
            data=data,
            source="parsed_logs",
        )
