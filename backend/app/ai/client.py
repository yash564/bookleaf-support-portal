"""Thin, safe wrapper around the Anthropic SDK.

Responsibilities (and nothing else):
- one lazily-created AsyncAnthropic client, configured from settings (key never leaves this process)
- a circuit breaker so a dead/rate-limited API doesn't add 20s of latency to every ticket
- mapping SDK exceptions to one domain error (`AiUnavailableError`) + a status for the usage ledger

Callers get back an `AiOutcome` describing what happened so the service layer can log it.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import anthropic
from pydantic import ValidationError

from app.config import get_settings
from app.core.errors import AiUnavailableError
from app.models.enums import AiCallStatus

log = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic | None:
    """None when AI is disabled or no key is configured; callers must handle that."""
    global _client
    s = get_settings()
    if not s.ai_available:
        return None
    if _client is None:
        # The SDK already retries 429/5xx/connection errors with backoff; we keep it small so a
        # background classification never hogs the worker for minutes.
        _client = anthropic.AsyncAnthropic(
            api_key=s.anthropic_api_key, timeout=s.ai_timeout_seconds, max_retries=s.ai_max_retries
        )
    return _client


class CircuitBreaker:
    """After `threshold` consecutive failures, skip the API for `cooldown` seconds.

    Protects two things: request latency (a classify that would time out is skipped instantly)
    and money (we don't pay for retries against an API that is overloaded).
    """

    def __init__(self, threshold: int = 3, cooldown_seconds: float = 120.0):
        self.threshold = threshold
        self.cooldown = cooldown_seconds
        self.failures = 0
        self.open_until = 0.0

    @property
    def is_open(self) -> bool:
        return time.monotonic() < self.open_until

    def record_success(self) -> None:
        self.failures = 0
        self.open_until = 0.0

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open_until = time.monotonic() + self.cooldown
            log.warning("AI circuit breaker OPEN for %.0fs after %d failures", self.cooldown, self.failures)

    def reset(self) -> None:
        self.record_success()


breaker = CircuitBreaker()


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @classmethod
    def from_response(cls, usage) -> Usage:
        return cls(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )


@dataclass
class AiOutcome:
    """What the ledger needs to know about one attempt, success or failure."""

    status: AiCallStatus
    model: str
    latency_ms: int
    usage: Usage = field(default_factory=Usage)
    error: str | None = None


async def invoke[T](call: Callable[[anthropic.AsyncAnthropic], Awaitable[tuple[T, object]]]) -> tuple[T, AiOutcome]:
    """Run one model call with timing, error mapping and breaker bookkeeping.

    `call` receives the client and must return `(result, usage)`. On any failure this raises
    `AiUnavailableError` carrying an `AiOutcome` in `.outcome` so the caller can still log it.
    """
    s = get_settings()
    client = get_client()
    if client is None:
        raise AiUnavailableError("AI is not configured on this server.", code="AI_DISABLED")
    if breaker.is_open:
        raise AiUnavailableError(
            "AI is temporarily paused after repeated failures; try again in a minute.", code="AI_CIRCUIT_OPEN"
        )

    started = time.perf_counter()

    def _ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        result, usage = await call(client)
    except anthropic.RateLimitError as e:
        outcome = AiOutcome(AiCallStatus.RATE_LIMITED, s.anthropic_model, _ms(), error=f"429: {e.message}"[:500])
    except anthropic.APITimeoutError as e:
        outcome = AiOutcome(AiCallStatus.TIMEOUT, s.anthropic_model, _ms(), error=str(e)[:500])
    except anthropic.APIConnectionError as e:
        outcome = AiOutcome(AiCallStatus.ERROR, s.anthropic_model, _ms(), error=f"connection: {e}"[:500])
    except anthropic.APIStatusError as e:  # 4xx/5xx we didn't single out (bad key, overloaded, ...)
        outcome = AiOutcome(AiCallStatus.ERROR, s.anthropic_model, _ms(), error=f"{e.status_code}: {e.message}"[:500])
    except ValidationError as e:  # structured output didn't match our schema
        outcome = AiOutcome(AiCallStatus.ERROR, s.anthropic_model, _ms(), error=f"schema: {e}"[:500])
    else:
        breaker.record_success()
        return result, AiOutcome(AiCallStatus.OK, s.anthropic_model, _ms(), usage=Usage.from_response(usage))

    breaker.record_failure()
    log.warning("AI call failed (%s): %s", outcome.status, outcome.error)
    err = AiUnavailableError("The AI assistant is unavailable right now.", code="AI_UNAVAILABLE")
    err.outcome = outcome  # type: ignore[attr-defined]
    raise err
