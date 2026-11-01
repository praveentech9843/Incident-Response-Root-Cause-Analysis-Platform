import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.test_safety import assert_safe_test_environment
from app.main import app
from app.models.log import Log
from app.models.parsed_log import ParsedLog
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.incident_context import IncidentContext
from app.models.incident_rca import IncidentRCAAnalysis
from app.models.incident_recommendation import IncidentRecommendation
from app.models.incident_investigation import (
    IncidentInvestigation,
    IncidentInvestigationNote,
    IncidentInvestigationAction,
    IncidentRecommendationReview,
    IncidentVerificationStep,
    IncidentTimelineEvent,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_db():
    assert_safe_test_environment()
    session = SessionLocal()
    try:
        session.query(IncidentTimelineEvent).delete()
        session.query(IncidentVerificationStep).delete()
        session.query(IncidentRecommendationReview).delete()
        session.query(IncidentInvestigationAction).delete()
        session.query(IncidentInvestigationNote).delete()
        session.query(IncidentInvestigation).delete()
        session.query(IncidentRecommendation).delete()
        session.query(IncidentRCAAnalysis).delete()
        session.query(IncidentContext).delete()
        session.query(IncidentEvent).delete()
        session.query(Incident).delete()
        session.query(ParsedLog).delete()
        session.query(Log).delete()
        session.commit()
    finally:
        session.close()
    yield
    assert_safe_test_environment()
    session = SessionLocal()
    try:
        session.query(IncidentTimelineEvent).delete()
        session.query(IncidentVerificationStep).delete()
        session.query(IncidentRecommendationReview).delete()
        session.query(IncidentInvestigationAction).delete()
        session.query(IncidentInvestigationNote).delete()
        session.query(IncidentInvestigation).delete()
        session.query(IncidentRecommendation).delete()
        session.query(IncidentRCAAnalysis).delete()
        session.query(IncidentContext).delete()
        session.query(IncidentEvent).delete()
        session.query(Incident).delete()
        session.query(ParsedLog).delete()
        session.query(Log).delete()
        session.commit()
    finally:
        session.close()


def create_test_incident(db_session, run_id: str):
    """Creates a correlated incident with parsed logs, context, RCA, and recommendations."""
    now = datetime.now(timezone.utc)

    # 1. Raw Log
    log = Log(
        original_filename=f"inv_{run_id}.log",
        file_type="log",
        raw_content=f"2026-10-07 10:00:00 ERROR AuthService [tx-{run_id}] Connection pool exhausted\n",
        content_hash=f"hash-{run_id}",
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    # 2. Parsed Log
    p1 = ParsedLog(
        log_id=log.id,
        event_index=1,
        timestamp=now,
        level="ERROR",
        service_name="AuthService",
        message="Connection pool exhausted",
        exception_type="PoolExhaustedException",
        stack_trace="com.auth.Pool:12\ncom.auth.Main:45",
    )
    db_session.add(p1)
    db_session.commit()
    db_session.refresh(p1)

    # 3. Incident
    inc = Incident(
        incident_key=f"inc-{run_id}",
        title="AuthService Database Exhaustion",
        status="OPEN",
        started_at=now,
        ended_at=now,
        event_count=1,
        service_count=1,
        correlation_reason="Single error cluster",
        correlation_confidence=1.0,
    )
    db_session.add(inc)
    db_session.commit()
    db_session.refresh(inc)

    # 4. Incident Event
    ie = IncidentEvent(
        incident_id=inc.id,
        parsed_log_id=p1.id,
        event_index=1,
    )
    db_session.add(ie)

    # 5. Context
    ctx = IncidentContext(
        incident_id=inc.id,
        context_category="SERVICE",
        status="AVAILABLE",
        data={"service": "AuthService", "tier": "critical"},
        source="service_catalog",
    )
    db_session.add(ctx)

    # 6. RCA
    rca = IncidentRCAAnalysis(
        incident_id=inc.id,
        analysis_id=f"rca-{run_id}",
        analysis_status="COMPLETED",
        provider="mock",
        model="mock-rca-v1",
        summary="AuthService connection pool saturation",
        confidence=0.85,
        confidence_level="HIGH",
        hypotheses=[
            {
                "hypothesis_id": "HYP-1",
                "title": "Database Connection Pool Saturation",
                "description": "Exhausted connections in AuthService",
                "confidence": 0.85,
                "confidence_level": "HIGH",
                "supporting_evidence": ["EVT-1", "EXC-1", "ST-1"],
                "causal_status": "SUPPORTED",
            }
        ],
        evidence_snapshot={
            "events": [{"evidence_id": "EVT-1", "service": "AuthService"}],
            "exceptions": [{"evidence_id": "EXC-1", "type": "PoolExhaustedException"}],
            "stack_traces": [{"evidence_id": "ST-1"}],
            "contexts": {"service": {"tier": "critical"}},
        },
        limitations=[],
    )
    db_session.add(rca)
    db_session.commit()
    db_session.refresh(rca)

    # 7. Recommendations
    rec = IncidentRecommendation(
        recommendation_id=f"REC-{run_id}-1",
        incident_id=inc.id,
        rca_analysis_id=rca.id,
        type="FIX",
        title="Scale connection pool size for AuthService",
        description="Increase pool size from 20 to 100",
        rationale="Exhaustion confirmed by EVT-1 and EXC-1",
        supporting_evidence=["EVT-1", "EXC-1"],
        confidence=0.85,
        confidence_level="HIGH",
        risk_level="MEDIUM",
        expected_impact="Mitigates connection timeouts",
        prerequisites=[],
        verification_steps=["Check pool utilization after restart"],
        status="PROPOSED",
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)

    return inc, rec


# =====================================================================
# Investigation Workspace & Assignment Tests
# =====================================================================

def test_create_investigation(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/investigation",
        json={
            "assigned_to": "dev-sarah",
            "assigned_to_name": "Sarah Connor",
            "investigation_summary": "Initial triage for connection pool exhaustion",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == inc.id
    assert data["assigned_to"] == "dev-sarah"
    assert data["assigned_to_name"] == "Sarah Connor"
    assert data["status"] in ("ASSIGNED", "INVESTIGATING")
    assert data["started_at"] is not None


def test_get_investigation(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    client.post(
        f"/api/v1/incidents/{inc.id}/investigation",
        json={"assigned_to": "dev-john", "investigation_summary": "Investigating logs"},
    )

    resp = client.get(f"/api/v1/incidents/{inc.id}/investigation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == inc.id
    assert data["assigned_to"] == "dev-john"


def test_assign_developer(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={})

    resp = client.patch(
        f"/api/v1/incidents/{inc.id}/investigation",
        json={"assigned_to": "dev-alex", "assigned_to_name": "Alex Mercer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["assigned_to"] == "dev-alex"
    assert data["assigned_to_name"] == "Alex Mercer"
    assert data["assigned_at"] is not None


def test_update_investigation_status(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={})

    resp = client.patch(
        f"/api/v1/incidents/{inc.id}/investigation",
        json={"status": "READY_FOR_VERIFICATION"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "READY_FOR_VERIFICATION"


def test_invalid_status_transition_via_patch(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={})

    # Cannot resolve via PATCH - must use /resolve
    resp = client.patch(
        f"/api/v1/incidents/{inc.id}/investigation",
        json={"status": "RESOLVED"},
    )
    assert resp.status_code == 400
    assert "Cannot resolve investigation via PATCH" in resp.json()["detail"]


# =====================================================================
# Investigation Notes Tests
# =====================================================================

def test_create_and_retrieve_notes(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/investigation/notes",
        json={"author": "dev-alex", "note": "Checked logs around 10:00:00. DB saturation found."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["author"] == "dev-alex"
    assert "Checked logs" in data["note"]

    # Retrieve notes
    list_resp = client.get(f"/api/v1/incidents/{inc.id}/investigation/notes")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert any(n["author"] == "dev-alex" for n in list_data["notes"])


def test_reject_empty_note(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/investigation/notes",
        json={"author": "dev-alex", "note": "   "},
    )
    assert resp.status_code == 422


def test_note_with_valid_and_invalid_evidence(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    # Valid evidence token (EVT-1 or CTX-service)
    resp = client.post(
        f"/api/v1/incidents/{inc.id}/investigation/notes",
        json={"author": "dev-alex", "note": "Corroborated with service context", "evidence_references": ["CTX-service"]},
    )
    assert resp.status_code == 200

    # Invalid evidence token
    resp_invalid = client.post(
        f"/api/v1/incidents/{inc.id}/investigation/notes",
        json={"author": "dev-alex", "note": "Citing fake evidence", "evidence_references": ["FAKE-EVT-9999"]},
    )
    assert resp_invalid.status_code == 400
    assert "Invalid evidence reference" in resp_invalid.json()["detail"]


# =====================================================================
# Investigation Actions Tests
# =====================================================================

def test_create_and_retrieve_actions(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/investigation/actions",
        json={
            "action_type": "DIAGNOSTIC_CHECK",
            "description": "Checked connection pool utilization metric on PostgreSQL instance",
            "performed_by": "dev-alex",
            "result": "Saturation reached 100/100 active connections",
            "evidence_references": ["CTX-service"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["action_type"] == "DIAGNOSTIC_CHECK"
    assert data["performed_by"] == "dev-alex"

    list_resp = client.get(f"/api/v1/incidents/{inc.id}/investigation/actions")
    assert list_resp.status_code == 200
    actions = list_resp.json()["actions"]
    assert len(actions) >= 1


def test_action_reject_fake_evidence(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/investigation/actions",
        json={
            "action_type": "LOG_REVIEW",
            "description": "Inspecting missing logs",
            "performed_by": "dev-alex",
            "result": "No logs",
            "evidence_references": ["EVT-9999999"],
        },
    )
    assert resp.status_code == 400
    assert "Invalid evidence reference" in resp.json()["detail"]


def test_reject_empty_action_fields(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/investigation/actions",
        json={
            "action_type": "OBSERVATION",
            "description": "",
            "performed_by": "dev-alex",
            "result": "Some result",
        },
    )
    assert resp.status_code == 422


# =====================================================================
# Recommendation Review Tests
# =====================================================================

def test_accept_recommendation(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rec = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/recommendations/{rec.recommendation_id}/review",
        json={
            "reviewed_by": "dev-alex",
            "decision": "ACCEPTED",
            "reason": "RCA analysis shows clear pool exhaustion",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "ACCEPTED"
    assert data["recommendation_id"] == rec.recommendation_id


def test_reject_recommendation_requires_reason(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rec = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/recommendations/{rec.recommendation_id}/review",
        json={
            "reviewed_by": "dev-alex",
            "decision": "REJECTED",
            "reason": "",
        },
    )
    assert resp.status_code == 422


def test_defer_recommendation_with_reason(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rec = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/recommendations/{rec.recommendation_id}/review",
        json={
            "reviewed_by": "dev-alex",
            "decision": "DEFERRED",
            "reason": "Deferring until off-peak maintenance window",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["decision"] == "DEFERRED"


def test_prevent_mutation_of_original_recommendation(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rec = create_test_incident(db_session, run_id)

    client.post(
        f"/api/v1/incidents/{inc.id}/recommendations/{rec.recommendation_id}/review",
        json={
            "reviewed_by": "dev-alex",
            "decision": "ACCEPTED",
            "reason": "Accepted for execution",
        },
    )

    get_rec = client.get(f"/api/v1/incidents/{inc.id}/recommendations/{rec.recommendation_id}")
    assert get_rec.status_code == 200
    rec_data = get_rec.json()

    assert rec_data["title"] == rec.title
    assert rec_data["supporting_evidence"] == rec.supporting_evidence
    assert rec_data["status"] == "PROPOSED"


# =====================================================================
# Verification Checklist Tests
# =====================================================================

def test_create_and_update_verification_step(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/verification",
        json={
            "title": "Confirm AuthService health endpoint returns 200 OK",
            "description": "Probe /health endpoint over 3 consecutive minutes",
            "is_required": True,
            "evidence_references": ["CTX-service"],
        },
    )
    assert resp.status_code == 200
    step = resp.json()
    assert step["title"] == "Confirm AuthService health endpoint returns 200 OK"
    assert step["status"] == "PENDING"
    step_id = step["id"]

    update_resp = client.patch(
        f"/api/v1/incidents/{inc.id}/verification/{step_id}",
        json={
            "status": "PASSED",
            "result": "All 3 probes returned HTTP 200 with latency < 15ms",
            "verified_by": "dev-sarah",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "PASSED"
    assert update_resp.json()["verified_by"] == "dev-sarah"


def test_verification_step_reject_fake_evidence(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/verification",
        json={
            "title": "Check fake metric",
            "evidence_references": ["EVT-FAKE-999"],
        },
    )
    assert resp.status_code == 400
    assert "Invalid evidence reference" in resp.json()["detail"]


# =====================================================================
# Resolution Validation Tests
# =====================================================================

def test_prevent_resolution_without_verification_steps(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={"assigned_to": "dev-alex"})

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={
            "resolved_by": "dev-alex",
            "resolution_summary": "Resolved without any verification checks",
            "root_cause_confirmed": "CONFIRMED",
        },
    )
    assert resp.status_code == 400
    assert "At least one required verification step must be defined" in resp.json()["detail"]


def test_prevent_resolution_with_pending_verification(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={"assigned_to": "dev-alex"})

    client.post(
        f"/api/v1/incidents/{inc.id}/verification",
        json={"title": "Confirm error rate returns to normal", "is_required": True},
    )

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={
            "resolved_by": "dev-alex",
            "resolution_summary": "Attempting resolution with pending check",
        },
    )
    assert resp.status_code == 400
    assert "still pending" in resp.json()["detail"]


def test_prevent_resolution_with_failed_verification(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={"assigned_to": "dev-alex"})

    step = client.post(
        f"/api/v1/incidents/{inc.id}/verification",
        json={"title": "Health check", "is_required": True},
    ).json()

    client.patch(
        f"/api/v1/incidents/{inc.id}/verification/{step['id']}",
        json={"status": "FAILED", "result": "Failed with 500 Internal Error", "verified_by": "dev-alex"},
    )

    resp = client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={
            "resolved_by": "dev-alex",
            "resolution_summary": "Trying to resolve despite failure",
        },
    )
    assert resp.status_code == 400
    assert "failed" in resp.json()["detail"]


def test_resolve_with_valid_verification_and_reopen(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={"assigned_to": "dev-alex"})

    step = client.post(
        f"/api/v1/incidents/{inc.id}/verification",
        json={"title": "Connection pool verified below 50%", "is_required": True},
    ).json()

    client.patch(
        f"/api/v1/incidents/{inc.id}/verification/{step['id']}",
        json={"status": "PASSED", "result": "Pool utilization at 22%", "verified_by": "dev-alex"},
    )

    resolve_resp = client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={
            "resolved_by": "dev-alex",
            "resolution_summary": "Pool size increased from 20 to 100. Verification confirmed stable latency.",
            "root_cause_confirmed": "CONFIRMED",
        },
    )
    assert resolve_resp.status_code == 200
    res_data = resolve_resp.json()
    assert res_data["status"] == "RESOLVED"
    assert res_data["resolved_at"] is not None
    assert res_data["resolved_by"] == "dev-alex"
    assert res_data["investigation_status"] == "RESOLVED"

    detail = client.get(f"/api/v1/incidents/{inc.id}").json()
    assert detail["status"] == "RESOLVED"

    reopen_resp = client.post(
        f"/api/v1/incidents/{inc.id}/reopen",
        json={"reopened_by": "dev-alex", "reason": "Intermittent error resurfaced after 30 minutes"},
    )
    assert reopen_resp.status_code == 200
    reopen_data = reopen_resp.json()
    assert reopen_data["status"] == "INVESTIGATING"

    reopened_detail = client.get(f"/api/v1/incidents/{inc.id}").json()
    assert reopened_detail["status"] == "INVESTIGATING"
    assert reopened_detail["resolved_at"] is None
    assert reopened_detail["resolved_by"] is None
    assert reopened_detail["resolution_summary"] is None
    assert reopened_detail["root_cause_confirmed"] is None


def test_reopen_invalidates_verification_and_blocks_resolution_until_reverified(client, db_session):
    """
    Regression test for incident reopen verification invalidation:
    1. Resolve an incident after passing its required verification step.
    2. Reopen the incident.
    3. Confirm the step is now PENDING and its previous verification metadata is cleared.
    4. Attempt to resolve without fresh verification and assert HTTP 400.
    5. Pass the required step again and confirm resolution succeeds.
    6. Confirm verification-step definitions and evidence references remain unchanged.
    """
    run_id = uuid.uuid4().hex[:8]
    inc, _ = create_test_incident(db_session, run_id)

    # Start investigation
    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={"assigned_to": "dev-alex"})

    # Create verification step with evidence reference
    step = client.post(
        f"/api/v1/incidents/{inc.id}/verification",
        json={
            "title": "Confirm AuthService health endpoint returns 200 OK",
            "description": "Probe /health endpoint over 3 consecutive minutes",
            "is_required": True,
            "evidence_references": ["CTX-service"],
        },
    ).json()
    step_id = step["id"]
    assert step["status"] == "PENDING"
    assert step["title"] == "Confirm AuthService health endpoint returns 200 OK"
    assert step["description"] == "Probe /health endpoint over 3 consecutive minutes"
    assert step["is_required"] is True
    assert step["evidence_references"] == ["CTX-service"]

    # Pass the step
    patch_resp = client.patch(
        f"/api/v1/incidents/{inc.id}/verification/{step_id}",
        json={
            "status": "PASSED",
            "result": "All 3 probes returned HTTP 200 with latency < 15ms",
            "verified_by": "dev-sarah",
        },
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "PASSED"
    assert patch_resp.json()["result"] == "All 3 probes returned HTTP 200 with latency < 15ms"
    assert patch_resp.json()["verified_by"] == "dev-sarah"
    assert patch_resp.json()["verified_at"] is not None

    # Resolve incident
    res_resp = client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={
            "resolved_by": "dev-sarah",
            "resolution_summary": "Service restored and verified healthy",
            "root_cause_confirmed": "CONFIRMED",
        },
    )
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "RESOLVED"

    # Reopen incident
    reopen_resp = client.post(
        f"/api/v1/incidents/{inc.id}/reopen",
        json={
            "reopened_by": "dev-alex",
            "reason": "Connection errors recurred under traffic load",
        },
    )
    assert reopen_resp.status_code == 200

    # Confirm incident resolution fields are cleared
    reopened_inc = client.get(f"/api/v1/incidents/{inc.id}").json()
    assert reopened_inc["status"] == "INVESTIGATING"
    assert reopened_inc["resolved_at"] is None
    assert reopened_inc["resolved_by"] is None
    assert reopened_inc["resolution_summary"] is None
    assert reopened_inc["root_cause_confirmed"] is None

    # Confirm verification step is now PENDING and metadata is cleared
    steps_resp = client.get(f"/api/v1/incidents/{inc.id}/verification")
    assert steps_resp.status_code == 200
    steps_data = steps_resp.json()["steps"]
    assert len(steps_data) == 1
    reopened_step = steps_data[0]
    assert reopened_step["id"] == step_id
    assert reopened_step["status"] == "PENDING"
    assert reopened_step["result"] is None
    assert reopened_step["verified_by"] is None
    assert reopened_step["verified_at"] is None

    # Confirm step definitions and evidence references remain unchanged
    assert reopened_step["title"] == "Confirm AuthService health endpoint returns 200 OK"
    assert reopened_step["description"] == "Probe /health endpoint over 3 consecutive minutes"
    assert reopened_step["is_required"] is True
    assert reopened_step["evidence_references"] == ["CTX-service"]

    # Attempt to resolve without fresh verification -> must fail with HTTP 400
    premature_resolve = client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={
            "resolved_by": "dev-alex",
            "resolution_summary": "Premature attempt to resolve reopened incident",
            "root_cause_confirmed": "UNKNOWN",
        },
    )
    assert premature_resolve.status_code == 400
    assert "still pending" in premature_resolve.json()["detail"]

    # Pass the required step again
    reverify_resp = client.patch(
        f"/api/v1/incidents/{inc.id}/verification/{step_id}",
        json={
            "status": "PASSED",
            "result": "Re-verified after config patch: 0 errors over 10 minutes",
            "verified_by": "dev-alex",
        },
    )
    assert reverify_resp.status_code == 200
    assert reverify_resp.json()["status"] == "PASSED"

    # Now resolution succeeds
    second_resolve = client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={
            "resolved_by": "dev-alex",
            "resolution_summary": "Applied pool tuning patch and re-verified stable operation",
            "root_cause_confirmed": "REFUTED",
        },
    )
    assert second_resolve.status_code == 200
    assert second_resolve.json()["status"] == "RESOLVED"
    assert second_resolve.json()["root_cause_confirmed"] == "REFUTED"



# =====================================================================
# Audit Timeline Tests
# =====================================================================

def test_timeline_tracks_full_workflow(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rec = create_test_incident(db_session, run_id)

    # 1. Start investigation
    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={"assigned_to": "dev-alex"})

    # 2. Add note
    client.post(
        f"/api/v1/incidents/{inc.id}/investigation/notes",
        json={"author": "dev-alex", "note": "Reviewed stack traces."},
    )

    # 3. Add action
    client.post(
        f"/api/v1/incidents/{inc.id}/investigation/actions",
        json={
            "action_type": "LOG_REVIEW",
            "description": "Reviewed application logs",
            "performed_by": "dev-alex",
            "result": "Identified connection failure point",
        },
    )

    # 4. Review recommendation
    client.post(
        f"/api/v1/incidents/{inc.id}/recommendations/{rec.recommendation_id}/review",
        json={"reviewed_by": "dev-alex", "decision": "ACCEPTED", "reason": "Fix confirmed"},
    )

    # 5. Add & pass verification step
    step = client.post(
        f"/api/v1/incidents/{inc.id}/verification",
        json={"title": "Service health check", "is_required": True},
    ).json()

    client.patch(
        f"/api/v1/incidents/{inc.id}/verification/{step['id']}",
        json={"status": "PASSED", "result": "Healthy", "verified_by": "dev-alex"},
    )

    # 6. Resolve
    client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={"resolved_by": "dev-alex", "resolution_summary": "Resolved"},
    )

    # 7. Reopen
    client.post(
        f"/api/v1/incidents/{inc.id}/reopen",
        json={"reopened_by": "dev-alex", "reason": "Testing reopen"},
    )

    # Query timeline
    timeline_resp = client.get(f"/api/v1/incidents/{inc.id}/timeline")
    assert timeline_resp.status_code == 200
    events = timeline_resp.json()["events"]
    assert len(events) >= 6

    event_types = [e["event_type"] for e in events]
    assert "INVESTIGATION_STARTED" in event_types
    assert "NOTE_ADDED" in event_types
    assert "ACTION_RECORDED" in event_types
    assert "RECOMMENDATION_REVIEWED" in event_types
    assert "VERIFICATION_CREATED" in event_types
    assert "INCIDENT_RESOLVED" in event_types
    assert "INCIDENT_REOPENED" in event_types


# =====================================================================
# Immutability Guarantees Tests
# =====================================================================

def test_phase_1_to_6_data_remains_immutable_during_investigation(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rec = create_test_incident(db_session, run_id)

    initial_rca = client.get(f"/api/v1/incidents/{inc.id}/rca").json()
    initial_recs = client.get(f"/api/v1/incidents/{inc.id}/recommendations").json()

    client.post(f"/api/v1/incidents/{inc.id}/investigation", json={"assigned_to": "dev-alex"})
    client.post(
        f"/api/v1/incidents/{inc.id}/investigation/notes",
        json={"author": "dev-alex", "note": "Investigating."},
    )
    step = client.post(
        f"/api/v1/incidents/{inc.id}/verification",
        json={"title": "Verification check", "is_required": True},
    ).json()
    client.patch(
        f"/api/v1/incidents/{inc.id}/verification/{step['id']}",
        json={"status": "PASSED", "result": "Passed", "verified_by": "dev-alex"},
    )
    client.post(
        f"/api/v1/incidents/{inc.id}/resolve",
        json={"resolved_by": "dev-alex", "resolution_summary": "All resolved."},
    )

    current_rca = client.get(f"/api/v1/incidents/{inc.id}/rca").json()
    assert current_rca["analysis_id"] == initial_rca["analysis_id"]
    assert current_rca["evidence_snapshot"] == initial_rca["evidence_snapshot"]
    assert current_rca["hypotheses"] == initial_rca["hypotheses"]

    current_recs = client.get(f"/api/v1/incidents/{inc.id}/recommendations").json()
    assert len(current_recs["recommendations"]) == len(initial_recs["recommendations"])
    assert current_recs["recommendations"][0]["supporting_evidence"] == initial_recs["recommendations"][0]["supporting_evidence"]
    assert current_recs["recommendations"][0]["rationale"] == initial_recs["recommendations"][0]["rationale"]


def test_get_recommendation_reviews_route_collision_fixed(client, db_session):
    """
    Regression test for route collision:
    GET /api/v1/incidents/{incident_id}/recommendations/reviews must resolve to the
    static review list endpoint and NEVER interpret 'reviews' as recommendation_id.
    """
    run_id = uuid.uuid4().hex[:8]
    inc, rec = create_test_incident(db_session, run_id)

    # 1. Before any reviews exist, GET /recommendations/reviews returns 200 with empty list
    resp = client.get(f"/api/v1/incidents/{inc.id}/recommendations/reviews")
    assert resp.status_code == 200, f"Expected 200 OK but got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["incident_id"] == inc.id
    assert data["total"] == 0
    assert data["reviews"] == []

    # 2. Review a recommendation via dynamic route POST /recommendations/{rec_id}/review
    post_resp = client.post(
        f"/api/v1/incidents/{inc.id}/recommendations/{rec.recommendation_id}/review",
        json={
            "reviewed_by": "dev-alex",
            "decision": "ACCEPTED",
            "reason": "Fix verified against logs",
        },
    )
    assert post_resp.status_code == 200
    review_data = post_resp.json()
    assert review_data["decision"] == "ACCEPTED"
    assert review_data["recommendation_id"] == rec.recommendation_id

    # 3. GET /recommendations/reviews returns the recorded review
    list_resp = client.get(f"/api/v1/incidents/{inc.id}/recommendations/reviews")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 1
    assert len(list_data["reviews"]) == 1
    assert list_data["reviews"][0]["recommendation_id"] == rec.recommendation_id
    assert list_data["reviews"][0]["decision"] == "ACCEPTED"

    # 4. Verify that normal recommendation lookup GET /recommendations/{rec_id} still works
    rec_resp = client.get(f"/api/v1/incidents/{inc.id}/recommendations/{rec.recommendation_id}")
    assert rec_resp.status_code == 200
    assert rec_resp.json()["recommendation_id"] == rec.recommendation_id
