"""Author-facing ticket endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from app.core.deps import CurrentAuthor, DbSession
from app.models.enums import TicketStatus
from app.realtime.broker import author_channel, ticket_channel
from app.realtime.sse import event_stream
from app.schemas.common import ErrorResponse, ListResponse
from app.schemas.tickets import MessageCreate, TicketCreate, TicketListItem, TicketOut
from app.services.ai_service import classify_ticket_task
from app.services.tickets import TicketService

router = APIRouter(prefix="/tickets", tags=["author"])
ERR = {401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}}


@router.get("", response_model=ListResponse[TicketListItem], responses=ERR)
async def list_my_tickets(
    ctx: CurrentAuthor, db: DbSession, status: Annotated[TicketStatus | None, Query()] = None
) -> ListResponse[TicketListItem]:
    tickets = await TicketService(db).list_for_author(ctx, status)
    return ListResponse(items=[TicketListItem.from_model(t, admin=False) for t in tickets], total=len(tickets))


@router.post(
    "", response_model=TicketOut, status_code=status.HTTP_201_CREATED, responses={**ERR, 422: {"model": ErrorResponse}}
)
async def create_ticket(
    payload: TicketCreate, ctx: CurrentAuthor, db: DbSession, background: BackgroundTasks
) -> TicketOut:
    """Raise a support query. The ticket is committed first; AI classification runs *after* the
    response is sent so an AI outage can never block ticket creation."""
    ticket = await TicketService(db).create_for_author(ctx, payload)
    background.add_task(classify_ticket_task, ticket.id)
    return TicketOut.from_model(ticket)


@router.get("/{ticket_id}", response_model=TicketOut, responses=ERR)
async def get_my_ticket(ticket_id: uuid.UUID, ctx: CurrentAuthor, db: DbSession) -> TicketOut:
    return TicketOut.from_model(await TicketService(db).get_for_author(ctx, ticket_id))


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    responses={**ERR, 409: {"model": ErrorResponse}},
)
async def reply_to_my_ticket(
    ticket_id: uuid.UUID, payload: MessageCreate, ctx: CurrentAuthor, db: DbSession
) -> TicketOut:
    """Follow-up from the author. Replying to a RESOLVED ticket reopens it; CLOSED tickets reject replies (409)."""
    return TicketOut.from_model(await TicketService(db).add_author_message(ctx, ticket_id, payload))


@router.get("/events/stream", responses=ERR, summary="SSE: all of my tickets")
async def my_tickets_events(request: Request, ctx: CurrentAuthor):
    """Server-Sent Events. Browsers can't set headers on EventSource, so pass `?token=<jwt>`.
    Events: `ready`, `ping` (15s heartbeat), `ticket.created`, `ticket.updated`, `message.created`.
    Payloads are signals; refetch the REST resource on receipt."""
    return EventSourceResponse(event_stream(request, [author_channel(ctx.author_id)]))  # type: ignore[arg-type]


@router.get("/{ticket_id}/events", responses=ERR, summary="SSE: one ticket")
async def my_ticket_events(ticket_id: uuid.UUID, request: Request, ctx: CurrentAuthor, db: DbSession):
    await TicketService(db).get_for_author(ctx, ticket_id)  # 404 if not mine
    return EventSourceResponse(event_stream(request, [ticket_channel(ticket_id)]))
