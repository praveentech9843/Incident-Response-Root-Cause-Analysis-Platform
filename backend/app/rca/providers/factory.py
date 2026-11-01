from typing import Optional
from app.core.config import settings
from app.rca.base import RCAProvider
from app.rca.providers.mock_provider import MockRCAProvider
from app.rca.providers.llm_provider import LLMRCAProvider


def get_rca_provider() -> Optional[RCAProvider]:
    """
    Factory function returning the configured RCA provider instance.
    Returns None if no provider or API key is configured.
    """
    provider_type = (settings.RCA_PROVIDER or "none").strip().lower()

    if provider_type == "mock":
        return MockRCAProvider()

    if provider_type in ("llm", "openai", "gemini", "anthropic"):
        api_key = (settings.RCA_API_KEY or "").strip()
        if not api_key:
            return None
        return LLMRCAProvider(
            api_key=api_key,
            model=settings.RCA_MODEL if settings.RCA_MODEL != "none" else None,
            base_url=settings.RCA_BASE_URL or None,
        )

    return None
