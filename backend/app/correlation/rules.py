import re
from typing import Optional, List, Set
from app.models.parsed_log import ParsedLog

# Regex patterns for extracting explicit correlation, trace, or request identifiers
CORRELATION_PATTERNS = [
    # Key-value or tagged style: correlation_id=abc, [req:req-9821], [run:run_123], trace_id=xyz
    re.compile(
        r"(?i)(?:\[|\b)(?:run|request_id|correlation_id|trace_id|transaction_id|req_id|x_request_id|request|correlation|trace|transaction|req|tx)[\s:=]+[\"']?([a-zA-Z0-9_\-]+)[\"']?(?:\]|\b)?"
    ),
    # Prefixed identifier tokens: req_123, req-123, corr_abc, trace-xyz, tx_99
    re.compile(
        r"\b((?:req|corr|trace|tx)[_\-][a-zA-Z0-9_\-]+)\b",
        re.IGNORECASE,
    ),
]

ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}


def extract_correlation_id(event: ParsedLog) -> Optional[str]:
    """
    Extract an explicit correlation, request, trace, or transaction ID
    from the event message or stack trace if present.
    """
    # Check message first
    if event.message:
        for pattern in CORRELATION_PATTERNS:
            match = pattern.search(event.message)
            if match:
                return match.group(1).strip()

    # Check stack trace
    if event.stack_trace:
        for pattern in CORRELATION_PATTERNS:
            match = pattern.search(event.stack_trace)
            if match:
                return match.group(1).strip()

    return None


def is_incident_worthy(event: ParsedLog) -> bool:
    """
    Determine if an individual event is sufficiently critical to act as an incident trigger.
    Only ERROR, CRITICAL, FATAL events, or events with exceptions, can independently trigger incidents.
    Informational/Debug logs never independently initiate an incident.
    """
    if event.level and event.level.upper() in ERROR_LEVELS:
        return True
    if event.exception_type is not None:
        return True
    return False


def generate_incident_title(services: List[str], events: List[ParsedLog]) -> str:
    """
    Generate a deterministic incident title based strictly on available event evidence.
    Does NOT infer causality or designate any service as root cause.
    """
    clean_services = sorted(list(set(s for s in services if s)))
    
    if len(clean_services) > 1:
        return f"Correlated errors across {', '.join(clean_services)}"
    elif len(clean_services) == 1:
        svc = clean_services[0]
        # Check if there is a dominant exception type
        exceptions = [e.exception_type for e in events if e.exception_type]
        if exceptions:
            return f"{svc}: Correlated {exceptions[0]} failure"
        return f"{svc}: Correlated error event cluster"
    else:
        exceptions = [e.exception_type for e in events if e.exception_type]
        if exceptions:
            return f"Correlated {exceptions[0]} failure cluster"
        return "Correlated system error event cluster"


def calculate_correlation_metadata(
    events: List[ParsedLog],
    explicit_corr_id: Optional[str],
    window_seconds: int,
) -> tuple[str, float]:
    """
    Calculate explainable correlation reason and deterministic confidence score.
    Returns (correlation_reason, correlation_confidence).
    """
    services = sorted(list(set(e.service_name for e in events if e.service_name)))
    service_count = len(services)
    event_count = len(events)

    if explicit_corr_id:
        if service_count > 1:
            reason = (
                f"Events share explicit correlation ID '{explicit_corr_id}' "
                f"across {service_count} services ({', '.join(services)})."
            )
        else:
            reason = f"Events share explicit correlation ID '{explicit_corr_id}'."
        return reason, 0.95

    if service_count > 1:
        reason = (
            f"Multi-service error events across {', '.join(services)} "
            f"occurred within the configured {window_seconds}s correlation window."
        )
        return reason, 0.85

    if event_count > 1:
        reason = (
            f"Events occurred within the configured {window_seconds}-second "
            f"temporal correlation window."
        )
        return reason, 0.75

    # Single event
    lvl = events[0].level or "ERROR"
    reason = f"Single isolated {lvl} event exceeding incident threshold."
    return reason, 0.70
