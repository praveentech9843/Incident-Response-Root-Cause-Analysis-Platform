from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AlertRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    severity_trigger: Optional[str] = Field("ALL", pattern="^(CRITICAL|HIGH|MEDIUM|LOW|ALL)$")
    escalation_minutes: int = Field(30, ge=1, le=1440)
    channel: str = Field(..., pattern="^(slack|email|pagerduty)$")
    target: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True


class AlertRuleResponse(BaseModel):
    id: int
    name: str
    severity_trigger: Optional[str]
    escalation_minutes: int
    channel: str
    target: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertRuleListResponse(BaseModel):
    total: int
    rules: List[AlertRuleResponse]


class IncidentNotificationResponse(BaseModel):
    id: int
    alert_id: Optional[int]
    incident_id: int
    channel: str
    recipient: str
    status: str
    payload: Optional[str]
    response_message: Optional[str]
    retry_count: int
    created_at: datetime
    sent_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class IncidentAlertResponse(BaseModel):
    id: int
    incident_id: int
    rule_id: Optional[int]
    alert_type: str
    dedup_key: str
    status: str
    created_at: datetime
    notifications: List[IncidentNotificationResponse] = []

    model_config = ConfigDict(from_attributes=True)


class IncidentAlertListResponse(BaseModel):
    total: int
    alerts: List[IncidentAlertResponse]


class NotificationListResponse(BaseModel):
    total: int
    notifications: List[IncidentNotificationResponse]
