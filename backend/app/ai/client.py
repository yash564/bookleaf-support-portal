"""Safety wrapper around whichever LLM provider is active.

Responsibilities (and nothing else):
- a circuit breaker so a dead/rate-limited API doesn't add 20s of latency to every ticket
- mapping SDK exceptions (Anthropic or OpenAI — same class names, different packages) to one
  domain error (`AiUnavailableError`) plus a status for the usage ledger
- timing

Callers get back an `AiOutcome` describing what happened so the service layer can log it.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import anthropic
import openai
from pydantic import ValidationError

from app.ai.providers import Provider, Usage, get_provider
from app.config import get_settings
from app.core.errors import AiUnavailableError
from app.models.enums import AiCallStatus

log = logging.getLogger(__name__)

RATE_LIMITED = (anthropic.RateLimitError, openai.RateLimitError)
TIMEOUT = (anthropic.APITimeoutError, openai.APITimeoutError)
CONNECTION = (anthropic.APIConnectionError, openai.APIConnectionError)
STATUS = (anthropic.APIStatusError, openai.APIStatusError)


class CircuitBreaker:
    """After `threshold` consecutive failures, skip the API for `cooldown` seconds.

    Protects two things: request latency (a classify that would time out is skipped instantly)
    and money (we don't pay for retries against an API that is overloaded or out of credit).
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
class AiOutcome:
    """What the ledger needs to know about one attempt, success or failure."""

    status: AiCallStatus
    model: str
    latency_ms: int
    usage: Usage = field(default_factory=Usage)
    error: str | None = None


async def invoke[T](call: Callable[[Provider], Awaitable[tuple[T, Usage]]]) -> tuple[T, AiOutcome]:
    """Run one model call with timing, error mapping and breaker bookkeeping.

    `call` receives the active provider and returns `(result, usage)`. On any failure this raises
    `AiUnavailableError` carrying an `AiOutcome` in `.outcome` so the caller can still log it.
    """
    s = get_settings()
    provider = get_provider()
    if provider is None:
        raise AiUnavailableError("AI is not configured on this server.", code="AI_DISABLED")
    if breaker.is_open:
        raise AiUnavailableError(
            "AI is temporarily paused after repeated failures; try again in a minute.", code="AI_CIRCUIT_OPEN"
        )

    model = s.active_model
    started = time.perf_counter()

    def _ms() -> int:
        return int((time.perf_counter() - started) * 1000)

    try:
        result, usage = await call(provider)
    except RATE_LIMITED as e:
        outcome = AiOutcome(AiCallStatus.RATE_LIMITED, model, _ms(), error=f"429: {e}"[:500])
    except TIMEOUT as e:
        outcome = AiOutcome(AiCallStatus.TIMEOUT, model, _ms(), error=str(e)[:500])
    except CONNECTION as e:
        outcome = AiOutcome(AiCallStatus.ERROR, model, _ms(), error=f"connection: {e}"[:500])
    except STATUS as e:  # 4xx/5xx we didn't single out (bad key, no credit, overloaded, ...)
        outcome = AiOutcome(AiCallStatus.ERROR, model, _ms(), error=f"{e.status_code}: {e}"[:500])
    except (ValidationError, ValueError) as e:  # structured output missing or didn't match our schema
        outcome = AiOutcome(AiCallStatus.ERROR, model, _ms(), error=f"output: {e}"[:500])
    else:
        breaker.record_success()
        return result, AiOutcome(AiCallStatus.OK, model, _ms(), usage=usage)

    breaker.record_failure()
    log.warning("AI call failed (%s): %s", outcome.status, outcome.error)
    err = AiUnavailableError("The AI assistant is unavailable right now.", code="AI_UNAVAILABLE")
    err.outcome = outcome  # type: ignore[attr-defined]
    raise err
