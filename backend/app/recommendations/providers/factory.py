import logging
from typing import Optional

from app.core.config import Settings
from app.recommendations.base import RecommendationProvider
from app.recommendations.providers.llm_provider import LLMRecommendationProvider
from app.recommendations.providers.mock_provider import MockRecommendationProvider

logger = logging.getLogger(__name__)


def get_recommendation_provider(settings: Optional[Settings] = None) -> Optional[RecommendationProvider]:
    """
    Factory function returning the configured RecommendationProvider instance.
    Returns None if provider is disabled or missing required API keys.
    """
    if settings is None:
        from app.core.config import Settings
        settings = Settings()

    provider_type = (settings.RECOMMENDATION_PROVIDER or "none").lower()

    if provider_type == "mock":
        return MockRecommendationProvider()

    if provider_type in ("llm", "openai", "gemini", "anthropic"):
        api_key = settings.RECOMMENDATION_API_KEY
        if not api_key:
            logger.warning(
                f"Recommendation provider configured as '{provider_type}' but RECOMMENDATION_API_KEY is not set."
            )
            return None

        return LLMRecommendationProvider(
            api_key=api_key,
            model=settings.RECOMMENDATION_MODEL or "gpt-4o-mini",
            base_url=settings.RECOMMENDATION_BASE_URL or None,
        )

    return None
