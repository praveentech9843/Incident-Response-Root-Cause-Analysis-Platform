import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set
from app.models.parsed_log import ParsedLog
from app.correlation.rules import (
    extract_correlation_id,
    is_incident_worthy,
    generate_incident_title,
    calculate_correlation_metadata,
)


@dataclass
class CorrelationCluster:
    """Internal cluster representation during correlation processing."""

    events: List[ParsedLog]
    explicit_corr_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


@dataclass
class CorrelatedIncidentResult:
    """Final deterministic incident representation produced by the correlation engine."""

    incident_key: str
    title: str
    status: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    event_count: int
    service_count: int
    correlation_reason: str
    correlation_confidence: float
    events: List[ParsedLog]


class CorrelationEngine:
    """
    Deterministic Correlation Engine.
    Correlates parsed log events into incidents based on:
    1. Explicit correlation/request/trace identifiers
    2. Temporal proximity within a configurable sliding window
    3. Multi-service interactions and shared context
    Does NOT infer causality or determine root causes.
    """

    def __init__(self, default_window_seconds: int = 30):
        self.default_window_seconds = default_window_seconds

    def correlate(
        self,
        events: List[ParsedLog],
        window_seconds: Optional[int] = None,
    ) -> List[CorrelatedIncidentResult]:
        """
        Group parsed log events into correlated incident candidates deterministically.
        """
        if not events:
            return []

        active_window = window_seconds if window_seconds is not None else self.default_window_seconds

        # Sort events deterministically: timestamp asc (nulls last), log_id, event_index, id
        sorted_events = sorted(
            events,
            key=lambda e: (
                e.timestamp is None,
                e.timestamp or datetime.min,
                e.log_id,
                e.event_index,
                e.id,
            ),
        )

        clusters: List[CorrelationCluster] = []
        assigned_event_ids: Set[int] = set()

        # Step 1: Group by explicit correlation / request / trace ID
        corr_id_buckets: Dict[str, List[ParsedLog]] = {}
        for event in sorted_events:
            cid = extract_correlation_id(event)
            if cid:
                corr_id_buckets.setdefault(cid, []).append(event)

        for cid, group_events in corr_id_buckets.items():
            # An explicit correlation group becomes an incident only if it contains
            # at least one incident-worthy event (e.g. error, critical, or exception)
            if any(is_incident_worthy(e) for e in group_events):
                timestamps = [e.timestamp for e in group_events if e.timestamp is not None]
                s_at = min(timestamps) if timestamps else None
                e_at = max(timestamps) if timestamps else None
                clusters.append(
                    CorrelationCluster(
                        events=group_events,
                        explicit_corr_id=cid,
                        started_at=s_at,
                        ended_at=e_at,
                    )
                )
                for e in group_events:
                    assigned_event_ids.add(e.id)

        # Step 2: Temporal correlation for unassigned incident-worthy events
        # Normal INFO/DEBUG events without explicit IDs do NOT start incidents
        unassigned_error_events = [
            e for e in sorted_events
            if e.id not in assigned_event_ids and is_incident_worthy(e)
        ]

        temporal_clusters: List[CorrelationCluster] = []
        for event in unassigned_error_events:
            placed = False
            ev_ts = event.timestamp

            # Attempt to attach to existing temporal cluster within the window
            for cluster in temporal_clusters:
                cl_end = cluster.ended_at or cluster.started_at
                if ev_ts is not None and cl_end is not None:
                    diff_seconds = abs((ev_ts - cl_end).total_seconds())
                    if diff_seconds <= active_window:
                        cluster.events.append(event)
                        # Expand cluster time bounds
                        if cluster.started_at is None or ev_ts < cluster.started_at:
                            cluster.started_at = ev_ts
                        if cluster.ended_at is None or ev_ts > cluster.ended_at:
                            cluster.ended_at = ev_ts
                        placed = True
                        break
                elif ev_ts is None and cl_end is None:
                    # Neither has timestamps; check if from same log file and proximate index
                    last_ev = cluster.events[-1]
                    if last_ev.log_id == event.log_id and abs(event.event_index - last_ev.event_index) <= 10:
                        cluster.events.append(event)
                        placed = True
                        break

            if not placed:
                # Create a new temporal cluster
                temporal_clusters.append(
                    CorrelationCluster(
                        events=[event],
                        explicit_corr_id=None,
                        started_at=ev_ts,
                        ended_at=ev_ts,
                    )
                )

        clusters.extend(temporal_clusters)

        # Step 3: Convert clusters into deterministic CorrelatedIncidentResult entities
        results: List[CorrelatedIncidentResult] = []
        for cluster in clusters:
            if not cluster.events:
                continue

            # Deterministic sorting of constituent events
            ordered_events = sorted(
                cluster.events,
                key=lambda e: (
                    e.timestamp is None,
                    e.timestamp or datetime.min,
                    e.event_index,
                    e.id,
                ),
            )

            # Unique services
            services = sorted(list(set(e.service_name for e in ordered_events if e.service_name)))
            service_count = len(services)
            event_count = len(ordered_events)

            # Compute deterministic incident key
            sorted_event_ids = sorted([e.id for e in ordered_events])
            key_raw = f"inc:{','.join(str(i) for i in sorted_event_ids)}"
            incident_key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()

            # Metadata
            title = generate_incident_title(services, ordered_events)
            reason, confidence = calculate_correlation_metadata(
                ordered_events, cluster.explicit_corr_id, active_window
            )

            # Recalculate timestamps from ordered events
            ts_list = [e.timestamp for e in ordered_events if e.timestamp is not None]
            started_at = min(ts_list) if ts_list else None
            ended_at = max(ts_list) if ts_list else None

            results.append(
                CorrelatedIncidentResult(
                    incident_key=incident_key,
                    title=title,
                    status="OPEN",
                    started_at=started_at,
                    ended_at=ended_at,
                    event_count=event_count,
                    service_count=service_count,
                    correlation_reason=reason,
                    correlation_confidence=confidence,
                    events=ordered_events,
                )
            )

        # Sort results deterministically by started_at (nulls last), then incident_key
        results.sort(
            key=lambda r: (
                r.started_at is None,
                r.started_at or datetime.min,
                r.incident_key,
            )
        )

        return results
