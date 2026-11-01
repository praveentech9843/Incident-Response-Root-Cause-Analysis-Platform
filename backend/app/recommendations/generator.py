from typing import Optional

from app.recommendations.base import RecommendationProvider
from app.recommendations.evidence import RecommendationInput
from app.recommendations.providers.factory import get_recommendation_provider
from app.recommendations.schemas import (
    RecommendationGenerationStatus,
    RecommendationResult,
)
from app.recommendations.validators import RecommendationValidator

_USE_DEFAULT_PROVIDER = object()


class RecommendationGenerator:
    """
    High-level orchestrator for Evidence-Grounded Investigation and Fix Recommendations.
    Guarantees provider decoupling, handles provider unavailability gracefully,
    and enforces strict safety and anti-hallucination validation before accepting any recommendation.
    """

    def __init__(self, provider: Optional[RecommendationProvider] = _USE_DEFAULT_PROVIDER):  # type: ignore
        if provider is _USE_DEFAULT_PROVIDER:
            self._provider = get_recommendation_provider()
        else:
            self._provider = provider

    @property
    def provider(self) -> Optional[RecommendationProvider]:
        return self._provider

    def generate(self, rec_input: RecommendationInput) -> RecommendationResult:
        active_provider = self.provider

        # 1. Check if Provider is Configured
        if active_provider is None:
            return RecommendationResult(
                status=RecommendationGenerationStatus.PROVIDER_UNAVAILABLE,
                analysis_id=rec_input.rca_analysis_id,
                summary="AI Recommendation provider is not configured.",
                recommendations=[],
                limitations=[
                    "No AI recommendation provider or API key configured. Configure RECOMMENDATION_PROVIDER in environment."
                ],
                provider="none",
                model="none",
            )

        # 2. Call Active Provider
        raw_result = active_provider.generate_recommendations(rec_input)

        # 3. Apply Multi-Layer Anti-Hallucination & Safety Validation
        validated_result = RecommendationValidator.validate_and_refine(raw_result, rec_input)

        return validated_result
