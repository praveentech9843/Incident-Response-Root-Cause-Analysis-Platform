import json
import logging
from typing import Optional
import httpx
from pydantic import ValidationError

from app.recommendations.base import RecommendationProvider
from app.recommendations.evidence import RecommendationInput
from app.recommendations.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    RECOMMENDATION_USER_PROMPT,
)
from app.recommendations.schemas import (
    RecommendationGenerationStatus,
    RecommendationResult,
)

logger = logging.getLogger(__name__)


class LLMRecommendationProvider(RecommendationProvider):
    """
    Production-ready LLM Recommendation provider communicating with OpenAI-compatible APIs over HTTP.
    Never executes actions or leaks secrets.
    """

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ):
        self.api_key = api_key
        self._model = model or "gpt-4o-mini"
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "llm"

    @property
    def model_name(self) -> str:
        return self._model

    def generate_recommendations(self, rec_input: RecommendationInput) -> RecommendationResult:
        user_content = RECOMMENDATION_USER_PROMPT.format(
            incident_id=rec_input.incident_id,
            incident_key=rec_input.incident_key,
            incident_title=rec_input.incident_title,
            services=", ".join(rec_input.services_involved) if rec_input.services_involved else "N/A",
            rca_analysis_id=rec_input.rca_analysis_id,
            rca_status=rec_input.rca_status,
            rca_summary=rec_input.rca_summary,
            hypotheses_json=json.dumps(rec_input.hypotheses, indent=2),
            observed_evidence_json=json.dumps(rec_input.evidence_snapshot.get("observed_evidence_items", []), indent=2),
            unavailable_context_json=json.dumps(rec_input.unavailable_contexts, indent=2),
            limitations_json=json.dumps(rec_input.limitations, indent=2),
        )

        endpoint = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": RECOMMENDATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                response_json = response.json()

            message_content = response_json["choices"][0]["message"]["content"]
            parsed_data = json.loads(message_content)

            parsed_data["provider"] = self.provider_name
            parsed_data["model"] = self.model_name
            if "analysis_id" not in parsed_data:
                parsed_data["analysis_id"] = rec_input.rca_analysis_id

            return RecommendationResult.model_validate(parsed_data)

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValidationError) as exc:
            logger.error(f"LLM Recommendation Provider execution failed: {str(exc)}", exc_info=True)
            return RecommendationResult(
                status=RecommendationGenerationStatus.FAILED,
                analysis_id=rec_input.rca_analysis_id,
                summary=f"AI Recommendation Provider failed: {str(exc)}",
                recommendations=[],
                limitations=[f"Provider error: {str(exc)}"],
                provider=self.provider_name,
                model=self.model_name,
            )
