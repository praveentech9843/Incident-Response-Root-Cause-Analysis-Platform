import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, Tuple
import httpx

from app.alerting.base import NotificationProvider, NotificationStatus
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("alert_providers")


class SlackNotificationProvider(NotificationProvider):
    """Real Slack notification provider with bounded retries."""

    def __init__(self):
        super().__init__(name="slack")
        self.enabled = settings.SLACK_ENABLED and bool(settings.SLACK_TOKEN)

    def send_notification(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Dict[str, Any],
    ) -> Tuple[NotificationStatus, str]:
        if not self.enabled:
            return (
                NotificationStatus.NOT_CONNECTED,
                "Slack integration not configured. Set SLACK_ENABLED and SLACK_TOKEN.",
            )

        channel = recipient or settings.SLACK_DEFAULT_CHANNEL
        payload = {
            "channel": channel,
            "text": f"*{subject}*\n{message}",
        }
        headers = {
            "Authorization": f"Bearer {settings.SLACK_TOKEN}",
            "Content-Type": "application/json",
        }

        # Bounded retries: 2 attempts
        for attempt in range(1, 3):
            try:
                with httpx.Client(timeout=5.0) as client:
                    res = client.post(
                        "https://slack.com/api/chat.postMessage",
                        json=payload,
                        headers=headers,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("ok"):
                            return (NotificationStatus.SENT, "Slack message delivered successfully")
                        return (NotificationStatus.FAILED, f"Slack API error: {data.get('error')}")
                    return (NotificationStatus.FAILED, f"Slack HTTP error {res.status_code}")
            except httpx.RequestError as exc:
                if attempt == 2:
                    return (NotificationStatus.FAILED, f"Slack connection timeout/error: {str(exc)}")

        return (NotificationStatus.FAILED, "Slack delivery failed after retries")


class EmailNotificationProvider(NotificationProvider):
    """Real SMTP Email notification provider."""

    def __init__(self):
        super().__init__(name="email")
        self.enabled = settings.EMAIL_ENABLED and bool(settings.SMTP_HOST)

    def send_notification(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Dict[str, Any],
    ) -> Tuple[NotificationStatus, str]:
        if not self.enabled:
            return (
                NotificationStatus.NOT_CONNECTED,
                "Email integration not configured. Set EMAIL_ENABLED and SMTP_HOST.",
            )

        try:
            msg = MIMEText(message)
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_USER or "alerts@incidentplatform.local"
            msg["To"] = recipient

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5.0) as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            return (NotificationStatus.SENT, f"Email delivered to {recipient}")
        except Exception as exc:
            logger.warning("SMTP email delivery failed: %s", exc)
            return (NotificationStatus.FAILED, f"SMTP failure: {str(exc)}")


class PagerDutyNotificationProvider(NotificationProvider):
    """Real PagerDuty Events API v2 notification provider."""

    def __init__(self):
        super().__init__(name="pagerduty")
        self.enabled = settings.PAGERDUTY_ENABLED and bool(settings.PAGERDUTY_TOKEN)

    def send_notification(
        self,
        recipient: str,
        subject: str,
        message: str,
        metadata: Dict[str, Any],
    ) -> Tuple[NotificationStatus, str]:
        if not self.enabled:
            return (
                NotificationStatus.NOT_CONNECTED,
                "PagerDuty integration not configured. Set PAGERDUTY_ENABLED and PAGERDUTY_TOKEN.",
            )

        routing_key = recipient or settings.PAGERDUTY_TOKEN
        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": subject,
                "severity": metadata.get("severity", "error").lower(),
                "source": "Incident-Response-Platform",
                "custom_details": {"message": message, **metadata},
            },
        }

        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                )
                if res.status_code in (200, 202):
                    return (NotificationStatus.SENT, "PagerDuty event enqueued")
                return (NotificationStatus.FAILED, f"PagerDuty HTTP {res.status_code}: {res.text}")
        except httpx.RequestError as exc:
            return (NotificationStatus.FAILED, f"PagerDuty network error: {str(exc)}")


def get_notification_provider(channel: str) -> NotificationProvider:
    channel_lower = channel.lower()
    if channel_lower == "slack":
        return SlackNotificationProvider()
    elif channel_lower == "email":
        return EmailNotificationProvider()
    elif channel_lower == "pagerduty":
        return PagerDutyNotificationProvider()
    raise ValueError(f"Unknown notification channel: {channel}")
