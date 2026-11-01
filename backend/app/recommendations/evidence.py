from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from app.models.incident import Incident
from app.models.incident_rca import IncidentRCAAnalysis


class RecommendationInput(BaseModel):
    """
    Controlled input context provided to the Recommendation engine.
    Constructed exclusively from a validated Phase 5 RCA analysis record
    and its immutable evidence snapshot.
    """

    incident_id: int
    incident_key: str
    incident_title: str
    rca_id: int
    rca_analysis_id: str
    rca_status: str
    rca_summary: str
    hypotheses: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_snapshot: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    services_involved: List[str] = Field(default_factory=list)
    unavailable_contexts: List[Dict[str, Any]] = Field(default_factory=list)

    def get_observed_evidence_ids(self) -> Set[str]:
        """Extracts all valid, observed evidence IDs present in the RCA evidence snapshot."""
        valid_ids: Set[str] = set()

        # Check observed_evidence_items in snapshot
        observed_items = self.evidence_snapshot.get("observed_evidence_items", [])
        for item in observed_items:
            if isinstance(item, dict) and "evidence_id" in item:
                valid_ids.add(item["evidence_id"])

        # Check events in snapshot
        events = self.evidence_snapshot.get("events", [])
        for evt in events:
            if isinstance(evt, dict):
                if "event_id" in evt:
                    valid_ids.add(f"EVT-{evt['event_id']}")
                if "db_id" in evt:
                    valid_ids.add(f"EVT-{evt['db_id']}")

        # Check hypotheses supporting evidence
        for hyp in self.hypotheses:
            if isinstance(hyp, dict):
                for ev_id in hyp.get("supporting_evidence", []):
                    valid_ids.add(ev_id)

        return valid_ids

    def get_known_services(self) -> Set[str]:
        """Extracts all valid service names associated with this incident."""
        services = set(self.services_involved)
        events = self.evidence_snapshot.get("events", [])
        for evt in events:
            if isinstance(evt, dict) and evt.get("service_name"):
                services.add(evt["service_name"])
        return services

    def is_insufficient_evidence(self) -> bool:
        """Returns True if the underlying RCA had insufficient evidence."""
        return (
            self.rca_status == "INSUFFICIENT_EVIDENCE"
            or len(self.hypotheses) == 0
            or len(self.get_observed_evidence_ids()) == 0
        )


class RecommendationEvidenceBuilder:
    """Builder that extracts and formats RecommendationInput from verified DB entities."""

    @staticmethod
    def build(incident: Incident, rca_analysis: IncidentRCAAnalysis) -> RecommendationInput:
        snapshot = rca_analysis.evidence_snapshot or {}
        services = snapshot.get("services_involved", [])
        if not services and snapshot.get("incident"):
            services = snapshot["incident"].get("services_involved", [])

        unavailable = snapshot.get("unavailable_contexts", [])

        return RecommendationInput(
            incident_id=incident.id,
            incident_key=incident.incident_key,
            incident_title=incident.title,
            rca_id=rca_analysis.id,
            rca_analysis_id=rca_analysis.analysis_id,
            rca_status=rca_analysis.analysis_status,
            rca_summary=rca_analysis.summary,
            hypotheses=rca_analysis.hypotheses or [],
            evidence_snapshot=snapshot,
            limitations=rca_analysis.limitations or [],
            services_involved=services,
            unavailable_contexts=unavailable,
        )
