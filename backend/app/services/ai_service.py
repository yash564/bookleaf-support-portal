"""Glue between the AI package and the database: persist results, log every call, degrade gracefully.

Nothing in here can break ticket creation: `classify_ticket_task` runs after the HTTP response and
swallows every error into the ticket's `ai_status` + the usage ledger.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classify import classify
from app.ai.client import AiOutcome
from app.ai.draft import draft_reply
from app.ai.fallback import classify_by_rules
from app.ai.pricing import PRICES, estimate_cost_usd
from app.config import get_settings
from app.core.errors import AiUnavailableError
from app.db.base import utcnow
from app.db.session import SessionLocal
from app.models.ai_call import AiCall
from app.models.enums import AiPurpose, AiStatus
from app.models.ticket import Ticket
from app.realtime.broker import ADMIN_QUEUE_CHANNEL, broker, ticket_channel
from app.repositories.tickets import TicketRepository
from app.schemas.tickets import AiUsageOut, AiUsageRow, DraftOut

log = logging.getLogger(__name__)


def _record(db: AsyncSession, ticket_id: uuid.UUID | None, purpose: AiPurpose, outcome: AiOutcome) -> None:
    db.add(
        AiCall(
            ticket_id=ticket_id,
            purpose=purpose,
            model=outcome.model,
            status=outcome.status,
            input_tokens=outcome.usage.input_tokens,
            output_tokens=outcome.usage.output_tokens,
            cache_read_tokens=outcome.usage.cache_read_tokens,
            cache_write_tokens=outcome.usage.cache_write_tokens,
            latency_ms=outcome.latency_ms,
            error=outcome.error,
        )
    )


async def _notify_classified(ticket: Ticket) -> None:
    event = {
        "type": "ticket.classified",
        "ticket_id": str(ticket.id),
        "number": ticket.number,
        "status": ticket.status,
        "at": utcnow().isoformat(),
    }
    await broker.publish(ticket_channel(ticket.id), event)
    await broker.publish(ADMIN_QUEUE_CHANNEL, event)


# ---------- classification ----------


async def classify_ticket(db: AsyncSession, ticket: Ticket, *, raise_on_unavailable: bool = False) -> Ticket:
    """Classify + prioritise. Preserves admin overrides; falls back to rules when the model is unavailable."""
    settings = get_settings()
    book_line = f"{ticket.book.title} ({ticket.book.status})" if ticket.book else None
    first_time = ticket.ai_status in (AiStatus.PENDING, AiStatus.SKIPPED)

    if not settings.ai_available:
        if first_time:
            _apply_rules(ticket, reason_suffix=" AI disabled by configuration.")
            ticket.ai_status = AiStatus.SKIPPED
            await db.commit()
            await _notify_classified(ticket)
        if raise_on_unavailable:
            raise AiUnavailableError("AI is not configured on this server.", code="AI_DISABLED")
        return ticket

    try:
        result, outcome = await classify(ticket.subject, ticket.description, book_line)
    except AiUnavailableError as e:
        outcome = getattr(e, "outcome", None)
        if outcome is not None:
            _record(db, ticket.id, AiPurpose.CLASSIFY, outcome)
        if first_time:
            # Provisional, clearly-labelled values so the queue still sorts sensibly.
            _apply_rules(ticket)
            ticket.ai_status = AiStatus.FALLBACK
        await db.commit()
        if first_time:
            await _notify_classified(ticket)
        if raise_on_unavailable:
            raise
        return ticket

    _record(db, ticket.id, AiPurpose.CLASSIFY, outcome)
    ticket.ai_category, ticket.ai_priority = result.category, result.priority
    ticket.ai_confidence, ticket.ai_reasoning = round(result.confidence, 3), result.reasoning
    ticket.ai_status = AiStatus.DONE
    # The AI only *suggests*; an admin's explicit override always wins.
    if not ticket.category_overridden:
        ticket.category = result.category
    if not ticket.priority_overridden:
        ticket.priority = result.priority
    await db.commit()
    await db.refresh(ticket)
    await _notify_classified(ticket)
    return ticket


def _apply_rules(ticket: Ticket, *, reason_suffix: str = "") -> None:
    category, priority, reasoning = classify_by_rules(ticket.subject, ticket.description)
    ticket.ai_category, ticket.ai_priority = category, priority
    ticket.ai_confidence, ticket.ai_reasoning = None, reasoning + reason_suffix
    if not ticket.category_overridden:
        ticket.category = category
    if not ticket.priority_overridden:
        ticket.priority = priority


async def classify_ticket_task(ticket_id: uuid.UUID) -> None:
    """BackgroundTask entry point: own session, never raises."""
    try:
        async with SessionLocal() as db:
            ticket = await TicketRepository(db).get(ticket_id)
            if ticket is None:
                return
            await classify_ticket(db, ticket)
    except Exception:  # noqa: BLE001 — a background task must not take the worker down
        log.exception("Background classification failed for ticket %s", ticket_id)


# ---------- drafts ----------


async def get_or_create_draft(
    db: AsyncSession, ticket: Ticket, *, agent_name: str, regenerate: bool = False
) -> DraftOut:
    """Serve the cached draft unless asked to regenerate. One ticket = at most one draft call unless an admin opts in."""
    settings = get_settings()
    if ticket.ai_draft and ticket.ai_draft_generated_at and not regenerate:
        return DraftOut(draft=ticket.ai_draft, generated_at=ticket.ai_draft_generated_at, cached=True, model=None)

    try:
        text, outcome = await draft_reply(ticket, agent_name=agent_name, today=date.today())
    except AiUnavailableError as e:
        outcome = getattr(e, "outcome", None)
        if outcome is not None:
            _record(db, ticket.id, AiPurpose.DRAFT, outcome)
            await db.commit()
        raise

    _record(db, ticket.id, AiPurpose.DRAFT, outcome)
    ticket.ai_draft = text
    ticket.ai_draft_generated_at = utcnow()
    await db.commit()
    await db.refresh(ticket)
    return DraftOut(draft=text, generated_at=ticket.ai_draft_generated_at, cached=False, model=settings.anthropic_model)


# ---------- usage ----------


async def usage_report(db: AsyncSession, since: date | None) -> AiUsageOut:
    model = get_settings().anthropic_model
    rows = []
    total = 0
    for r in await TicketRepository(db).ai_usage(since):
        cost = estimate_cost_usd(
            model,
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            cache_read=r["cache_read_tokens"],
            cache_write=r["cache_write_tokens"],
        )
        total += cost
        rows.append(AiUsageRow(**r, estimated_cost_usd=cost))
    inp, out = PRICES.get(model, PRICES["claude-haiku-5-5"])
    return AiUsageOut(
        model=model,
        since=since,
        rows=rows,
        total_cost_usd=total,
        pricing_note=f"Estimated at ${inp}/M input, ${out}/M output tokens; cache reads billed at 10%, cache writes at 125% of input.",
    )
