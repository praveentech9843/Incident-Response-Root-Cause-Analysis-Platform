from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.core.database import get_db
from app.core.security import Role
from app.models.audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.audit import AuditLogListResponse, AuditLogResponse

router = APIRouter()


@router.get("/logs", response_model=AuditLogListResponse)
def list_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    target_entity: Optional[str] = Query(None),
    current_user: User = Depends(require_roles([Role.ADMIN.value])),
    db: Session = Depends(get_db),
):
    """
    Admin-only append-only security and operational audit trail.
    Supports filtering by actor, action, and target_entity with pagination.
    """
    query = db.query(SecurityAuditLog)
    if actor:
        query = query.filter(SecurityAuditLog.actor == actor)
    if action:
        query = query.filter(SecurityAuditLog.action == action)
    if target_entity:
        query = query.filter(SecurityAuditLog.target_entity == target_entity)

    total = query.count()
    logs = query.order_by(SecurityAuditLog.id.desc()).offset(offset).limit(limit).all()

    return AuditLogListResponse(
        total=total,
        logs=[AuditLogResponse.model_validate(log) for log in logs],
    )
