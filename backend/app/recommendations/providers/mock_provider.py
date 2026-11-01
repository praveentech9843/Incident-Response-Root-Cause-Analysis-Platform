import uuid
from typing import List
from app.recommendations.base import RecommendationProvider
from app.recommendations.evidence import RecommendationInput
from app.recommendations.schemas import (
    RecommendationConfidenceLevel,
    RecommendationGenerationStatus,
    RecommendationItem,
    RecommendationResult,
    RecommendationStatus,
    RecommendationType,
    RiskLevel,
)


class MockRecommendationProvider(RecommendationProvider):
    """
    Deterministic recommendation provider for testing and offline environments.
    Strictly uses real evidence IDs from the RCA package.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-rec-v1"

    def generate_recommendations(self, rec_input: RecommendationInput) -> RecommendationResult:
        analysis_id = rec_input.rca_analysis_id
        valid_evidence_ids = list(rec_input.get_observed_evidence_ids())

        # Case 1: Insufficient Evidence in RCA
        if rec_input.is_insufficient_evidence():
            ev_list = valid_evidence_ids[:1] if valid_evidence_ids else []
            recs = [
                RecommendationItem(
                    recommendation_id=f"rec-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.INVESTIGATION,
                    title="Collect additional log telemetry across correlated window",
                    description="Current incident data lacks sufficient event volume to formulate actionable fixes. Inspect external observability logs.",
                    rationale="Underlying RCA confirmed insufficient evidence to determine reliable causal factors.",
                    supporting_evidence=ev_list,
                    confidence=0.40,
                    confidence_level=RecommendationConfidenceLevel.LOW,
                    risk_level=RiskLevel.LOW,
                    expected_impact="Enable causal determination once additional event telemetry is captured.",
                    prerequisites=[],
                    verification_steps=["Verify ingestion pipeline coverage for the affected service."],
                    status=RecommendationStatus.REVIEW_REQUIRED,
                ),
                RecommendationItem(
                    recommendation_id=f"rec-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.DIAGNOSTIC_VERIFICATION,
                    title="Connect metrics telemetry for infrastructure and container health",
                    description="Telemetry integrations for CPU, memory, and container status are currently disconnected.",
                    rationale="Metrics context status is NOT_CONNECTED or UNAVAILABLE.",
                    supporting_evidence=ev_list,
                    confidence=0.40,
                    confidence_level=RecommendationConfidenceLevel.LOW,
                    risk_level=RiskLevel.LOW,
                    expected_impact="Eliminate telemetry blind spots for ongoing and future incident triage.",
                    prerequisites=[],
                    verification_steps=["Confirm metric telemetry endpoint connectivity and scraper status."],
                    status=RecommendationStatus.REVIEW_REQUIRED,
                ),
            ]
            return RecommendationResult(
                status=RecommendationGenerationStatus.INSUFFICIENT_EVIDENCE,
                analysis_id=analysis_id,
                summary="Available RCA evidence is insufficient for prescriptive fixes; prioritizing investigation and observability enhancements.",
                recommendations=recs,
                limitations=["Metrics context unavailable", "Deployment metadata unavailable"],
                provider=self.provider_name,
                model=self.model_name,
            )

        # Case 2: Evidence-backed RCA
        recommendations: List[RecommendationItem] = []
        hypotheses = rec_input.hypotheses or []

        for idx, hyp in enumerate(hypotheses[:3]):
            title = hyp.get("title", f"Hypothesis {idx + 1}")
            causal_status = hyp.get("causal_status", "HYPOTHESIS")
            hyp_evidence = hyp.get("supporting_evidence", [])
            # Ensure grounded evidence citations
            cited_evidence = [e for e in hyp_evidence if e in valid_evidence_ids]
            if not cited_evidence and valid_evidence_ids:
                cited_evidence = valid_evidence_ids[:2]

            # Investigation Recommendation
            recommendations.append(
                RecommendationItem(
                    recommendation_id=f"rec-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.INVESTIGATION,
                    title=f"Inspect operational behavior for {title}",
                    description=f"Inspect detailed component behavior and verify upstream call boundaries around {title}.",
                    rationale=f"Observed evidence indicates abnormal behavior associated with {title}.",
                    supporting_evidence=cited_evidence,
                    confidence=0.72,
                    confidence_level=RecommendationConfidenceLevel.MEDIUM,
                    risk_level=RiskLevel.LOW,
                    expected_impact="Clarify sequence of failure events and isolate boundary condition.",
                    prerequisites=[],
                    verification_steps=[
                        "Compare log timestamps against downstream service request timelines.",
                        "Inspect error return codes from external boundary calls.",
                    ],
                    status=RecommendationStatus.REVIEW_REQUIRED,
                )
            )

            # Diagnostic Verification Recommendation
            recommendations.append(
                RecommendationItem(
                    recommendation_id=f"rec-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.DIAGNOSTIC_VERIFICATION,
                    title=f"Verify error rates and downstream dependencies for {title}",
                    description=f"Perform diagnostic health check and verify error rates during the incident window for {title}.",
                    rationale=f"Validates whether {title} was a localized symptom or a sustained error state.",
                    supporting_evidence=cited_evidence,
                    confidence=0.70,
                    confidence_level=RecommendationConfidenceLevel.MEDIUM,
                    risk_level=RiskLevel.LOW,
                    expected_impact="Confirm or refute whether this condition persisted beyond the observed incident window.",
                    prerequisites=[],
                    verification_steps=[
                        "Inspect service availability check endpoints for consecutive 5xx errors.",
                        "Check dependency connectivity and timeout thresholds.",
                    ],
                    status=RecommendationStatus.REVIEW_REQUIRED,
                )
            )

            # Fix Recommendation (only if supported/confirmed)
            if causal_status in ("SUPPORTED", "CONFIRMED"):
                recommendations.append(
                    RecommendationItem(
                        recommendation_id=f"rec-{uuid.uuid4().hex[:8]}",
                        type=RecommendationType.FIX,
                        title=f"Review connection and timeout configuration related to {title}",
                        description=f"Review operational timeout and retry settings for components participating in {title}.",
                        rationale=f"Supported RCA findings indicate that timeout and boundary failure in {title} contributed to incident impact.",
                        supporting_evidence=cited_evidence,
                        confidence=0.82,
                        confidence_level=RecommendationConfidenceLevel.HIGH,
                        risk_level=RiskLevel.MEDIUM,
                        expected_impact="Mitigate repeated boundary timeout failures if settings are aligned with downstream limits.",
                        prerequisites=["Review current configuration against baseline standards in staging environment."],
                        verification_steps=[
                            "Verify current timeout configuration matches approved operational baseline.",
                            "Monitor error rates and latency post-adjustment in staging.",
                            "Confirm no new cascading timeout exceptions in dependent services.",
                        ],
                        status=RecommendationStatus.REVIEW_REQUIRED,
                    )
                )

            # Prevention Recommendation
            recommendations.append(
                RecommendationItem(
                    recommendation_id=f"rec-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.PREVENTION,
                    title=f"Establish proactive alert thresholds for {title}",
                    description=f"Configure alerting on elevated error rates and timeout spikes for components in {title}.",
                    rationale="Early detection prevents cascading degradation across dependent microservices.",
                    supporting_evidence=cited_evidence,
                    confidence=0.75,
                    confidence_level=RecommendationConfidenceLevel.MEDIUM,
                    risk_level=RiskLevel.LOW,
                    expected_impact="Reduce time-to-detect for recurrent incidents of this failure pattern.",
                    prerequisites=[],
                    verification_steps=["Simulate alert trigger in non-production environment."],
                    status=RecommendationStatus.PROPOSED,
                )
            )

        return RecommendationResult(
            status=RecommendationGenerationStatus.COMPLETED,
            analysis_id=analysis_id,
            summary=f"Formulated {len(recommendations)} evidence-grounded recommendations prioritizing investigation and verification.",
            recommendations=recommendations,
            limitations=rec_input.limitations,
            provider=self.provider_name,
            model=self.model_name,
        )
