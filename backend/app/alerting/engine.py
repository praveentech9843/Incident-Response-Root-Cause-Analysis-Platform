from datetime import datetime, timezone
from typing import List, Optional, Union
from sqlalchemy.orm import Session

from app.alerting.base import NotificationStatus
from app.alerting.providers import get_notification_provider
from app.core.logging import get_logger
from app.models.alerting import IncidentAlert, IncidentAlertRule, IncidentNotification
from app.models.incident import Incident

logger = get_logger("alert_engine")


def evaluate_incident_alerts(
    db: Session,
    incident_or_id: Union[Incident, int],
    alert_type: str = "INCIDENT_CREATED",
) -> List[IncidentAlert]:
    """
    Evaluates alerting rules against an incident.
    Enforces strict alert deduplication via unique dedup_key.
    Dispatches notifications via configured providers.
    """
    alerts_created: List[IncidentAlert] = []

    inc_id = incident_or_id if isinstance(incident_or_id, int) else incident_or_id.id
    incident = db.query(Incident).filter(Incident.id == inc_id).first()
    if not incident:
        logger.warning("evaluate_incident_alerts: Incident %s not found", inc_id)
        return []

    # Read needed attributes immediately to avoid DetachedInstanceError across transactions
    inc_title = incident.title or "Incident"
    inc_status = incident.status
    inc_severity = getattr(incident, "severity", None) or "HIGH"
    inc_services = incident.service_count or 1
    inc_started = str(incident.started_at)
    inc_reason = incident.correlation_reason or "None"

    # Query active rules matching severity or all
    rules = (
        db.query(IncidentAlertRule)
        .filter(IncidentAlertRule.is_active == True)
        .all()
    )

    # If no rules exist in database, evaluate default notification channels
    if not rules:
        channels_to_evaluate = [
            ("slack", "#incidents"),
            ("pagerduty", "default_service"),
        ]
    else:
        channels_to_evaluate = [(r.channel, r.target) for r in rules]

    for channel, recipient in channels_to_evaluate:
        # Build deduplication key
        dedup_key = f"{inc_id}:{alert_type}:{channel}"

        # Deduplication check: Do not send repeated notifications for the same condition
        existing_alert = (
            db.query(IncidentAlert)
            .filter(IncidentAlert.dedup_key == dedup_key)
            .first()
        )

        if existing_alert:
            logger.info(
                "DEDUPLICATION: Alert already exists for %s, skipping duplicate delivery",
                dedup_key,
            )
            continue

        # Create new IncidentAlert record
        alert = IncidentAlert(
            incident_id=inc_id,
            alert_type=alert_type,
            dedup_key=dedup_key,
            status="ACTIVE",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)

        # Dispatch notification attempt
        subject = f"[{inc_severity}] Incident #{inc_id}: {inc_title}"
        message = (
            f"Status: {inc_status}\n"
            f"Services: {inc_services}\n"
            f"Started At: {inc_started}\n"
            f"Correlation Reason: {inc_reason}"
        )
        metadata = {
            "incident_id": inc_id,
            "severity": inc_severity,
            "alert_type": alert_type,
        }

        try:
            provider = get_notification_provider(channel)
            notif_status, resp_msg = provider.send_notification(
                recipient=recipient,
                subject=subject,
                message=message,
                metadata=metadata,
            )
        except Exception as exc:
            logger.error("Provider dispatch error for %s: %s", channel, exc)
            notif_status = NotificationStatus.FAILED
            resp_msg = str(exc)

        # Record notification delivery
        notification = IncidentNotification(
            alert_id=alert.id,
            incident_id=inc_id,
            channel=channel,
            recipient=recipient,
            status=notif_status.value,
            payload=message,
            response_message=resp_msg,
            retry_count=0 if notif_status == NotificationStatus.SENT else 1,
            sent_at=datetime.now(timezone.utc) if notif_status == NotificationStatus.SENT else None,
        )
        db.add(notification)
        db.commit()

        alerts_created.append(alert)

    return alerts_created
