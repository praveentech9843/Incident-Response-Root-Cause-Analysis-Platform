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


class DependencyContextProvider(ContextProvider):
    """
    Derives dependency and service participation context strictly from correlated events.
    Strictly preserves the principle: CORRELATION IS NOT CAUSATION.
    Does NOT infer causal directionality or claim service dependency failures without verified topology.
    """

    @property
    def category(self) -> ContextCategory:
        return ContextCategory.DEPENDENCIES

    def collect(
        self,
        incident: Incident,
        events: List[ParsedLog],
        db: Session,
    ) -> ContextResult:
        # Collect distinct services involved in the incident events
        services_set = set()
        observed_sequence = []

        for e in events:
            if e.service_name and e.service_name.strip():
                svc = e.service_name.strip()
                services_set.add(svc)
                if not observed_sequence or observed_sequence[-1] != svc:
                    observed_sequence.append(svc)

        services_involved = sorted(list(services_set))

        # Build observed temporal co-occurrences without claiming causality
        observed_co_occurrences = []
        for i in range(len(observed_sequence) - 1):
            pair = (observed_sequence[i], observed_sequence[i + 1])
            if pair[0] != pair[1] and pair not in observed_co_occurrences:
                observed_co_occurrences.append(pair)

        data = {
            "services_involved": services_involved,
            "service_count": len(services_involved),
            "observed_co_occurring_pairs": [
                {"service_a": p[0], "service_b": p[1], "relation": "TEMPORAL_CO_OCCURRENCE"}
                for p in observed_co_occurrences
            ],
            "causal_graph": None,
            "causality_status": "UNVERIFIED",
            "correlation_vs_causation_notice": (
                "Correlation is NOT causation. Services listed reflect concurrent or temporal co-occurrence "
                "within the incident window. No causal direction or dependency tree is asserted in Phase 4."
            ),
        }

        return ContextResult(
            category=self.category,
            status=ContextStatus.AVAILABLE if services_involved else ContextStatus.UNAVAILABLE,
            data=data,
            source="incident_events",
        )
