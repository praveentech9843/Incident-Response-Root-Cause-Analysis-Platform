from abc import ABC, abstractmethod
from app.recommendations.evidence import RecommendationInput
from app.recommendations.schemas import RecommendationResult


class RecommendationProvider(ABC):
    """
    Abstract provider interface for evidence-grounded investigation & fix recommendations.
    Decouples recommendation logic from specific AI engines or deterministic mocks.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'mock', 'openai', 'gemini')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Underlying model identifier (e.g. 'mock-rec-v1', 'gpt-4o')."""
        pass

    @abstractmethod
    def generate_recommendations(self, rec_input: RecommendationInput) -> RecommendationResult:
        """
        Generate operational recommendations reasoning strictly over the supplied
        RecommendationInput context.
        """
        pass
