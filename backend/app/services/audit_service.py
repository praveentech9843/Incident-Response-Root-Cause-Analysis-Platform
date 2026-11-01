import json
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.models.audit_log import SecurityAuditLog
from app.core.logging import get_logger

logger = get_logger("audit_service")


def log_audit_event(
    db: Session,
    actor: str,
    action: str,
    target_entity: str,
    target_id: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> SecurityAuditLog:
    """
    Append an immutable audit entry to security_audit_logs.
    """
    metadata_json = None
    if metadata is not None:
        try:
            metadata_json = json.dumps(metadata)
        except Exception as e:
            metadata_json = json.dumps({"serialization_error": str(e)})

    audit_entry = SecurityAuditLog(
        actor=actor,
        action=action,
        target_entity=target_entity,
        target_id=str(target_id) if target_id is not None else None,
        request_id=request_id,
        metadata_json=metadata_json,
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    logger.info(
        "AUDIT [%s] actor='%s' action='%s' target='%s:%s' req='%s'",
        audit_entry.id,
        actor,
        action,
        target_entity,
        target_id,
        request_id,
    )
    return audit_entry
