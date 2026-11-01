from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.alerting.engine import evaluate_incident_alerts
from app.api.dependencies.auth import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import Role
from app.models.alerting import IncidentAlert, IncidentAlertRule, IncidentNotification
from app.models.incident import Incident
from app.models.user import User
from app.schemas.alerting import (
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleResponse,
    IncidentAlertListResponse,
    IncidentAlertResponse,
    IncidentNotificationResponse,
    NotificationListResponse,
)
from app.services.audit_service import log_audit_event

router = APIRouter()


@router.get("/rules", response_model=AlertRuleListResponse)
def list_alert_rules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all alert rules."""
    rules = db.query(IncidentAlertRule).order_by(IncidentAlertRule.id.asc()).all()
    return AlertRuleListResponse(
        total=len(rules),
        rules=[AlertRuleResponse.model_validate(r) for r in rules],
    )


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
def create_alert_rule(
    req: AlertRuleCreate,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value])),
    db: Session = Depends(get_db),
):
    """Admin-only creation of alert rules."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    rule = IncidentAlertRule(
        name=req.name,
        severity_trigger=req.severity_trigger,
        escalation_minutes=req.escalation_minutes,
        channel=req.channel,
        target=req.target,
        is_active=req.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    log_audit_event(
        db=db,
        actor=current_user.username,
        action="ALERT_RULE_CREATE",
        target_entity="ALERT_RULE",
        target_id=str(rule.id),
        request_id=request_id,
        metadata={"name": rule.name, "channel": rule.channel},
    )

    return AlertRuleResponse.model_validate(rule)


@router.get("", response_model=IncidentAlertListResponse)
def list_alerts(
    incident_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List generated incident alerts with deduplication status."""
    query = db.query(IncidentAlert)
    if incident_id is not None:
        query = query.filter(IncidentAlert.incident_id == incident_id)

    total = query.count()
    alerts = query.order_by(IncidentAlert.id.desc()).offset(offset).limit(limit).all()

    return IncidentAlertListResponse(
        total=total,
        alerts=[IncidentAlertResponse.model_validate(a) for a in alerts],
    )


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    incident_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notification attempts and delivery status (QUEUED, SENT, FAILED, NOT_CONNECTED)."""
    query = db.query(IncidentNotification)
    if incident_id is not None:
        query = query.filter(IncidentNotification.incident_id == incident_id)
    if status_filter:
        query = query.filter(IncidentNotification.status == status_filter.upper())

    total = query.count()
    notifications = (
        query.order_by(IncidentNotification.id.desc()).offset(offset).limit(limit).all()
    )

    return NotificationListResponse(
        total=total,
        notifications=[IncidentNotificationResponse.model_validate(n) for n in notifications],
    )


@router.post("/evaluate/{incident_id}", response_model=IncidentAlertListResponse)
def evaluate_alerts_for_incident(
    incident_id: int,
    alert_type: str = Query("INCIDENT_CREATED"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluate alerts for a given incident.
    Suppresses duplicate alerts for the same condition.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "INCIDENT_NOT_FOUND", "message": f"Incident {incident_id} not found"}},
        )

    alerts = evaluate_incident_alerts(db, incident, alert_type=alert_type)
    return IncidentAlertListResponse(
        total=len(alerts),
        alerts=[IncidentAlertResponse.model_validate(a) for a in alerts],
    )
