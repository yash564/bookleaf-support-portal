"""LLM provider adapters. The rest of the AI package talks to the `Provider` protocol only.

Two operations are all the product needs:
- `parse`    : system + user → an instance of a Pydantic schema (classification)
- `complete` : system + user → text (draft reply)

Anthropic is the default; OpenAI is a drop-in alternative selected with `AI_PROVIDER=openai`.
Both adapters report usage in one shape so the cost ledger and cache metrics are provider-neutral.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.config import Settings, get_settings

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class Provider(Protocol):
    name: str
    model: str

    async def parse(
        self, *, system: str, user: str, schema: type[SchemaT], max_tokens: int
    ) -> tuple[SchemaT, Usage]: ...

    async def complete(self, *, system: str, user: str, max_tokens: int) -> tuple[str, Usage]: ...


# ---------------------------------------------------------------- Anthropic


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, s: Settings):
        import anthropic

        self.model = s.anthropic_model
        # The SDK already retries 429/5xx/connection errors with backoff; keep it small so a background
        # classification never hogs the worker for minutes.
        self._client = anthropic.AsyncAnthropic(
            api_key=s.anthropic_api_key, timeout=s.ai_timeout_seconds, max_retries=s.ai_max_retries
        )

    @staticmethod
    def _usage(u) -> Usage:
        return Usage(
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        )

    async def parse(self, *, system, user, schema, max_tokens):
        resp = await self._client.messages.parse(
            model=self.model,
            max_tokens=max_tokens,
            # Static block is cache-marked; only `user` varies per ticket.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": "low"},  # triage is routine; low effort keeps it fast and cheap
        )
        if resp.parsed_output is None:
            raise ValueError(f"no structured output (stop_reason={resp.stop_reason})")
        return resp.parsed_output, self._usage(resp.usage)

    async def complete(self, *, system, user, max_tokens):
        resp = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium"},
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise ValueError(f"empty draft (stop_reason={resp.stop_reason})")
        return text, self._usage(resp.usage)


# ---------------------------------------------------------------- OpenAI


class OpenAIProvider:
    name = "openai"

    def __init__(self, s: Settings):
        import openai

        self.model = s.openai_model
        self._client = openai.AsyncOpenAI(
            api_key=s.openai_api_key, timeout=s.ai_timeout_seconds, max_retries=s.ai_max_retries
        )

    @staticmethod
    def _usage(u) -> Usage:
        # OpenAI caches automatically for prompts >= 1024 tokens and reports it as cached_tokens
        # (billed at 50% of input). There is no explicit cache write, so cache_write stays 0.
        details = getattr(u, "input_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) or 0
        return Usage(
            input_tokens=max(0, (getattr(u, "input_tokens", 0) or 0) - cached),
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            cache_read_tokens=cached,
        )

    async def parse(self, *, system, user, schema, max_tokens):
        # `instructions` is the system/developer message; the stable prefix is what OpenAI's automatic
        # prompt cache keys on, so it stays byte-identical across tickets.
        resp = await self._client.responses.parse(
            model=self.model,
            instructions=system,
            input=user,
            text_format=schema,
            max_output_tokens=max_tokens,
        )
        if resp.output_parsed is None:
            raise ValueError(f"no structured output (status={resp.status})")
        return resp.output_parsed, self._usage(resp.usage)

    async def complete(self, *, system, user, max_tokens):
        resp = await self._client.responses.create(
            model=self.model, instructions=system, input=user, max_output_tokens=max_tokens
        )
        text = (resp.output_text or "").strip()
        if not text:
            raise ValueError(f"empty draft (status={resp.status})")
        return text, self._usage(resp.usage)


# ---------------------------------------------------------------- selection

_provider: Provider | None = None


def get_provider() -> Provider | None:
    """None when AI is disabled or the selected provider has no key. Cached per process."""
    global _provider
    s = get_settings()
    if not s.ai_available:
        return None
    if _provider is None or _provider.name != s.active_provider:
        _provider = OpenAIProvider(s) if s.active_provider == "openai" else AnthropicProvider(s)
    return _provider


def reset_provider() -> None:
    """For tests / settings reloads."""
    global _provider
    _provider = None
