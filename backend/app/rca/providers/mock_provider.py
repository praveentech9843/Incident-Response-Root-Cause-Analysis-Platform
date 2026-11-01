from typing import List
from app.rca.base import RCAProvider
from app.rca.evidence import RCAEvidencePackage
from app.rca.schemas import (
    AnalysisStatus,
    CausalStatus,
    ConfidenceLevel,
    RCAHypothesis,
    RCAResult,
    RoleClassification,
)


class MockRCAProvider(RCAProvider):
    """
    Deterministic provider used for test verification.
    Formulates evidence-grounded hypotheses by analyzing earliest failure events
    and exceptions in the evidence package without invoking external LLMs.
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-rca-v1"

    def analyze(self, package: RCAEvidencePackage) -> RCAResult:
        if package.total_events == 0 or len(package.observed_evidence_items) == 0:
            return RCAResult(
                analysis_status=AnalysisStatus.INSUFFICIENT_EVIDENCE,
                summary="Available evidence is insufficient to determine a reliable root cause.",
                hypotheses=[],
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                limitations=["No observed log events available in incident package."],
                provider=self.provider_name,
                model=self.model_name,
            )

        # Find exception items and error events
        exceptions = [i for i in package.observed_evidence_items if i.evidence_type.value == "EXCEPTION"]
        error_events = [
            i for i in package.observed_evidence_items
            if i.evidence_type.value == "LOG_EVENT" and (i.details.get("level") or "").upper() in ["ERROR", "CRITICAL", "FATAL"]
        ]

        hypotheses: List[RCAHypothesis] = []

        if exceptions:
            # First exception is a strong root-cause candidate
            primary_exc = exceptions[0]
            related_evt_id = primary_exc.evidence_id.replace("EXC-", "EVT-")
            supporting = [primary_exc.evidence_id]
            if related_evt_id in package.get_observed_evidence_ids():
                supporting.append(related_evt_id)

            exc_type = primary_exc.details.get("exception_type") or "Failure"
            svc = primary_exc.details.get("service_name") or primary_exc.source

            hypotheses.append(
                RCAHypothesis(
                    hypothesis_id="HYP-1",
                    title=f"{svc} {exc_type}",
                    description=f"{svc} encountered an unhandled {exc_type} resulting in downstream service errors.",
                    confidence=0.85,
                    confidence_level=ConfidenceLevel.HIGH,
                    supporting_evidence=supporting,
                    contradicting_evidence=[],
                    reasoning=f"Observed exception {primary_exc.evidence_id} in {svc} matches earliest error cascade.",
                    causal_status=CausalStatus.SUPPORTED,
                    role=RoleClassification.ROOT_CAUSE_CANDIDATE,
                )
            )

        elif error_events:
            # Earliest error event as hypothesis
            earliest = error_events[0]
            svc = earliest.details.get("service_name") or "PrimaryService"
            hypotheses.append(
                RCAHypothesis(
                    hypothesis_id="HYP-1",
                    title=f"{svc} Error State",
                    description=f"Earliest observed failure was recorded in {svc}.",
                    confidence=0.75,
                    confidence_level=ConfidenceLevel.MEDIUM,
                    supporting_evidence=[earliest.evidence_id],
                    contradicting_evidence=[],
                    reasoning=f"Log event {earliest.evidence_id} shows error message: '{earliest.details.get('message', '')}'",
                    causal_status=CausalStatus.HYPOTHESIS,
                    role=RoleClassification.ROOT_CAUSE_CANDIDATE,
                )
            )
        elif package.observed_evidence_items:
            # Fall back to first observed log event
            first_item = package.observed_evidence_items[0]
            svc = first_item.details.get("service_name") or "PrimaryService"
            hypotheses.append(
                RCAHypothesis(
                    hypothesis_id="HYP-1",
                    title=f"{svc} Observed Event",
                    description=f"Initial anomaly observed in {svc}.",
                    confidence=0.65,
                    confidence_level=ConfidenceLevel.MEDIUM,
                    supporting_evidence=[first_item.evidence_id],
                    contradicting_evidence=[],
                    reasoning=f"Log event {first_item.evidence_id} recorded in incident context.",
                    causal_status=CausalStatus.HYPOTHESIS,
                    role=RoleClassification.ROOT_CAUSE_CANDIDATE,
                )
            )

        if not hypotheses:
            return RCAResult(
                analysis_status=AnalysisStatus.INSUFFICIENT_EVIDENCE,
                summary="Available evidence is insufficient to determine a reliable root cause.",
                hypotheses=[],
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                limitations=["No exception or error events found in evidence package."],
                provider=self.provider_name,
                model=self.model_name,
            )

        # Check for secondary failure as contributing factor or symptom
        if len(error_events) > 1:
            secondary = error_events[-1]
            if secondary.evidence_id not in hypotheses[0].supporting_evidence:
                sec_svc = secondary.details.get("service_name") or "SecondaryService"
                hypotheses.append(
                    RCAHypothesis(
                        hypothesis_id="HYP-2",
                        title=f"{sec_svc} Cascading Failure",
                        description=f"{sec_svc} reported errors temporally following the initial upstream incident.",
                        confidence=0.65,
                        confidence_level=ConfidenceLevel.MEDIUM,
                        supporting_evidence=[secondary.evidence_id],
                        contradicting_evidence=[],
                        reasoning=f"Downstream service {sec_svc} recorded error in event {secondary.evidence_id}.",
                        causal_status=CausalStatus.HYPOTHESIS,
                        role=RoleClassification.SYMPTOM,
                    )
                )

        summary = (
            f"Identified {len(hypotheses)} evidence-supported hypothesis(es) across "
            f"{len(package.service_names)} service(s). Primary candidate: {hypotheses[0].title}."
        )

        return RCAResult(
            analysis_status=AnalysisStatus.COMPLETED,
            summary=summary,
            hypotheses=hypotheses,
            confidence=0.80,
            confidence_level=ConfidenceLevel.HIGH,
            limitations=[],
            provider=self.provider_name,
            model=self.model_name,
        )
