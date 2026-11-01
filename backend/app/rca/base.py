from abc import ABC, abstractmethod
from app.rca.evidence import RCAEvidencePackage
from app.rca.schemas import RCAResult


class RCAProvider(ABC):
    """Abstract interface for AI Root Cause Analysis engines."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'mock', 'openai', 'gemini')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the model used for analysis."""
        pass

    @abstractmethod
    def analyze(self, package: RCAEvidencePackage) -> RCAResult:
        """
        Executes root cause reasoning over the supplied controlled evidence package.
        Returns a structured RCAResult.
        """
        pass
