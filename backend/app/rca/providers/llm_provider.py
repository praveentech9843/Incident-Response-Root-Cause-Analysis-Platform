import json
import logging
from typing import Optional
import httpx
from pydantic import ValidationError

from app.rca.base import RCAProvider
from app.rca.evidence import RCAEvidencePackage
from app.rca.prompts import SYSTEM_PROMPT, build_user_prompt
from app.rca.schemas import (
    AnalysisStatus,
    RCAResult,
)

logger = logging.getLogger(__name__)


class LLMRCAProvider(RCAProvider):
    """
    Production-ready LLM provider using HTTP REST API (OpenAI-compatible / Anthropic / Gemini).
    Does NOT hardcode secrets or vendor SDKs; communicates over httpx.
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

    def analyze(self, package: RCAEvidencePackage) -> RCAResult:
        if package.total_events == 0:
            return RCAResult(
                analysis_status=AnalysisStatus.INSUFFICIENT_EVIDENCE,
                summary="Available evidence is insufficient to perform root cause analysis.",
                hypotheses=[],
                confidence=0.0,
                limitations=["No observed log events provided."],
                provider=self.provider_name,
                model=self.model_name,
            )

        user_content = build_user_prompt(package)
        endpoint = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
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

            # Ensure provider & model metadata are set
            parsed_data["provider"] = self.provider_name
            parsed_data["model"] = self.model_name

            return RCAResult.model_validate(parsed_data)

        except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValidationError) as exc:
            logger.error(f"LLM RCA Provider execution failed: {str(exc)}", exc_info=True)
            return RCAResult(
                analysis_status=AnalysisStatus.FAILED,
                summary=f"AI RCA Provider failed to complete analysis: {str(exc)}",
                hypotheses=[],
                confidence=0.0,
                limitations=[f"Provider error: {str(exc)}"],
                provider=self.provider_name,
                model=self.model_name,
            )
