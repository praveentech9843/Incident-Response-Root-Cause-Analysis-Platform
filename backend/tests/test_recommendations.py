import uuid
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.log import Log
from app.models.parsed_log import ParsedLog
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.incident_context import IncidentContext
from app.models.incident_rca import IncidentRCAAnalysis
from app.models.incident_recommendation import IncidentRecommendation
from app.recommendations.base import RecommendationProvider
from app.recommendations.evidence import RecommendationEvidenceBuilder, RecommendationInput
from app.recommendations.generator import RecommendationGenerator
from app.recommendations.providers.mock_provider import MockRecommendationProvider
from app.recommendations.schemas import (
    RecommendationConfidenceLevel,
    RecommendationGenerationStatus,
    RecommendationItem,
    RecommendationResult,
    RecommendationStatus,
    RecommendationType,
    RiskLevel,
)
from app.recommendations.validators import RecommendationValidator
from app.services.recommendation_service import RecommendationService


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
    """Clean tables before and after each test to maintain strict isolation."""
    from app.models.incident_investigation import (
        IncidentTimelineEvent,
        IncidentVerificationStep,
        IncidentRecommendationReview,
        IncidentInvestigationAction,
        IncidentInvestigationNote,
        IncidentInvestigation,
    )
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



def create_test_incident_with_rca(
    db_session,
    run_id: str,
    causal_status: str = "SUPPORTED",
    rca_status: str = "COMPLETED",
    hypotheses: list = None,
):
    """Helper to create a complete incident with parsed logs, contexts, and a validated RCA analysis."""
    # 1. Raw Log
    log = Log(
        original_filename=f"rec_{run_id}.log",
        file_type="log",
        raw_content=f"2026-10-07 10:00:00 ERROR OrderService: Connection timeout to Redis [req:{run_id}]\n",
        content_hash=f"hash-{run_id}",
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    # 2. Parsed Log
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
    db_session.add(p1)
    db_session.commit()
    db_session.refresh(p1)

    # 3. Incident
    inc = Incident(
        incident_key=f"inc-{run_id}",
        title="OrderService Redis Timeout Cluster",
        status="OPEN",
        event_count=1,
        service_count=1,
        correlation_reason="Cross-service temporal cluster",
    )
    db_session.add(inc)
    db_session.commit()
    db_session.refresh(inc)

    # 4. Incident Event
    ie = IncidentEvent(incident_id=inc.id, parsed_log_id=p1.id, event_index=0)
    db_session.add(ie)

    # 5. Incident Contexts
    ctx_service = IncidentContext(
        incident_id=inc.id,
        context_category="service",
        status="AVAILABLE",
        source="StaticCatalogProvider",
        data={"services": [{"name": "OrderService", "tier": "critical"}]},
    )
    ctx_metrics = IncidentContext(
        incident_id=inc.id,
        context_category="metrics",
        status="NOT_CONNECTED",
        source="NullMetricsProvider",
        data={},
    )
    ctx_deploy = IncidentContext(
        incident_id=inc.id,
        context_category="deployment",
        status="INTEGRATION_REQUIRED",
        source="NullDeploymentProvider",
        data={},
    )
    db_session.add_all([ctx_service, ctx_metrics, ctx_deploy])
    db_session.commit()

    # 6. RCA Analysis
    default_hypotheses = [
        {
            "hypothesis_id": "HYP-1",
            "title": "Redis Connection Pool Exhaustion in OrderService",
            "description": "OrderService experienced read timeout connecting to Redis.",
            "confidence": 0.85,
            "confidence_level": "HIGH",
            "supporting_evidence": [f"EVT-{p1.id}", f"EXC-{p1.id}"],
            "contradicting_evidence": [],
            "reasoning": "Observed timeout exceptions in log events.",
            "causal_status": causal_status,
            "role": "ROOT_CAUSE_CANDIDATE",
        }
    ]

    evidence_snapshot = {
        "services_involved": ["OrderService"],
        "observed_evidence_items": [
            {
                "evidence_id": f"EVT-{p1.id}",
                "evidence_type": "LOG_EVENT",
                "source": "parsed_logs",
                "description": "Connection timeout to Redis",
            },
            {
                "evidence_id": f"EXC-{p1.id}",
                "evidence_type": "EXCEPTION",
                "source": "parsed_logs",
                "description": "TimeoutException: Read timed out",
            },
        ],
        "unavailable_contexts": [
            {"category": "metrics", "status": "NOT_CONNECTED"},
            {"category": "deployment", "status": "INTEGRATION_REQUIRED"},
        ],
        "events": [
            {
                "event_id": p1.id,
                "service_name": "OrderService",
                "message": "Connection timeout to Redis",
            }
        ],
    }

    rca = IncidentRCAAnalysis(
        incident_id=inc.id,
        analysis_id=f"rca-{run_id}",
        analysis_status=rca_status,
        provider="mock",
        model="mock-rca-v1",
        summary="Redis Connection Pool Exhaustion in OrderService is supported by observed timeout exceptions.",
        confidence=0.85,
        confidence_level="HIGH",
        hypotheses=hypotheses if hypotheses is not None else default_hypotheses,
        evidence_snapshot=evidence_snapshot,
        limitations=["Metrics context unavailable", "Deployment metadata unavailable"],
    )
    db_session.add(rca)
    db_session.commit()
    db_session.refresh(rca)

    return inc, rca, p1, log


# 1. Recommendation generation from validated RCA
def test_recommendation_generation_from_validated_rca(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)

    service = RecommendationService(db=db_session)
    result = service.generate_recommendations(incident_id=inc.id)

    assert result.status == "COMPLETED"
    assert result.total_recommendations > 0
    assert result.rca_analysis_id == rca.id
    # Ensure types exist
    types = {r.type for r in result.recommendations}
    assert "INVESTIGATION" in types
    assert "DIAGNOSTIC_VERIFICATION" in types


# 2. No RCA -> recommendation generation rejected with 409
def test_no_rca_recommendation_generation_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc = Incident(
        incident_key=f"inc-no-rca-{run_id}",
        title="Incident without RCA",
        status="OPEN",
        event_count=0,
        service_count=0,
        correlation_reason="None",
    )
    db_session.add(inc)
    db_session.commit()

    service = RecommendationService(db=db_session)
    with pytest.raises(HTTPException) as exc_info:
        service.generate_recommendations(incident_id=inc.id)

    assert exc_info.value.status_code == 409
    assert "Validated RCA is required" in exc_info.value.detail


# 3. Evidence references are validated
def test_evidence_references_are_validated(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)

    rec_input = RecommendationEvidenceBuilder.build(inc, rca)
    observed_ids = rec_input.get_observed_evidence_ids()
    assert f"EVT-{p1.id}" in observed_ids
    assert f"EXC-{p1.id}" in observed_ids

    generator = RecommendationGenerator()
    result = generator.generate(rec_input)

    for rec in result.recommendations:
        for ev_id in rec.supporting_evidence:
            assert ev_id in observed_ids


# 4. Invalid evidence reference rejected / stripped
def test_invalid_evidence_reference_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-test-invalid-ev",
        type=RecommendationType.INVESTIGATION,
        title="Check OrderService",
        description="Check timeout logs",
        rationale="Timeout observed",
        supporting_evidence=[f"EVT-{p1.id}", "EVT-999999", "FAKE-EVIDENCE-ID"],
        confidence=0.8,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.LOW,
        expected_impact="Isolate issue",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    res_rec = validated.recommendations[0]
    assert "EVT-999999" not in res_rec.supporting_evidence
    assert "FAKE-EVIDENCE-ID" not in res_rec.supporting_evidence
    assert f"EVT-{p1.id}" in res_rec.supporting_evidence
    assert any("Nonexistent evidence reference" in lim for lim in validated.limitations)


# 5. Unknown service reference rejected / flagged
def test_unknown_service_reference_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-unknown-svc",
        type=RecommendationType.INVESTIGATION,
        title="Inspect InventoryService and BillingService",
        description="Verify BillingService timeout in incident",
        rationale="BillingService had failures",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.8,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.LOW,
        expected_impact="Isolate issue",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    assert any("BillingService" in lim and "not present" in lim for lim in validated.limitations)


# 6. Unavailable metric not treated as evidence
def test_unavailable_metric_not_treated_as_evidence(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-metric-claim",
        type=RecommendationType.INVESTIGATION,
        title="Analyze CPU saturation spike",
        description="CPU utilization reached 98% saturation spike during incident",
        rationale="CPU metric saturation caused timeout",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.8,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.LOW,
        expected_impact="Isolate issue",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    assert any("Metrics context was NOT_CONNECTED" in lim for lim in validated.limitations)


# 7. Unavailable deployment data not treated as evidence
def test_unavailable_deployment_data_not_treated_as_evidence(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-deploy-claim",
        type=RecommendationType.INVESTIGATION,
        title="Rollback commit deploy regression",
        description="Recent deploy release introduced regression causing failure",
        rationale="Commit release regression",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.8,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.LOW,
        expected_impact="Isolate issue",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    assert any("Deployment context was INTEGRATION_REQUIRED" in lim for lim in validated.limitations)


# 8. Hypothesis is not converted into confirmed fact
def test_hypothesis_not_converted_into_confirmed_fact(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id, causal_status="HYPOTHESIS")
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-fix-hyp",
        type=RecommendationType.FIX,
        title="Reconfigure timeout",
        description="Apply fix to OrderService",
        rationale="Proven root cause",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.9,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.MEDIUM,
        expected_impact="Fix the issue",
        prerequisites=[],
        verification_steps=["Step 1"],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    # Must be downgraded from FIX to DIAGNOSTIC_VERIFICATION because RCA causal_status is HYPOTHESIS
    assert validated.recommendations[0].type == RecommendationType.DIAGNOSTIC_VERIFICATION


# 9. Low confidence RCA produces investigation-oriented recommendations
def test_low_confidence_rca_produces_investigation_oriented_recommendations(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(
        db_session, run_id, causal_status="HYPOTHESIS", rca_status="COMPLETED"
    )
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    generator = RecommendationGenerator()
    result = generator.generate(rec_input)

    types = [r.type for r in result.recommendations]
    assert RecommendationType.INVESTIGATION in types
    # No FIX recommendations should remain when all hypotheses are HYPOTHESIS
    assert RecommendationType.FIX not in types


# 10. Medium confidence RCA produces verification-oriented recommendations
def test_medium_confidence_rca_produces_verification_oriented_recommendations(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(
        db_session, run_id, causal_status="HYPOTHESIS", rca_status="COMPLETED"
    )
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    generator = RecommendationGenerator()
    result = generator.generate(rec_input)

    types = [r.type for r in result.recommendations]
    assert RecommendationType.DIAGNOSTIC_VERIFICATION in types


# 11. High confidence RCA may produce fix recommendations
def test_high_confidence_rca_may_produce_fix_recommendations(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(
        db_session, run_id, causal_status="SUPPORTED", rca_status="COMPLETED"
    )
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    generator = RecommendationGenerator()
    result = generator.generate(rec_input)

    types = [r.type for r in result.recommendations]
    assert RecommendationType.FIX in types
    fix_rec = next(r for r in result.recommendations if r.type == RecommendationType.FIX)
    assert fix_rec.status == RecommendationStatus.REVIEW_REQUIRED


# 12. Unsupported configuration value rejected / sanitized
def test_unsupported_configuration_value_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-config-val",
        type=RecommendationType.INVESTIGATION,
        title="Set timeout to 30s for OrderService",
        description="Change timeout to 30 seconds and increase memory to 4GB",
        rationale="Timeout issue",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.8,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.LOW,
        expected_impact="Isolate issue",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    res_rec = validated.recommendations[0]
    assert "to 30s" not in res_rec.title
    assert "30 seconds" not in res_rec.description
    assert any("Unsupported specific configuration values detected" in lim for lim in validated.limitations)


# 13. Unsupported numerical impact rejected / sanitized
def test_unsupported_numerical_impact_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-impact-pct",
        type=RecommendationType.INVESTIGATION,
        title="Inspect logs",
        description="Inspect OrderService logs",
        rationale="Timeout observed",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.8,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.LOW,
        expected_impact="Will reduce errors by 87% across all endpoints",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    res_rec = validated.recommendations[0]
    assert "87%" not in res_rec.expected_impact
    assert any("Invented numerical impact percentages detected" in lim for lim in validated.limitations)


# 14. Destructive command rejected
def test_destructive_command_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-destructive",
        type=RecommendationType.INVESTIGATION,
        title="Run cleanup",
        description="Execute rm -rf /var/log/redis and DROP TABLE old_sessions",
        rationale="Free disk",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.8,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.HIGH,
        expected_impact="Cleanup",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    assert len(validated.recommendations) == 0
    assert any("Rejected recommendation" in lim and "forbidden execution" in lim for lim in validated.limitations)


# 15. Automatic remediation instruction rejected
def test_automatic_remediation_instruction_rejected(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-kubectl",
        type=RecommendationType.FIX,
        title="Restart pod with kubectl",
        description="Run kubectl rollout restart deployment/orderservice",
        rationale="Restart fixes hang",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.9,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.HIGH,
        expected_impact="Restore service",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    assert len(validated.recommendations) == 0


# 16. Risk classification works
def test_risk_classification_works(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id, causal_status="SUPPORTED")
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    generator = RecommendationGenerator()
    result = generator.generate(rec_input)

    for rec in result.recommendations:
        assert rec.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)
        if rec.type == RecommendationType.INVESTIGATION:
            assert rec.risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)


# 17. Confidence validation works
def test_confidence_validation_works(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    # Provider reports 0.99 with only 1 supporting evidence
    raw_rec = RecommendationItem(
        recommendation_id="rec-overconfident",
        type=RecommendationType.INVESTIGATION,
        title="Inspect OrderService",
        description="Check timeout logs",
        rationale="Timeout observed",
        supporting_evidence=[f"EVT-{p1.id}"],
        confidence=0.99,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.LOW,
        expected_impact="Isolate issue",
        prerequisites=[],
        verification_steps=[],
        status=RecommendationStatus.PROPOSED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    assert validated.recommendations[0].confidence <= 0.65
    assert validated.recommendations[0].confidence_level != RecommendationConfidenceLevel.HIGH


# 18. Recommendation persistence works
def test_recommendation_persistence_works(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)

    service = RecommendationService(db=db_session)
    response = service.generate_recommendations(incident_id=inc.id)

    db_recs = db_session.query(IncidentRecommendation).filter(IncidentRecommendation.incident_id == inc.id).all()
    assert len(db_recs) == response.total_recommendations
    assert len(db_recs) > 0
    assert db_recs[0].rca_analysis_id == rca.id


# 19. Recommendation history works
def test_recommendation_history_works(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)

    service = RecommendationService(db=db_session)
    service.generate_recommendations(incident_id=inc.id)

    history = service.get_recommendation_history(incident_id=inc.id)
    assert history.incident_id == inc.id
    assert history.total_recommendations > 0
    assert len(history.items) == history.total_recommendations


# 20. Multiple recommendation runs remain auditable
def test_multiple_recommendation_runs_remain_auditable(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)

    service = RecommendationService(db=db_session)
    run1 = service.generate_recommendations(incident_id=inc.id)
    import time
    time.sleep(0.05)
    run2 = service.generate_recommendations(incident_id=inc.id)

    all_recs = db_session.query(IncidentRecommendation).filter(IncidentRecommendation.incident_id == inc.id).all()
    assert len(all_recs) == run1.total_recommendations + run2.total_recommendations

    latest = service.get_latest_recommendations(incident_id=inc.id)
    assert latest.total_recommendations == run2.total_recommendations


# 21. Every FIX recommendation has verification steps
def test_every_fix_recommendation_has_verification_steps(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id, causal_status="SUPPORTED")
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    raw_rec = RecommendationItem(
        recommendation_id="rec-fix-no-steps",
        type=RecommendationType.FIX,
        title="Review connection pool configuration",
        description="Review pool configuration for OrderService",
        rationale="Timeout caused incident",
        supporting_evidence=[f"EVT-{p1.id}", f"EXC-{p1.id}"],
        confidence=0.85,
        confidence_level=RecommendationConfidenceLevel.HIGH,
        risk_level=RiskLevel.MEDIUM,
        expected_impact="Mitigate errors",
        prerequisites=[],
        verification_steps=[],  # Empty!
        status=RecommendationStatus.REVIEW_REQUIRED,
    )
    raw_result = RecommendationResult(
        status=RecommendationGenerationStatus.COMPLETED,
        analysis_id=rca.analysis_id,
        summary="Test",
        recommendations=[raw_rec],
        limitations=[],
        provider="test",
        model="test",
    )

    validated = RecommendationValidator.validate_and_refine(raw_result, rec_input)
    assert validated.recommendations[0].type == RecommendationType.FIX
    assert len(validated.recommendations[0].verification_steps) > 0
    assert any("Added mandatory verification steps" in lim for lim in validated.limitations)


# 22. Provider unavailable handled correctly
def test_provider_unavailable_handled_correctly(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    generator = RecommendationGenerator(provider=None)
    result = generator.generate(rec_input)

    assert result.status == RecommendationGenerationStatus.PROVIDER_UNAVAILABLE
    assert result.recommendations == []
    assert "not configured" in result.summary


# 23. Mock provider deterministic
def test_mock_provider_deterministic(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    rec_input = RecommendationEvidenceBuilder.build(inc, rca)

    provider = MockRecommendationProvider()
    res1 = provider.generate_recommendations(rec_input)
    res2 = provider.generate_recommendations(rec_input)

    assert len(res1.recommendations) == len(res2.recommendations)
    assert [r.type for r in res1.recommendations] == [r.type for r in res2.recommendations]


# 24. Raw logs unchanged
def test_raw_logs_unchanged(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, log = create_test_incident_with_rca(db_session, run_id)
    orig_content = log.raw_content
    orig_hash = log.content_hash

    service = RecommendationService(db=db_session)
    service.generate_recommendations(incident_id=inc.id)

    db_log = db_session.query(Log).filter(Log.id == log.id).one()
    assert db_log.raw_content == orig_content
    assert db_log.content_hash == orig_hash


# 25. Parsed logs unchanged
def test_parsed_logs_unchanged(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    orig_msg = p1.message
    orig_level = p1.level

    service = RecommendationService(db=db_session)
    service.generate_recommendations(incident_id=inc.id)

    db_parsed = db_session.query(ParsedLog).filter(ParsedLog.id == p1.id).one()
    assert db_parsed.message == orig_msg
    assert db_parsed.level == orig_level


# 26. Incident events unchanged
def test_incident_events_unchanged(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    orig_count = db_session.query(IncidentEvent).filter(IncidentEvent.incident_id == inc.id).count()

    service = RecommendationService(db=db_session)
    service.generate_recommendations(incident_id=inc.id)

    after_count = db_session.query(IncidentEvent).filter(IncidentEvent.incident_id == inc.id).count()
    assert orig_count == after_count


# 27. Incident context unchanged
def test_incident_context_unchanged(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    orig_contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    orig_len = len(orig_contexts)

    service = RecommendationService(db=db_session)
    service.generate_recommendations(incident_id=inc.id)

    after_contexts = db_session.query(IncidentContext).filter(IncidentContext.incident_id == inc.id).all()
    assert len(after_contexts) == orig_len


# 28. RCA analyses unchanged
def test_rca_analyses_unchanged(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(db_session, run_id)
    orig_summary = rca.summary
    orig_hypotheses = rca.hypotheses

    service = RecommendationService(db=db_session)
    service.generate_recommendations(incident_id=inc.id)

    db_rca = db_session.query(IncidentRCAAnalysis).filter(IncidentRCAAnalysis.id == rca.id).one()
    assert db_rca.summary == orig_summary
    assert db_rca.hypotheses == orig_hypotheses


# 29. Insufficient evidence RCA produces investigation only
def test_insufficient_evidence_rca_produces_investigation_only(db_session):
    run_id = uuid.uuid4().hex[:8]
    inc, rca, p1, _ = create_test_incident_with_rca(
        db_session,
        run_id,
        rca_status="INSUFFICIENT_EVIDENCE",
        hypotheses=[],
    )

    service = RecommendationService(db=db_session)
    result = service.generate_recommendations(incident_id=inc.id)

    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.total_recommendations > 0
    # FIX recommendations strictly forbidden
    for rec in result.recommendations:
        assert rec.type != "FIX"
        assert rec.type in ("INVESTIGATION", "DIAGNOSTIC_VERIFICATION")
