"""AI-drafted reply grounded in the KB and this author's real data."""

from __future__ import annotations

from datetime import date

from app.ai.client import AiOutcome, invoke
from app.ai.context import ticket_context
from app.ai.prompts import DRAFT_SYSTEM
from app.config import get_settings
from app.models.enums import CATEGORY_LABELS, MessageKind, TicketCategory
from app.models.ticket import Ticket

MAX_HISTORY_MESSAGES = 3  # the latest exchanges carry the state; older ones are noise + tokens
MAX_MESSAGE_CHARS = 600
MAX_DESCRIPTION_CHARS = 3000


def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + " …[truncated]"


def _history(ticket: Ticket) -> str:
    visible = [m for m in ticket.messages if m.kind != MessageKind.INTERNAL_NOTE][-MAX_HISTORY_MESSAGES:]
    if not visible:
        return "(no replies yet — this is the first response)"
    who = {MessageKind.AUTHOR_MESSAGE: "Author", MessageKind.ADMIN_REPLY: "BookLeaf"}
    return "\n".join(
        f"{who.get(m.kind, m.kind)} ({m.created_at:%d %b %Y}): {_trim(m.body, MAX_MESSAGE_CHARS)}" for m in visible
    )


def build_user_message(ticket: Ticket, *, agent_name: str, today: date) -> str:
    return "\n\n".join(
        [
            f"Today's date: {today:%d %B %Y}. You are replying as {agent_name}, BookLeaf Author Support.",
            ticket_context(ticket, today),
            f"TICKET #{ticket.number} — category {CATEGORY_LABELS[TicketCategory(ticket.category)]}, priority {ticket.priority}\n"
            f"Subject: {ticket.subject}\n\n{_trim(ticket.description, MAX_DESCRIPTION_CHARS)}",
            f"CONVERSATION SO FAR (latest {MAX_HISTORY_MESSAGES})\n{_history(ticket)}",
            "Write the reply now.",
        ]
    )


async def draft_reply(ticket: Ticket, *, agent_name: str, today: date | None = None) -> tuple[str, AiOutcome]:
    s = get_settings()
    user = build_user_message(ticket, agent_name=agent_name, today=today or date.today())

    async def _call(client):
        resp = await client.messages.create(
            model=s.anthropic_model,
            max_tokens=1024,
            # Static block (persona + KB + examples) is cache-marked; only `user` varies per ticket.
            system=[{"type": "text", "text": DRAFT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium"},
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise ValueError(f"empty draft (stop_reason={resp.stop_reason})")
        return text, resp.usage

    return await invoke(_call)
