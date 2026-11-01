from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class IncidentAlertRule(Base):
    """
    Configurable alert rules for incidents (e.g. CRITICAL incident -> notification,
    OPEN for > X minutes -> escalation).
    """
    __tablename__ = "incident_alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    severity_trigger = Column(String(32), nullable=True)  # CRITICAL, HIGH, ALL
    escalation_minutes = Column(Integer, default=30, nullable=False)
    channel = Column(String(32), nullable=False)  # slack, email, pagerduty
    target = Column(String(255), nullable=False)  # webhook, email address, service key
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class IncidentAlert(Base):
    """
    Alert generated from incident conditions.
    Enforces deduplication via unique dedup_key.
    """
    __tablename__ = "incident_alerts"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("incident_alert_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    alert_type = Column(String(64), nullable=False)  # INCIDENT_CREATED, CRITICAL_SEVERITY, ESCALATION, INCIDENT_RESOLVED
    dedup_key = Column(String(128), unique=True, index=True, nullable=False)
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, SUPPRESSED, RESOLVED
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    notifications = relationship("IncidentNotification", back_populates="alert", cascade="all, delete-orphan")


class IncidentNotification(Base):
    """
    Delivery attempt of an alert to a specific external notification channel.
    Status: QUEUED, SENT, FAILED, NOT_CONNECTED.
    """
    __tablename__ = "incident_notifications"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("incident_alerts.id", ondelete="CASCADE"), nullable=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(32), nullable=False)  # slack, email, pagerduty
    recipient = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False)  # QUEUED, SENT, FAILED, NOT_CONNECTED
    payload = Column(Text, nullable=True)
    response_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    alert = relationship("IncidentAlert", back_populates="notifications")
