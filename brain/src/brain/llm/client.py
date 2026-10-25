"""The only module that talks to Gemini (CLAUDE.md: no other module imports google.genai).

Stateless by design (ADR-019): we use `models.generate_content`, send everything
the model needs in each request, and ask Google not to log the request.
"""

import logging
import random
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


class QuotaExhausted(LLMError):
    """A per-day (or long) quota is used up. Retrying now is pointless, so stop the batch."""

    def __init__(self, message: str, retry_after_s: float | None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


MAX_RATE_LIMIT_WAIT_S = 60  # a per-minute limit asks us to wait seconds; longer means a daily limit


def quota_info(details: object) -> tuple[bool, float | None]:
    """Read Google's 429 body: is it a per-day quota, and how long does the server say to wait?"""
    error = details.get("error", details) if isinstance(details, dict) else {}
    daily, delay = False, None
    for d in error.get("details", []) if isinstance(error, dict) else []:
        kind = d.get("@type", "")
        if kind.endswith("RetryInfo"):
            delay = float(str(d.get("retryDelay", "0s")).rstrip("s") or 0)
        elif kind.endswith("QuotaFailure"):
            daily |= any("PerDay" in v.get("quotaId", "") for v in d.get("violations", []))
    return daily, delay


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
                # The SDK retries transient failures with exponential backoff and jitter.
                # 429 is excluded: we read Google's RetryInfo/QuotaFailure ourselves (see _call).
                retry_options=types.HttpRetryOptions(attempts=5, initial_delay=2.0, max_delay=60.0,
                                                     http_status_codes=[408, 500, 502, 503, 504]),
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
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            store=False,
        )
        response = self._call(prompt, config)
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

    def embed(self, text: str, *, model: str, dims: int) -> list[float]:
        """One text → one vector. (gemini-embedding-2 merges a *list* of inputs into one vector, so never batch.)"""
        def call():
            return self._client.models.embed_content(
                model=model, contents=text, config=types.EmbedContentConfig(output_dimensionality=dims))
        result = self._with_rate_limits(call, model)
        return list(result.embeddings[0].values)

    def _call(self, prompt: str, config: types.GenerateContentConfig):
        return self._with_rate_limits(
            lambda: self._client.models.generate_content(model=self.model, contents=prompt, config=config), self.model)

    def _with_rate_limits(self, call, model: str, rate_limit_retries: int = 3):
        for attempt in range(rate_limit_retries + 1):
            try:
                return call()
            except errors.APIError as e:
                if e.code != 429:
                    raise LLMError(f"Gemini API error {e.code}: {e.message}") from e
                daily, delay = quota_info(e.details)
                if daily or (delay or 0) > MAX_RATE_LIMIT_WAIT_S or attempt == rate_limit_retries:
                    hours = f" (retry in {delay / 3600:.1f}h)" if delay and delay > 3600 else ""
                    raise QuotaExhausted(f"Gemini quota exhausted for {model}{hours}", delay) from e
                wait = (delay or 2 ** attempt * 5) + random.uniform(0, 1)  # the server's delay, plus jitter
                log.warning("rate limited by %s, waiting %.0fs (attempt %d)", model, wait, attempt + 1)
                time.sleep(wait)
        raise AssertionError("unreachable")

    def _usage(self, response: types.GenerateContentResponse, start: float) -> Usage:
        meta = response.usage_metadata
        return Usage(
            model=self.model,
            prompt_tokens=(meta and meta.prompt_token_count) or 0,
            output_tokens=(meta and meta.candidates_token_count) or 0,
            thinking_tokens=(meta and meta.thoughts_token_count) or 0,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )
