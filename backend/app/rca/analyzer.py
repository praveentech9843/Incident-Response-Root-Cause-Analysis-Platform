from typing import Optional
from app.rca.base import RCAProvider
from app.rca.evidence import RCAEvidencePackage
from app.rca.providers.factory import get_rca_provider
from app.rca.schemas import (
    AnalysisStatus,
    ConfidenceLevel,
    RCAResult,
)
from app.rca.validators import RCAValidator


_USE_DEFAULT_PROVIDER = object()


class RootCauseAnalyzer:
    """
    High-level Root Cause Analysis orchestrator.
    Executes reasoning over controlled evidence packages, guards against provider absence,
    and runs the strict anti-hallucination validation pipeline.
    """

    def __init__(self, provider: Optional[RCAProvider] = _USE_DEFAULT_PROVIDER):  # type: ignore
        if provider is _USE_DEFAULT_PROVIDER:
            self._provider = get_rca_provider()
        else:
            self._provider = provider

    @property
    def provider(self) -> Optional[RCAProvider]:
        return self._provider

    def analyze(self, package: RCAEvidencePackage) -> RCAResult:
        # 1. Check if Provider is Configured
        active_provider = self.provider
        if active_provider is None:
            return RCAResult(
                analysis_status=AnalysisStatus.PROVIDER_UNAVAILABLE,
                summary="AI Root Cause Analysis provider is not configured.",
                hypotheses=[],
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                limitations=[
                    "No AI provider or API key configured. Configure RCA_PROVIDER and RCA_API_KEY in environment."
                ],
                provider="none",
                model="none",
            )

        # 2. Check for Insufficient Evidence
        if package.total_events == 0 or len(package.observed_evidence_items) == 0:
            return RCAResult(
                analysis_status=AnalysisStatus.INSUFFICIENT_EVIDENCE,
                summary="Available evidence is insufficient to determine a reliable root cause.",
                hypotheses=[],
                confidence=0.0,
                confidence_level=ConfidenceLevel.LOW,
                limitations=RCAValidator._build_limitations(package, ["No correlated log events available for analysis."]),
                provider=active_provider.provider_name,
                model=active_provider.model_name,
            )

        # 3. Call AI Provider
        raw_result = active_provider.analyze(package)

        # 4. Strict Evidence Validation & Anti-Hallucination Pipeline
        validated_result = RCAValidator.validate_and_refine(raw_result, package)

        return validated_result
