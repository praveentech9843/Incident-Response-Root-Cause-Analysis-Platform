from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from app.models.incident import Incident
from app.models.parsed_log import ParsedLog
from app.models.incident_context import IncidentContext
from app.rca.schemas import RCAEvidenceItem, EvidenceType


class RCAEvidencePackage(BaseModel):
    """
    Controlled evidence package constructed deterministically for Root Cause Analysis.
    Only contains real, observed data. Unconnected systems are explicitly marked unavailable.
    """

    incident: Dict[str, Any]
    service_names: List[str]
    observed_evidence_items: List[RCAEvidenceItem] = Field(default_factory=list)
    unavailable_contexts: List[Dict[str, Any]] = Field(default_factory=list)
    total_events: int = 0
    total_observed_evidence: int = 0

    def get_observed_evidence_ids(self) -> Set[str]:
        return {item.evidence_id for item in self.observed_evidence_items if item.is_available}

    def get_known_services(self) -> Set[str]:
        return set(self.service_names)

    def to_snapshot(self) -> Dict[str, Any]:
        """Serialize full evidence package into audit snapshot."""
        return self.model_dump(mode="json")


class RCAEvidenceBuilder:
    """
    Constructs a normalized, deterministic RCAEvidencePackage from PostgreSQL incident records.
    Never invents evidence or converts unverified integrations into facts.
    """

    @classmethod
    def build(
        cls,
        incident: Incident,
        events: List[ParsedLog],
        contexts: List[IncidentContext],
    ) -> RCAEvidencePackage:
        evidence_items: List[RCAEvidenceItem] = []
        unavailable_contexts: List[Dict[str, Any]] = []

        # 1. Services present across events
        services_set: Set[str] = set()
        for e in events:
            if e.service_name and e.service_name.strip():
                services_set.add(e.service_name.strip())

        # 2. Extract Event, Exception, and Stack Trace Evidence
        for e in events:
            evt_id = f"EVT-{e.id}"
            evt_desc = f"Log event from {e.service_name or 'Unknown'}: [{e.level or 'UNKNOWN'}] {e.message or ''}"
            evidence_items.append(
                RCAEvidenceItem(
                    evidence_id=evt_id,
                    evidence_type=EvidenceType.LOG_EVENT,
                    source="parsed_logs",
                    is_available=True,
                    description=evt_desc.strip(),
                    details={
                        "event_id": e.id,
                        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                        "level": e.level,
                        "service_name": e.service_name,
                        "message": e.message,
                        "class_name": e.class_name,
                        "method_name": e.method_name,
                        "source_file": e.source_file,
                        "line_number": e.line_number,
                    },
                    db_reference={"parsed_log_id": e.id, "log_id": e.log_id},
                )
            )

            # Exception evidence
            if e.exception_type or e.exception_message:
                exc_id = f"EXC-{e.id}"
                exc_desc = f"Exception in {e.service_name or 'service'}: {e.exception_type or 'Exception'}: {e.exception_message or ''}"
                evidence_items.append(
                    RCAEvidenceItem(
                        evidence_id=exc_id,
                        evidence_type=EvidenceType.EXCEPTION,
                        source="parsed_logs",
                        is_available=True,
                        description=exc_desc.strip(),
                        details={
                            "event_id": e.id,
                            "exception_type": e.exception_type,
                            "exception_message": e.exception_message,
                        },
                        db_reference={"parsed_log_id": e.id, "log_id": e.log_id},
                    )
                )

            # Stack trace evidence
            if e.stack_trace:
                st_id = f"ST-{e.id}"
                snippet = (e.stack_trace[:300] + "...") if len(e.stack_trace) > 300 else e.stack_trace
                evidence_items.append(
                    RCAEvidenceItem(
                        evidence_id=st_id,
                        evidence_type=EvidenceType.STACK_TRACE,
                        source="parsed_logs",
                        is_available=True,
                        description=f"Stack trace frame for {e.service_name or 'service'}: {snippet}".strip(),
                        details={
                            "event_id": e.id,
                            "stack_trace": e.stack_trace,
                        },
                        db_reference={"parsed_log_id": e.id, "log_id": e.log_id},
                    )
                )

        # 3. Extract Phase 4 Context Evidence
        for ctx in contexts:
            category = ctx.context_category.lower()
            status = ctx.status
            data = ctx.data or {}

            if status == "AVAILABLE":
                if category == "service":
                    evidence_items.append(
                        RCAEvidenceItem(
                            evidence_id=f"CTX-SERVICE-{ctx.id}",
                            evidence_type=EvidenceType.SERVICE_CONTEXT,
                            source=ctx.source,
                            is_available=True,
                            description=f"Observed participating services: {', '.join(data.get('services_involved', []))}",
                            details=data,
                            db_reference={"incident_context_id": ctx.id, "category": "service"},
                        )
                    )
                    # Add any additional services found in context
                    for s in data.get("services_involved", []):
                        if s:
                            services_set.add(s)

                elif category == "history":
                    evidence_items.append(
                        RCAEvidenceItem(
                            evidence_id=f"CTX-HISTORY-{ctx.id}",
                            evidence_type=EvidenceType.HISTORY,
                            source=ctx.source,
                            is_available=True,
                            description=(
                                f"Historical occurrences: {data.get('previous_occurrence_count', 0)} prior incidents, "
                                f"recurring={data.get('recurring', False)}"
                            ),
                            details=data,
                            db_reference={"incident_context_id": ctx.id, "category": "history"},
                        )
                    )

                elif category == "dependencies":
                    evidence_items.append(
                        RCAEvidenceItem(
                            evidence_id=f"CTX-DEPS-{ctx.id}",
                            evidence_type=EvidenceType.DEPENDENCY_OBSERVATION,
                            source=ctx.source,
                            is_available=True,
                            description=(
                                f"Observed co-occurring services: {', '.join(data.get('services_involved', []))} "
                                f"(Causality: {data.get('causality_status', 'UNVERIFIED')})"
                            ),
                            details=data,
                            db_reference={"incident_context_id": ctx.id, "category": "dependencies"},
                        )
                    )
            else:
                # Explicitly record unavailable contexts
                unavailable_contexts.append({
                    "category": category,
                    "status": status,
                    "reason": data.get("message", f"{category.capitalize()} integration {status.lower().replace('_', ' ')}"),
                    "source": ctx.source,
                })

        incident_data = {
            "id": incident.id,
            "incident_key": incident.incident_key,
            "title": incident.title,
            "status": incident.status,
            "started_at": incident.started_at.isoformat() if incident.started_at else None,
            "ended_at": incident.ended_at.isoformat() if incident.ended_at else None,
            "event_count": incident.event_count,
            "service_count": incident.service_count,
            "correlation_reason": incident.correlation_reason,
            "correlation_confidence": incident.correlation_confidence,
        }

        return RCAEvidencePackage(
            incident=incident_data,
            service_names=sorted(list(services_set)),
            observed_evidence_items=evidence_items,
            unavailable_contexts=unavailable_contexts,
            total_events=len(events),
            total_observed_evidence=len(evidence_items),
        )
