from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.alerting.base import NotificationStatus
from app.alerting.engine import evaluate_incident_alerts
from app.alerting.providers import SlackNotificationProvider
from app.core.database import SessionLocal
from app.main import app
from app.models.alerting import IncidentAlert, IncidentAlertRule, IncidentNotification
from app.models.incident import Incident


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_alerting_db():
    session = SessionLocal()
    try:
        session.query(IncidentNotification).delete()
        session.query(IncidentAlert).delete()
        session.query(IncidentAlertRule).delete()
        session.query(Incident).delete()
        session.commit()
    finally:
        session.close()
    yield
    session = SessionLocal()
    try:
        session.query(IncidentNotification).delete()
        session.query(IncidentAlert).delete()
        session.query(IncidentAlertRule).delete()
        session.query(Incident).delete()
        session.commit()
    finally:
        session.close()


def test_alert_rule_creation_and_listing(client):
    """Test creating and listing alert rules."""
    rule_data = {
        "name": "Critical Incident Slack Alert",
        "severity_trigger": "CRITICAL",
        "escalation_minutes": 15,
        "channel": "slack",
        "target": "#incident-war-room",
        "is_active": True,
    }
    resp = client.post("/api/v1/alerts/rules", json=rule_data)
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Critical Incident Slack Alert"
    assert created["channel"] == "slack"

    # List rules
    list_resp = client.get("/api/v1/alerts/rules")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


def test_alert_deduplication():
    """Verify duplicate alerts are suppressed for identical incident and condition."""
    session = SessionLocal()
    inc = Incident(
        incident_key="test-dedup-key-1",
        title="Payment Service Latency Spike",
        status="OPEN",
        correlation_reason="Correlation reason",
    )
    session.add(inc)
    session.commit()
    session.refresh(inc)

    # First evaluation generates alerts
    alerts1 = evaluate_incident_alerts(session, inc.id, alert_type="INCIDENT_CREATED")
    assert len(alerts1) > 0

    total_alerts_after_first = session.query(IncidentAlert).filter(IncidentAlert.incident_id == inc.id).count()

    # Second evaluation must suppress duplicates!
    alerts2 = evaluate_incident_alerts(session, inc.id, alert_type="INCIDENT_CREATED")
    assert len(alerts2) == 0

    total_alerts_after_second = session.query(IncidentAlert).filter(IncidentAlert.incident_id == inc.id).count()
    assert total_alerts_after_second == total_alerts_after_first
    session.close()


def test_notification_provider_unconfigured_status():
    """Verify provider returns NOT_CONNECTED when credentials are not configured."""
    provider = SlackNotificationProvider()
    provider.enabled = False

    status, msg = provider.send_notification(
        recipient="#dev",
        subject="Alert",
        message="Test alert message",
        metadata={},
    )
    assert status == NotificationStatus.NOT_CONNECTED
    assert "not configured" in msg.lower()


def test_notification_dispatch_mocked_success():
    """Verify notification delivery succeeds when provider is mocked."""
    provider = SlackNotificationProvider()
    provider.enabled = True

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"ok": True}

        status, msg = provider.send_notification(
            recipient="#incidents",
            subject="Test Critical Alert",
            message="Database connection error",
            metadata={},
        )
        assert status == NotificationStatus.SENT
        assert "delivered" in msg.lower()


def test_alerts_api_evaluation_and_query(client):
    """Test POST /api/v1/alerts/evaluate/{incident_id} and GET /api/v1/alerts."""
    session = SessionLocal()
    inc = Incident(
        incident_key="test-api-eval-key",
        title="High Memory Usage",
        status="OPEN",
        correlation_reason="Threshold exceeded",
    )
    session.add(inc)
    session.commit()
    session.refresh(inc)
    inc_id = inc.id
    session.close()

    eval_resp = client.post(f"/api/v1/alerts/evaluate/{inc_id}")
    assert eval_resp.status_code == 200
    assert eval_resp.json()["total"] > 0

    # Query active alerts
    alerts_resp = client.get(f"/api/v1/alerts?incident_id={inc_id}")
    assert alerts_resp.status_code == 200
    assert alerts_resp.json()["total"] > 0
    assert alerts_resp.json()["alerts"][0]["incident_id"] == inc_id

    # Query notifications
    notifs_resp = client.get(f"/api/v1/alerts/notifications?incident_id={inc_id}")
    assert notifs_resp.status_code == 200
    assert notifs_resp.json()["total"] > 0
