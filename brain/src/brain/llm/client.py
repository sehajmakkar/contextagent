"""The only module that talks to Gemini (CLAUDE.md: no other module imports google.genai).

Stateless by design (ADR-019): we use `models.generate_content`, send everything
the model needs in each request, and ask Google not to log the request.
"""

import logging
import time
from dataclasses import dataclass
from typing import Literal, TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
ThinkingLevel = Literal["minimal", "low", "medium", "high"]


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class Usage:
    model: str
    prompt_tokens: int
    output_tokens: int
    thinking_tokens: int
    latency_ms: int


class LLMClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=120_000,  # ms
                # Exponential backoff with jitter on 408/429/5xx. Free-tier limits are low.
                retry_options=types.HttpRetryOptions(attempts=5, initial_delay=2.0, max_delay=60.0),
            ),
        )

    def generate_structured(
        self,
        *,
        schema: type[T],
        system: str,
        prompt: str,
        thinking_level: ThinkingLevel,
    ) -> tuple[T, Usage]:
        """One request whose reply must match `schema`. Validated again on our side."""
        start = time.perf_counter()
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    response_json_schema=schema.model_json_schema(),
                    thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    store=False,
                ),
            )
        except errors.APIError as e:  # raised after the SDK's retries are exhausted
            raise LLMError(f"Gemini API error {e.code}: {e.message}") from e
        usage = self._usage(response, start)

        candidate = response.candidates[0] if response.candidates else None
        if candidate is None or candidate.finish_reason != types.FinishReason.STOP:
            reason = candidate.finish_reason if candidate else response.prompt_feedback
            raise LLMError(f"Gemini did not finish normally: {reason}")

        log.info("llm %s prompt=%d out=%d thinking=%d %dms", self.model, usage.prompt_tokens,
                 usage.output_tokens, usage.thinking_tokens, usage.latency_ms)
        try:
            return schema.model_validate_json(response.text), usage
        except ValidationError as e:
            raise LLMError(f"Reply did not match {schema.__name__}: {e}") from e

    def _usage(self, response: types.GenerateContentResponse, start: float) -> Usage:
        meta = response.usage_metadata
        return Usage(
            model=self.model,
            prompt_tokens=(meta and meta.prompt_token_count) or 0,
            output_tokens=(meta and meta.candidates_token_count) or 0,
            thinking_tokens=(meta and meta.thoughts_token_count) or 0,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
