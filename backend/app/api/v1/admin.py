"""Admin-facing endpoints: queue, ticket management, AI actions, stats."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from app.core.deps import CurrentAdmin, DbSession
from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.realtime.broker import ADMIN_QUEUE_CHANNEL, ticket_channel
from app.realtime.sse import event_stream
from app.repositories.tickets import SortKey, TicketQueueFilters
from app.repositories.users import UserRepository
from app.schemas.auth import UserOut
from app.schemas.common import ErrorResponse, ListResponse
from app.schemas.tickets import (
    AdminMessageCreate,
    AdminTicketOut,
    AdminTicketUpdate,
    AiUsageOut,
    DraftOut,
    QueueStats,
    TicketListItem,
)
from app.services import ai_service
from app.services.tickets import TicketService

router = APIRouter(prefix="/admin", tags=["admin"])
ERR = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}


@router.get("/tickets", response_model=ListResponse[TicketListItem], responses=ERR)
async def list_tickets(
    ctx: CurrentAdmin,
    db: DbSession,
    status: Annotated[list[TicketStatus] | None, Query(description="Repeatable. Default: all statuses.")] = None,
    category: TicketCategory | None = None,
    priority: TicketPriority | None = None,
    assigned: Annotated[str | None, Query(description='"me", "unassigned", or an admin user id')] = None,
    q: Annotated[
        str | None, Query(max_length=100, description="Search subject, description, author name, ticket number")
    ] = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort: SortKey = "urgency",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ListResponse[TicketListItem]:
    """The queue. Default sort `urgency` = unresolved first, then priority, then oldest first."""
    filters = TicketQueueFilters(
        statuses=status or [],
        category=category,
        priority=priority,
        assigned=assigned,
        me=ctx.user.id,
        q=q,
        created_from=created_from,
        created_to=created_to,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    tickets, total = await TicketService(db).list_admin(filters)
    return ListResponse(items=[TicketListItem.from_model(t, admin=True) for t in tickets], total=total)


@router.get("/tickets/stats", response_model=QueueStats, responses=ERR)
async def queue_stats(ctx: CurrentAdmin, db: DbSession) -> QueueStats:
    return QueueStats(**await TicketService(db).tickets.stats())


@router.get("/tickets/events", responses=ERR, summary="SSE: whole queue")
async def queue_events(request: Request, ctx: CurrentAdmin):
    """Server-Sent Events for the queue (pass `?token=<jwt>`). Emits a signal on any ticket change."""
    return EventSourceResponse(event_stream(request, [ADMIN_QUEUE_CHANNEL]))


@router.get("/tickets/{ticket_id}", response_model=AdminTicketOut, responses=ERR)
async def get_ticket(ticket_id: uuid.UUID, ctx: CurrentAdmin, db: DbSession) -> AdminTicketOut:
    """Full ticket incl. internal notes, AI classification metadata and the cached draft (if any)."""
    return AdminTicketOut.from_model(await TicketService(db).get_admin(ticket_id))


@router.patch("/tickets/{ticket_id}", response_model=AdminTicketOut, responses={**ERR, 422: {"model": ErrorResponse}})
async def update_ticket(
    ticket_id: uuid.UUID, payload: AdminTicketUpdate, ctx: CurrentAdmin, db: DbSession
) -> AdminTicketOut:
    """Partial update: status, category/priority override, assignment (`assigned_to_id: null` unassigns)."""
    return AdminTicketOut.from_model(await TicketService(db).admin_update(ctx, ticket_id, payload))


@router.post(
    "/tickets/{ticket_id}/messages",
    response_model=AdminTicketOut,
    status_code=status.HTTP_201_CREATED,
    responses={**ERR, 422: {"model": ErrorResponse}},
)
async def add_message(
    ticket_id: uuid.UUID, payload: AdminMessageCreate, ctx: CurrentAdmin, db: DbSession
) -> AdminTicketOut:
    """`ADMIN_REPLY` is visible to the author (and moves OPEN → IN_PROGRESS); `INTERNAL_NOTE` never is."""
    return AdminTicketOut.from_model(await TicketService(db).admin_add_message(ctx, ticket_id, payload))


@router.post("/tickets/{ticket_id}/ai-draft", response_model=DraftOut, responses={**ERR, 503: {"model": ErrorResponse}})
async def ai_draft(
    ticket_id: uuid.UUID,
    ctx: CurrentAdmin,
    db: DbSession,
    regenerate: Annotated[bool, Query(description="Ignore the cached draft and spend tokens on a fresh one.")] = False,
) -> DraftOut:
    """AI-drafted reply grounded in the BookLeaf knowledge base + this author's real book data.
    Cached on the ticket; 503 `AI_UNAVAILABLE` when the model is down/rate-limited/unconfigured —
    the admin writes the reply manually in that case."""
    ticket = await TicketService(db).get_admin(ticket_id)
    return await ai_service.get_or_create_draft(db, ticket, agent_name=ctx.user.name, regenerate=regenerate)


@router.post(
    "/tickets/{ticket_id}/ai-classify", response_model=AdminTicketOut, responses={**ERR, 503: {"model": ErrorResponse}}
)
async def ai_classify(ticket_id: uuid.UUID, ctx: CurrentAdmin, db: DbSession) -> AdminTicketOut:
    """Re-run classification + priority scoring (e.g. after the author added details). Admin overrides are preserved."""
    ticket = await TicketService(db).get_admin(ticket_id)
    await ai_service.classify_ticket(db, ticket, raise_on_unavailable=True)
    return AdminTicketOut.from_model(ticket)


@router.get("/tickets/{ticket_id}/events", responses=ERR, summary="SSE: one ticket (admin)")
async def ticket_events(ticket_id: uuid.UUID, request: Request, ctx: CurrentAdmin, db: DbSession):
    await TicketService(db).get_admin(ticket_id)
    return EventSourceResponse(event_stream(request, [ticket_channel(ticket_id)]))


@router.get("/users", response_model=list[UserOut], responses=ERR)
async def list_admins(ctx: CurrentAdmin, db: DbSession) -> list[UserOut]:
    """Admin accounts, for the assignment dropdown."""
    return [UserOut(id=u.id, email=u.email, name=u.name, role=u.role) for u in await UserRepository(db).list_admins()]


@router.get("/ai/usage", response_model=AiUsageOut, responses=ERR)
async def ai_usage(ctx: CurrentAdmin, db: DbSession, since: date | None = None) -> AiUsageOut:
    """Token + cost ledger from the `ai_calls` table. Evidence for cost-awareness, not just a claim."""
    return await ai_service.usage_report(db, since)
