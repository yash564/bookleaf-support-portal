"""Category + priority in ONE structured-output call (not two)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.client import AiOutcome, invoke
from app.ai.prompts import CLASSIFY_SYSTEM
from app.config import get_settings
from app.models.enums import TicketCategory, TicketPriority

MAX_DESCRIPTION_CHARS = 2500  # a ticket body longer than this is almost always paste; the head decides the category


class Classification(BaseModel):
    category: TicketCategory
    priority: TicketPriority
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(max_length=300)


def _user_message(subject: str, description: str, book_line: str | None) -> str:
    body = (
        description
        if len(description) <= MAX_DESCRIPTION_CHARS
        else description[:MAX_DESCRIPTION_CHARS] + " …[truncated]"
    )
    scope = book_line or "General / account level (no specific book)"
    return f"TICKET\nAbout: {scope}\nSubject: {subject}\n\n{body}"


async def classify(subject: str, description: str, book_line: str | None) -> tuple[Classification, AiOutcome]:
    s = get_settings()

    async def _call(client):
        resp = await client.messages.parse(
            model=s.anthropic_model,
            max_tokens=400,
            system=[{"type": "text", "text": CLASSIFY_SYSTEM, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
            messages=[{"role": "user", "content": _user_message(subject, description, book_line)}],
            output_format=Classification,
            output_config={"effort": "low"},  # triage is routine; low effort keeps it fast and cheap
        )
        if resp.parsed_output is None:
            raise ValueError(f"no structured output (stop_reason={resp.stop_reason})")
        return resp.parsed_output, resp.usage

    return await invoke(_call)
