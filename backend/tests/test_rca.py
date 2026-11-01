import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.log import Log
from app.models.parsed_log import ParsedLog
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.incident_context import IncidentContext
from app.models.incident_rca import IncidentRCAAnalysis
from app.rca.analyzer import RootCauseAnalyzer
from app.rca.base import RCAProvider
from app.rca.evidence import RCAEvidenceBuilder, RCAEvidencePackage
from app.rca.providers.mock_provider import MockRCAProvider
from app.rca.schemas import (
    AnalysisStatus,
    CausalStatus,
    ConfidenceLevel,
    EvidenceType,
    RCAHypothesis,
    RCAResult,
    RoleClassification,
)
from app.rca.validators import RCAValidator
from app.services.rca_service import RCAService


@pytest.fixture
def db_session():
    """Database session fixture for testing."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_db():
    """Clean tables before each test to maintain isolation."""
    session = SessionLocal()
    try:
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
    session = SessionLocal()
    try:
        session.query(IncidentRCAAnalysis).delete()
        session.query(IncidentContext).delete()
        session.query(IncidentEvent).delete()
        session.query(Incident).delete()
        session.query(ParsedLog).delete()
        session.query(Log).delete()
        session.commit()
    finally:
        session.close()


def create_test_incident_with_data(db_session, run_id: str):
    """Helper creating a real incident with parsed logs, exceptions, and Phase 4 contexts."""
    # 1. Raw Log
    raw_text = (
        f"2026-10-07 10:00:00 ERROR OrderService: Connection timeout to Redis [req:{run_id}]\n"
        f"2026-10-07 10:00:02 ERROR Redis: Connection refused [req:{run_id}]\n"
    )
    log = Log(
        original_filename=f"rca_{run_id}.log",
        file_type="log",
        raw_content=raw_text,
        content_hash=f"hash-{run_id}",
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    # 2. Parsed Logs
    p1 = ParsedLog(
        log_id=log.id,
        event_index=0,
        timestamp=datetime.now(timezone.utc),
        level="ERROR",
        service_name="OrderService",
        message="Connection timeout to Redis",
        exception_type="TimeoutException",
        exception_message="Read timed out",
    )
    p2 = ParsedLog(
        log_id=log.id,
        event_index=1,
        timestamp=datetime.now(timezone.utc),
        level="ERROR",
        service_name="Redis",
        message="Connection refused",
        exception_type="ConnectionRefusedError",
        exception_message="Connection to 6379 failed",
        stack_trace="redis.exceptions.ConnectionError: Connection to 6379 refused at redis/client.py:120",
    )
    db_session.add_all([p1, p2])
    db_session.commit()
    db_session.refresh(p1)
    db_session.refresh(p2)

    # 3. Incident
    inc = Incident(
        incident_key=f"inc-key-{run_id}",
        title="Correlated errors across OrderService, Redis",
        status="OPEN",
        started_at=p1.timestamp,
        ended_at=p2.timestamp,
        event_count=2,
        service_count=2,
        correlation_reason=f"Events share correlation ID '{run_id}'",
        correlation_confidence=0.95,
    )
    db_session.add(inc)
    db_session.commit()
    db_session.refresh(inc)

    # 4. Incident Events
    ie1 = IncidentEvent(incident_id=inc.id, parsed_log_id=p1.id, event_index=0)
    ie2 = IncidentEvent(incident_id=inc.id, parsed_log_id=p2.id, event_index=1)
    db_session.add_all([ie1, ie2])

    # 5. Contexts (Some AVAILABLE, some NOT_CONNECTED/UNAVAILABLE)
    c_svc = IncidentContext(
        incident_id=inc.id,
        context_category="service",
        status="AVAILABLE",
        data={"services_involved": ["OrderService", "Redis"], "service_count": 2},
        source="parsed_logs",
    )
    c_hist = IncidentContext(
        incident_id=inc.id,
        context_category="history",
        status="AVAILABLE",
        data={"previous_occurrence_count": 1, "recurring": True, "previous_incident_ids": [10]},
        source="incidents",
    )
    c_metrics = IncidentContext(
        incident_id=inc.id,
        context_category="metrics",
        status="NOT_CONNECTED",
        data={"cpu_usage": None, "message": "Metrics backend not connected"},
        source="NullMetricsProvider",
    )
    c_deploy = IncidentContext(
        incident_id=inc.id,
        context_category="deployment",
        status="INTEGRATION_REQUIRED",
        data={"git_commit": None, "message": "CI/CD integration required"},
        source="NullDeploymentProvider",
    )
    db_session.add_all([c_svc, c_hist, c_metrics, c_deploy])
    db_session.commit()

    return inc, log, [p1, p2]


def test_evidence_package_construction(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()

    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)

    assert package.incident["id"] == inc.id
    assert package.total_events == 2
    assert "OrderService" in package.service_names
    assert "Redis" in package.service_names
    assert len(package.observed_evidence_items) >= 4  # 2 logs, 2 exceptions, 1 stack trace, 2 available contexts
    assert len(package.unavailable_contexts) == 2  # metrics, deployment


def test_evidence_package_contains_only_real_incident_data(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()

    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    observed_ids = package.get_observed_evidence_ids()

    for item in package.observed_evidence_items:
        assert item.evidence_id in observed_ids
        assert item.is_available is True
        assert item.source in ["parsed_logs", "incidents", "NullMetricsProvider", "NullDeploymentProvider"]


def test_available_context_included_correctly(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()

    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    service_items = [i for i in package.observed_evidence_items if i.evidence_type == EvidenceType.SERVICE_CONTEXT]
    history_items = [i for i in package.observed_evidence_items if i.evidence_type == EvidenceType.HISTORY]

    assert len(service_items) == 1
    assert "OrderService" in service_items[0].description
    assert len(history_items) == 1
    assert "recurring=True" in history_items[0].description


def test_unavailable_context_excluded_from_evidence_claims(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()

    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    unavail_categories = [u["category"] for u in package.unavailable_contexts]

    assert "metrics" in unavail_categories
    assert "deployment" in unavail_categories
    # Ensure no observed evidence item is of type METRIC or DEPLOYMENT_CONTEXT
    for item in package.observed_evidence_items:
        assert item.evidence_type != EvidenceType.METRIC
        assert item.evidence_type != EvidenceType.DEPLOYMENT_CONTEXT


def test_mock_provider_returns_structured_rca(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()

    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    provider = MockRCAProvider()
    result = provider.analyze(package)

    assert result.analysis_status == AnalysisStatus.COMPLETED
    assert len(result.hypotheses) >= 1
    assert result.provider == "mock"
    assert result.model == "mock-rca-v1"
    assert result.hypotheses[0].role == RoleClassification.ROOT_CAUSE_CANDIDATE


def test_provider_response_schema_validation():
    # Valid schema creation
    hyp = RCAHypothesis(
        hypothesis_id="HYP-1",
        title="Test Hypothesis",
        description="A failure occurred",
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        supporting_evidence=["EVT-1"],
        reasoning="Based on log event",
        causal_status=CausalStatus.SUPPORTED,
        role=RoleClassification.ROOT_CAUSE_CANDIDATE,
    )
    result = RCAResult(
        analysis_status=AnalysisStatus.COMPLETED,
        summary="Analysis complete",
        hypotheses=[hyp],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
        limitations=[],
        provider="test",
        model="test-v1",
    )
    assert result.hypotheses[0].hypothesis_id == "HYP-1"


def test_invalid_evidence_reference_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)

    # Hypothesis citing a fake, nonexistent evidence ID
    hyp = RCAHypothesis(
        hypothesis_id="HYP-HALLUCINATED",
        title="Fake Hypothesis",
        description="Fake description",
        confidence=0.99,
        confidence_level=ConfidenceLevel.HIGH,
        supporting_evidence=["EVT-999999", "FAKE-EVIDENCE-ID"],
        reasoning="Citing fabricated evidence",
        causal_status=CausalStatus.CONFIRMED,
        role=RoleClassification.ROOT_CAUSE_CANDIDATE,
    )
    raw_result = RCAResult(
        analysis_status=AnalysisStatus.COMPLETED,
        summary="Test",
        hypotheses=[hyp],
        provider="test",
        model="test",
    )

    validated = RCAValidator.validate_and_refine(raw_result, package)
    # The invalid citations must be stripped
    assert "EVT-999999" not in validated.hypotheses[0].supporting_evidence
    assert "FAKE-EVIDENCE-ID" not in validated.hypotheses[0].supporting_evidence
    assert validated.hypotheses[0].causal_status == CausalStatus.UNVERIFIED


def test_fabricated_service_reference_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    valid_ev = list(package.get_observed_evidence_ids())[0]

    hyp = RCAHypothesis(
        hypothesis_id="HYP-FABRICATED-SVC",
        title="PaymentGatewayService failure",
        description="PaymentGatewayService crashed and caused failure",
        confidence=0.8,
        confidence_level=ConfidenceLevel.MEDIUM,
        supporting_evidence=[valid_ev],
        reasoning="Reasoning mentioning FakeBillingService",
        causal_status=CausalStatus.HYPOTHESIS,
        role=RoleClassification.ROOT_CAUSE_CANDIDATE,
    )
    raw_result = RCAResult(
        analysis_status=AnalysisStatus.COMPLETED,
        summary="Test",
        hypotheses=[hyp],
        provider="test",
        model="test",
    )

    validated = RCAValidator.validate_and_refine(raw_result, package)
    assert any("not present in incident data" in lim for lim in validated.limitations)


def test_fabricated_metric_claim_flagged(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    valid_ev = list(package.get_observed_evidence_ids())[0]

    # Metrics context is NOT_CONNECTED, but hypothesis asserts CPU utilization % was 95%
    hyp = RCAHypothesis(
        hypothesis_id="HYP-METRICS",
        title="CPU Spike",
        description="CPU utilization % reached 95% on server",
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
        supporting_evidence=[valid_ev],
        reasoning="CPU usage % spike caused timeout",
        causal_status=CausalStatus.CONFIRMED,
        role=RoleClassification.ROOT_CAUSE_CANDIDATE,
    )
    raw_result = RCAResult(
        analysis_status=AnalysisStatus.COMPLETED,
        summary="Test",
        hypotheses=[hyp],
        provider="test",
        model="test",
    )

    validated = RCAValidator.validate_and_refine(raw_result, package)
    assert any("Metrics context was NOT_CONNECTED" in lim for lim in validated.limitations)
    assert validated.hypotheses[0].causal_status != CausalStatus.CONFIRMED


def test_fabricated_deployment_claim_flagged(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    valid_ev = list(package.get_observed_evidence_ids())[0]

    hyp = RCAHypothesis(
        hypothesis_id="HYP-DEPLOY",
        title="Git commit deployment regression",
        description="Deployed commit caused regression",
        confidence=0.8,
        confidence_level=ConfidenceLevel.MEDIUM,
        supporting_evidence=[valid_ev],
        reasoning="New deployment version was buggy",
        causal_status=CausalStatus.HYPOTHESIS,
        role=RoleClassification.ROOT_CAUSE_CANDIDATE,
    )
    raw_result = RCAResult(
        analysis_status=AnalysisStatus.COMPLETED,
        summary="Test",
        hypotheses=[hyp],
        provider="test",
        model="test",
    )

    validated = RCAValidator.validate_and_refine(raw_result, package)
    assert any("Deployment context was INTEGRATION_REQUIRED" in lim for lim in validated.limitations)


def test_unsupported_causal_claim_downgraded(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    valid_ev = list(package.get_observed_evidence_ids())[0]

    # Only 1 supporting evidence item, claims CONFIRMED
    hyp = RCAHypothesis(
        hypothesis_id="HYP-CAUSAL",
        title="OrderService Causality",
        description="OrderService caused Redis failure",
        confidence=0.99,
        confidence_level=ConfidenceLevel.HIGH,
        supporting_evidence=[valid_ev],
        reasoning="Claiming confirmed causality",
        causal_status=CausalStatus.CONFIRMED,
        role=RoleClassification.ROOT_CAUSE_CANDIDATE,
    )
    raw_result = RCAResult(
        analysis_status=AnalysisStatus.COMPLETED,
        summary="Test",
        hypotheses=[hyp],
        provider="test",
        model="test",
    )

    validated = RCAValidator.validate_and_refine(raw_result, package)
    # Must be downgraded from CONFIRMED to SUPPORTED or HYPOTHESIS
    assert validated.hypotheses[0].causal_status != CausalStatus.CONFIRMED


def test_insufficient_evidence_handled_correctly(db_session):
    # Incident with 0 events
    inc = Incident(
        incident_key=f"inc-empty-{uuid.uuid4().hex[:8]}",
        title="Empty Incident",
        status="OPEN",
        event_count=0,
        service_count=0,
        correlation_reason="None",
    )
    db_session.add(inc)
    db_session.commit()

    package = RCAEvidenceBuilder.build(incident=inc, events=[], contexts=[])
    analyzer = RootCauseAnalyzer(provider=MockRCAProvider())
    result = analyzer.analyze(package)

    assert result.analysis_status == AnalysisStatus.INSUFFICIENT_EVIDENCE
    assert result.hypotheses == []
    assert "insufficient" in result.summary.lower()


def test_provider_unavailable_handled_correctly(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)

    # Analyzer with provider=None
    analyzer = RootCauseAnalyzer(provider=None)
    result = analyzer.analyze(package)

    assert result.analysis_status == AnalysisStatus.PROVIDER_UNAVAILABLE
    assert result.hypotheses == []
    assert "not configured" in result.summary


def test_confidence_validation_works(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, events = create_test_incident_with_data(db_session, run_id)
    contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    package = RCAEvidenceBuilder.build(incident=inc, events=events, contexts=contexts)
    valid_ev = list(package.get_observed_evidence_ids())[0]

    # LLM reports 0.99 with only 1 supporting evidence
    hyp = RCAHypothesis(
        hypothesis_id="HYP-CONF",
        title="Single Evidence Hypothesis",
        description="Only one evidence",
        confidence=0.99,
        confidence_level=ConfidenceLevel.HIGH,
        supporting_evidence=[valid_ev],
        reasoning="Reasoning",
        causal_status=CausalStatus.HYPOTHESIS,
        role=RoleClassification.ROOT_CAUSE_CANDIDATE,
    )
    raw_result = RCAResult(
        analysis_status=AnalysisStatus.COMPLETED,
        summary="Test",
        hypotheses=[hyp],
        provider="test",
        model="test",
    )

    validated = RCAValidator.validate_and_refine(raw_result, package)
    # Must be capped at <= 0.50 because supporting_count == 1
    assert validated.hypotheses[0].confidence <= 0.50
    assert validated.hypotheses[0].confidence_level == ConfidenceLevel.MEDIUM or validated.hypotheses[0].confidence_level == ConfidenceLevel.LOW


def test_rca_analysis_persistence_and_snapshot(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, _ = create_test_incident_with_data(db_session, run_id)

    service = RCAService(db=db_session, provider=MockRCAProvider())
    res = service.run_incident_rca(inc.id)

    assert res.incident_id == inc.id
    assert res.analysis_status == "COMPLETED"
    assert res.provider == "mock"
    assert len(res.hypotheses) >= 1
    assert "incident" in res.evidence_snapshot
    assert "observed_evidence_items" in res.evidence_snapshot


def test_rca_history_and_latest_retrieval(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, _ = create_test_incident_with_data(db_session, run_id)

    service = RCAService(db=db_session, provider=MockRCAProvider())
    # Run analysis 1
    analysis_1 = service.run_incident_rca(inc.id)
    # Run analysis 2
    analysis_2 = service.run_incident_rca(inc.id)

    assert analysis_1.analysis_id != analysis_2.analysis_id

    # Latest should be analysis_2
    latest = service.get_latest_rca(inc.id)
    assert latest.analysis_id == analysis_2.analysis_id

    # History should contain both
    history = service.get_rca_history(inc.id)
    assert history.total >= 2
    analysis_ids = [item.analysis_id for item in history.items]
    assert analysis_1.analysis_id in analysis_ids
    assert analysis_2.analysis_id in analysis_ids

    # Query by ID
    by_id = service.get_rca_by_id(inc.id, analysis_1.analysis_id)
    assert by_id.analysis_id == analysis_1.analysis_id


def test_api_rca_endpoints(client, db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, _, _ = create_test_incident_with_data(db_session, run_id)

    # 1. Trigger RCA via API
    resp = client.post(f"/api/v1/incidents/{inc.id}/rca")
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == inc.id
    analysis_id = data["analysis_id"]

    # 2. Get latest
    resp_latest = client.get(f"/api/v1/incidents/{inc.id}/rca")
    assert resp_latest.status_code == 200
    assert resp_latest.json()["analysis_id"] == analysis_id

    # 3. Get history
    resp_hist = client.get(f"/api/v1/incidents/{inc.id}/rca/history")
    assert resp_hist.status_code == 200
    assert resp_hist.json()["total"] >= 1

    # 4. Get by analysis_id
    resp_by_id = client.get(f"/api/v1/incidents/{inc.id}/rca/{analysis_id}")
    assert resp_by_id.status_code == 200
    assert resp_by_id.json()["analysis_id"] == analysis_id

    # 5. Nonexistent incident 404
    resp_404 = client.post("/api/v1/incidents/999999/rca")
    assert resp_404.status_code == 404


def test_immutability_guarantees(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, log, events = create_test_incident_with_data(db_session, run_id)
    initial_raw = log.raw_content
    initial_event_count = len(events)

    service = RCAService(db=db_session, provider=MockRCAProvider())
    service.run_incident_rca(inc.id)

    # Verify log raw_content unchanged
    refreshed_log = db_session.query(Log).filter(Log.id == log.id).first()
    assert refreshed_log.raw_content == initial_raw

    # Verify parsed_logs unchanged
    parsed_count = db_session.query(ParsedLog).filter(ParsedLog.log_id == log.id).count()
    assert parsed_count == initial_event_count

    # Verify incident_events unchanged
    ie_count = db_session.query(IncidentEvent).filter(IncidentEvent.incident_id == inc.id).count()
    assert ie_count == initial_event_count

    # Verify incident_contexts unchanged
    ctx_count = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).count()
    assert ctx_count == 4
