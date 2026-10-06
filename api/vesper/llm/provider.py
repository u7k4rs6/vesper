"""The one place a language model is called. Imported only by pipeline/diagnose.py and pipeline/propose.py.

`complete_json` returns raw JSON text; the caller validates it against a closed Pydantic schema.
Retries, the timeout, and the hourly budget are enforced here, not by any prompt.
"""

import json
import threading
import time
from collections import deque
from typing import Any, Literal

import anthropic
import structlog

from vesper.config import get_settings

log = structlog.get_logger()

Stage = Literal["diagnose", "propose"]

TIMEOUT_S = 10.0
RETRY_DELAY_S = 2.0
# Models that accept the server-side `fallbacks: "default"` refusal routing.
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class ProviderError(Exception):
    """The model could not be reached or refused; the case escalates."""


class BudgetExceeded(ProviderError):
    pass


class _Budget:
    def __init__(self) -> None:
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def take(self) -> None:
        limit = get_settings().llm_max_calls_per_hour
        now = time.monotonic()
        with self._lock:
            while self._calls and now - self._calls[0] > 3600:
                self._calls.popleft()
            if len(self._calls) >= limit:
                raise BudgetExceeded("Model budget for this hour is used up; a human can review.")
            self._calls.append(now)


budget = _Budget()


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Keep only what structured outputs needs; the full constraints are re-checked by Pydantic."""
    drop = {"title", "maxLength", "minLength", "pattern", "default", "description"}
    if isinstance(schema, dict):
        return {k: _strict_schema(v) for k, v in schema.items() if k not in drop}
    if isinstance(schema, list):
        return [_strict_schema(v) for v in schema]
    return schema


class AnthropicProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.llm_model
        self._client = anthropic.Anthropic(api_key=settings.llm_api_key or None, timeout=TIMEOUT_S, max_retries=0)

    def complete(self, stage: Stage, system: str, user: str, schema: dict[str, Any]) -> str:
        extra: dict[str, Any] = {}
        if self._model in FALLBACK_MODELS:
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        response = self._client.beta.messages.create(
            model=self._model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": _strict_schema(schema)}},
            **extra,
        )
        if response.stop_reason == "refusal":
            raise ProviderError("The model declined to answer.")
        if response.stop_reason == "max_tokens":
            raise ProviderError("The model's answer was cut off.")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise ProviderError("The model returned no text.")
        return text


class FixtureProvider:
    """Deterministic answers for tests and offline runs. Tests may queue exact replies."""

    def __init__(self) -> None:
        self.queued: dict[str, deque[str]] = {"diagnose": deque(), "propose": deque()}
        self.calls: list[str] = []

    def complete(self, stage: Stage, system: str, user: str, schema: dict[str, Any]) -> str:
        self.calls.append(stage)
        if self.queued[stage]:
            return self.queued[stage].popleft()
        packet = json.loads(user.split("<data>", 1)[1].split("</data>", 1)[0])
        hint = packet["failure_category_hint"]
        if stage == "diagnose":
            return json.dumps({
                "category": hint,
                "cause": f"PayPal reported {packet['failure_code']}.",
                "customer_context": "No earlier messages about this payment.",
                "confidence": "medium",
            })
        action = {"soft": "SEND_INVOICE", "unknown": "ESCALATE", "pending": "WAIT", "hard": "NONE"}[hint]
        language = packet["customer"]["locale"].split("-")[0]
        from vesper.pipeline.messaging import fallback  # fixture only: reuse a known-good template

        template, _ = fallback(packet["customer"]["locale"])
        return json.dumps({
            "action": action,
            "rationale": "Fixture proposal.",
            "message_template": template if action == "SEND_INVOICE" else None,
            "language": language,
        })


_provider: AnthropicProvider | FixtureProvider | None = None


def get_provider() -> AnthropicProvider | FixtureProvider:
    global _provider
    if _provider is None:
        _provider = FixtureProvider() if get_settings().llm_provider == "fixture" else AnthropicProvider()
    return _provider


def complete_json(stage: Stage, *, system: str, user: str, schema: dict[str, Any]) -> str:
    """One model call with one retry on transport errors. Raises ProviderError when it cannot answer."""
    budget.take()
    provider = get_provider()
    for attempt in (1, 2):
        started = time.monotonic()
        try:
            text = provider.complete(stage, system, user, schema)
            log.info("llm_call", stage=stage, latency_ms=int((time.monotonic() - started) * 1000))
            return text
        except ProviderError:
            raise
        except anthropic.APIStatusError as e:
            if e.status_code < 500 and e.status_code != 429:
                raise ProviderError(f"The model provider rejected the request ({e.status_code}).") from e
            err: Exception = e
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            err = e
        log.warning("llm_retry", stage=stage, attempt=attempt, error=type(err).__name__)
        if attempt == 1:
            time.sleep(RETRY_DELAY_S)
    raise ProviderError("The model could not be reached.")
