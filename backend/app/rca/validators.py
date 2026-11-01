import re
from typing import Any, Dict, List, Set, Tuple
from app.rca.evidence import RCAEvidencePackage
from app.rca.schemas import (
    AnalysisStatus,
    CausalStatus,
    ConfidenceLevel,
    RCAHypothesis,
    RCAResult,
    RoleClassification,
)


class RCAValidationException(Exception):
    """Raised when an RCA result fails structural or integrity validation."""
    pass


class RCAValidator:
    """
    Strict evidence-grounded validation engine.
    Detects hallucinations, unsupported causal assertions, invalid evidence IDs,
    fabricated services, and unsubstantiated confidence values.
    """

    # Common hallucinated metrics or infra keywords to check against unavailable contexts
    METRIC_KEYWORDS = ["cpu", "memory", "ram", "p95", "p99", "latency ms", "utilization %", "usage %"]
    DEPLOY_KEYWORDS = ["git commit", "build number", "deployment version", "deployed commit"]
    INFRA_KEYWORDS = ["k8s cluster", "kubernetes node", "pod crashed", "container restart"]

    @classmethod
    def validate_and_refine(
        cls,
        raw_result: RCAResult,
        package: RCAEvidencePackage,
    ) -> RCAResult:
        """
        Validates every hypothesis, evidence reference, and confidence score against
        the actual evidence package. Adjusts or downgrades claims where necessary.
        """
        valid_evidence_ids: Set[str] = package.get_observed_evidence_ids()
        known_services: Set[str] = package.get_known_services()
        unavailable_categories: Set[str] = {
            item["category"].lower() for item in package.unavailable_contexts
        }

        # If evidence package had 0 events, enforce INSUFFICIENT_EVIDENCE
        if package.total_events == 0 or len(valid_evidence_ids) == 0:
            return RCAResult(
                analysis_status=AnalysisStatus.INSUFFICIENT_EVIDENCE,
                summary="Available evidence is insufficient to determine a reliable root cause.",
                hypotheses=[],
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                limitations=cls._build_limitations(package, ["No correlated log events available for analysis."]),
                provider=raw_result.provider,
                model=raw_result.model,
            )

        validated_hypotheses: List[RCAHypothesis] = []
        limitations: List[str] = list(raw_result.limitations or [])

        for hyp in raw_result.hypotheses:
            # 1. Validate Cited Evidence IDs
            verified_supporting: List[str] = []
            invalid_citations: List[str] = []
            for ev_id in hyp.supporting_evidence:
                if ev_id in valid_evidence_ids:
                    verified_supporting.append(ev_id)
                else:
                    invalid_citations.append(ev_id)

            if invalid_citations:
                limitations.append(
                    f"Hypothesis '{hyp.title}' cited nonexistent or unobserved evidence IDs {invalid_citations}, which were stripped."
                )

            # If no verified evidence remains, downgrade or skip
            if not verified_supporting:
                limitations.append(
                    f"Hypothesis '{hyp.title}' had no verified evidence and was classified as UNVERIFIED."
                )
                hyp.causal_status = CausalStatus.UNVERIFIED
                hyp.confidence = 0.1
                hyp.confidence_level = ConfidenceLevel.LOW
                hyp.supporting_evidence = []
                validated_hypotheses.append(hyp)
                continue

            # 2. Check for Hallucinated Unavailable Context Assertions
            combined_text = f"{hyp.title} {hyp.description} {hyp.reasoning}".lower()
            if "metrics" in unavailable_categories:
                for kw in cls.METRIC_KEYWORDS:
                    if kw in combined_text and ("%" in combined_text or "ms" in combined_text):
                        limitations.append(
                            f"Metrics context was NOT_CONNECTED; numerical metric claim in '{hyp.title}' cannot be verified."
                        )
                        # Downgrade causal status
                        if hyp.causal_status == CausalStatus.CONFIRMED:
                            hyp.causal_status = CausalStatus.HYPOTHESIS

            if "deployment" in unavailable_categories:
                for kw in cls.DEPLOY_KEYWORDS:
                    if kw in combined_text:
                        limitations.append(
                            f"Deployment context was INTEGRATION_REQUIRED; commit claim in '{hyp.title}' is unverified."
                        )

            # 3. Check for Fabricated Services
            # Extract potential CamelCase or PascalCase service identifiers
            words = re.findall(r"\b[A-Z][a-zA-Z0-9_-]+Service\b", f"{hyp.title} {hyp.description}")
            for w in words:
                if known_services and w not in known_services:
                    limitations.append(
                        f"Service '{w}' cited in hypothesis '{hyp.title}' is not present in incident data."
                    )

            # 4. Enforce Principle: Correlation != Causation (Never allow unverified CONFIRMED)
            # A hypothesis can only be CONFIRMED if there is an explicit exception/stack trace
            # with multiple corroborating events. Otherwise downgrade to SUPPORTED or HYPOTHESIS.
            causal_status = hyp.causal_status
            if causal_status == CausalStatus.CONFIRMED:
                has_exception_or_trace = any(
                    ev_id.startswith("EXC-") or ev_id.startswith("ST-") for ev_id in verified_supporting
                )
                if not (has_exception_or_trace and len(verified_supporting) >= 2):
                    causal_status = CausalStatus.SUPPORTED
                    limitations.append(
                        f"Hypothesis '{hyp.title}' downgraded from CONFIRMED to SUPPORTED: causal direction requires deeper corroboration."
                    )

            # 5. Deterministic Confidence Bounding
            bounded_confidence, confidence_level = cls._bound_confidence(
                reported_confidence=hyp.confidence,
                supporting_count=len(verified_supporting),
                contradicting_count=len(hyp.contradicting_evidence or []),
                causal_status=causal_status,
            )

            refined_hyp = RCAHypothesis(
                hypothesis_id=hyp.hypothesis_id,
                title=hyp.title,
                description=hyp.description,
                confidence=bounded_confidence,
                confidence_level=confidence_level,
                supporting_evidence=verified_supporting,
                contradicting_evidence=hyp.contradicting_evidence or [],
                reasoning=hyp.reasoning,
                causal_status=causal_status,
                role=hyp.role or RoleClassification.ROOT_CAUSE_CANDIDATE,
            )
            validated_hypotheses.append(refined_hyp)

        # 6. Overall Analysis Level
        limitations = cls._build_limitations(package, limitations)

        if not validated_hypotheses:
            return RCAResult(
                analysis_status=AnalysisStatus.INSUFFICIENT_EVIDENCE,
                summary="Available evidence is insufficient to determine a reliable root cause.",
                hypotheses=[],
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                limitations=limitations,
                provider=raw_result.provider,
                model=raw_result.model,
            )

        # Compute overall confidence
        avg_conf = sum(h.confidence for h in validated_hypotheses) / len(validated_hypotheses)
        overall_level = (
            ConfidenceLevel.HIGH
            if avg_conf >= 0.75
            else (ConfidenceLevel.MEDIUM if avg_conf >= 0.40 else ConfidenceLevel.LOW)
        )

        return RCAResult(
            analysis_status=AnalysisStatus.COMPLETED,
            summary=raw_result.summary,
            hypotheses=validated_hypotheses,
            confidence=round(avg_conf, 2),
            confidence_level=overall_level,
            limitations=limitations,
            provider=raw_result.provider,
            model=raw_result.model,
        )

    @classmethod
    def _bound_confidence(
        cls,
        reported_confidence: float,
        supporting_count: int,
        contradicting_count: int,
        causal_status: CausalStatus,
    ) -> Tuple[float, ConfidenceLevel]:
        """
        Deterministically caps and validates confidence based on factual evidence strength.
        Prevents LLM from assigning arbitrary 0.99 confidence to uncorroborated assertions.
        """
        # Base cap by evidence count
        if supporting_count == 0:
            cap = 0.10
        elif supporting_count == 1:
            cap = 0.50
        elif supporting_count in (2, 3):
            cap = 0.80
        else:
            cap = 0.95

        # Penalty for contradictions
        cap -= (contradicting_count * 0.15)
        cap = max(0.05, cap)

        # Cap by causal status
        if causal_status == CausalStatus.UNVERIFIED:
            cap = min(cap, 0.30)
        elif causal_status == CausalStatus.HYPOTHESIS:
            cap = min(cap, 0.70)
        elif causal_status == CausalStatus.SUPPORTED:
            cap = min(cap, 0.88)

        final_conf = round(min(reported_confidence, cap), 2)
        if final_conf >= 0.75:
            level = ConfidenceLevel.HIGH
        elif final_conf >= 0.40:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return final_conf, level

    @classmethod
    def _build_limitations(
        cls,
        package: RCAEvidencePackage,
        existing_limitations: List[str],
    ) -> List[str]:
        """Ensures all unavailable context categories are transparently reported in limitations."""
        limitations = list(dict.fromkeys(existing_limitations))  # preserve order without duplicates
        for unavail in package.unavailable_contexts:
            cat = unavail["category"].capitalize()
            status = unavail["status"]
            notice = f"{cat} telemetry is {status}; cannot verify runtime {cat.lower()} state."
            if notice not in limitations:
                limitations.append(notice)
        return limitations
