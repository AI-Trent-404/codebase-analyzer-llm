"""
LangChain + Anthropic Claude integration.

Everything that touches the model lives behind this class so the rest of the
pipeline is provider-agnostic and easily testable. Responsibilities:

* Build a ``ChatAnthropic`` client from settings.
* Expose typed, structured-output calls via ``with_structured_output`` — the model
  is *forced* to return an object matching a Pydantic schema, giving us reliable,
  machine-readable JSON with no text parsing.
* Retry transient failures (rate limits, 5xx) with exponential backoff.
* Track token usage and estimate cost, thread-safely, across concurrent calls.
"""
from __future__ import annotations

import threading
from typing import TypeVar

from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings

T = TypeVar("T", bound=BaseModel)


class UsageTracker:
    """Thread-safe accumulator for tokens/cost across concurrent LLM calls."""

    def __init__(self, price_in: float, price_out: float) -> None:
        self._lock = threading.Lock()
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self._price_in = price_in
        self._price_out = price_out

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        with self._lock:
            self.calls += 1
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens

    @property
    def estimated_cost_usd(self) -> float:
        cost = (
            self.prompt_tokens / 1_000_000 * self._price_in
            + self.completion_tokens / 1_000_000 * self._price_out
        )
        return round(cost, 4)


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        pricing = settings.pricing()
        self.usage = UsageTracker(pricing["input"], pricing["output"])
        self._model = self._build_model(settings)

    @staticmethod
    def _build_model(settings: Settings):
        # Imported lazily so unit tests that never call the LLM don't need the
        # package (or an API key) installed.
        from langchain_anthropic import ChatAnthropic

        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to .env or the environment. "
                "Use `--dry-run` to exercise the pipeline without an API key."
            )
        kwargs = dict(
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_output_tokens,
            api_key=settings.anthropic_api_key,
            timeout=120,
            max_retries=0,  # we manage retries via tenacity for full control
        )
        # Route through a proxy / reseller endpoint when configured.
        if settings.anthropic_base_url:
            kwargs["base_url"] = settings.anthropic_base_url
        return ChatAnthropic(**kwargs)

    def structured(self, schema: type[T], system: str, user: str) -> T:
        """
        Invoke the model and return an instance of ``schema``.

        ``with_structured_output`` binds the Pydantic schema as a tool the model
        must call, so the response is guaranteed to validate against ``schema``.
        """
        runnable = self._model.with_structured_output(schema, include_raw=True)

        @retry(
            reraise=True,
            stop=stop_after_attempt(self.settings.max_retries),
            wait=wait_exponential(multiplier=2, min=2, max=40),
            retry=retry_if_exception_type(Exception),
        )
        def _call():
            return runnable.invoke(
                [("system", system), ("human", user)]
            )

        result = _call()
        self._record_usage(result.get("raw"))
        parsed = result.get("parsed")
        if parsed is None:
            # Structured parsing failed even after retries; surface a clear error.
            raise ValueError("Model did not return a schema-valid object.")
        return parsed

    def _record_usage(self, raw_message) -> None:
        """Pull token counts off the raw AIMessage metadata when available."""
        if raw_message is None:
            return
        meta = getattr(raw_message, "usage_metadata", None) or {}
        prompt = int(meta.get("input_tokens", 0) or 0)
        completion = int(meta.get("output_tokens", 0) or 0)
        if prompt or completion:
            self.usage.record(prompt, completion)
