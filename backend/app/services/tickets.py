"""Ticket workflows. Routers call these; these call repositories and publish realtime signals."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AuthContext
from app.core.errors import ConflictError, NotFoundError, ValidationFailed
from app.db.base import utcnow
from app.models.enums import MessageKind, Role, TicketStatus
from app.models.ticket import Attachment, Ticket, TicketMessage
from app.realtime.broker import ADMIN_QUEUE_CHANNEL, author_channel, broker, ticket_channel
from app.repositories.books import BookRepository
from app.repositories.tickets import TicketQueueFilters, TicketRepository
from app.repositories.users import UserRepository
from app.schemas.tickets import AdminMessageCreate, AdminTicketUpdate, MessageCreate, TicketCreate

TERMINAL = (TicketStatus.RESOLVED, TicketStatus.CLOSED)


class TicketService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tickets = TicketRepository(db)
        self.books = BookRepository(db)
        self.users = UserRepository(db)

    # ---------- realtime ----------

    async def _notify(self, ticket: Ticket, event_type: str) -> None:
        event = {
            "type": event_type,
            "ticket_id": str(ticket.id),
            "number": ticket.number,
            "status": ticket.status,
            "at": utcnow().isoformat(),
        }
        await broker.publish(ticket_channel(ticket.id), event)
        await broker.publish(author_channel(ticket.author_id), event)
        await broker.publish(ADMIN_QUEUE_CHANNEL, event)

    # ---------- author ----------

    async def create_for_author(self, ctx: AuthContext, payload: TicketCreate) -> Ticket:
        assert ctx.author_id
        if payload.book_id is not None:
            book = await self.books.get_for_author(payload.book_id, ctx.author_id)
            if book is None:
                # 422 not 404: the request is malformed from this author's point of view.
                raise ValidationFailed(
                    "Unknown book for this account.", details=[{"field": "book_id", "message": "not one of your books"}]
                )
        ticket = Ticket(
            author_id=ctx.author_id, book_id=payload.book_id, subject=payload.subject, description=payload.description
        )
        for a in payload.attachments:
            ticket.attachments.append(Attachment(filename=a.filename, mime_type=a.mime_type, size_bytes=a.size_bytes))
        await self.tickets.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        await self._notify(ticket, "ticket.created")
        return ticket

    async def get_for_author(self, ctx: AuthContext, ticket_id: uuid.UUID) -> Ticket:
        assert ctx.author_id
        ticket = await self.tickets.get_for_author(ticket_id, ctx.author_id)
        if ticket is None:
            raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
        return ticket

    async def list_for_author(self, ctx: AuthContext, status: TicketStatus | None) -> list[Ticket]:
        assert ctx.author_id
        return await self.tickets.list_for_author(ctx.author_id, status)

    async def add_author_message(self, ctx: AuthContext, ticket_id: uuid.UUID, payload: MessageCreate) -> Ticket:
        ticket = await self.get_for_author(ctx, ticket_id)
        if ticket.status == TicketStatus.CLOSED:
            raise ConflictError("This ticket is closed. Please open a new ticket.", code="TICKET_CLOSED")
        await self.tickets.add_message(
            TicketMessage(
                ticket_id=ticket.id, sender_id=ctx.user.id, kind=MessageKind.AUTHOR_MESSAGE, body=payload.body
            )
        )
        if ticket.status == TicketStatus.RESOLVED:
            # An author replying to a resolved ticket means it isn't resolved for them.
            ticket.status = TicketStatus.OPEN
            ticket.resolved_at = None
        ticket.last_activity_at = utcnow()
        await self.db.commit()
        await self.db.refresh(ticket)
        await self._notify(ticket, "message.created")
        return ticket

    # ---------- admin ----------

    async def get_admin(self, ticket_id: uuid.UUID) -> Ticket:
        ticket = await self.tickets.get(ticket_id)
        if ticket is None:
            raise NotFoundError("Ticket not found.", code="TICKET_NOT_FOUND")
        return ticket

    async def list_admin(self, filters: TicketQueueFilters) -> tuple[list[Ticket], int]:
        return await self.tickets.list_admin(filters)

    async def admin_update(self, ctx: AuthContext, ticket_id: uuid.UUID, payload: AdminTicketUpdate) -> Ticket:
        ticket = await self.get_admin(ticket_id)
        fields = payload.model_fields_set
        if "category" in fields and payload.category is not None:
            ticket.category = payload.category
            ticket.category_overridden = ticket.ai_category is not None and payload.category != ticket.ai_category
        if "priority" in fields and payload.priority is not None:
            ticket.priority = payload.priority
            ticket.priority_overridden = ticket.ai_priority is not None and payload.priority != ticket.ai_priority
        if "status" in fields and payload.status is not None:
            ticket.status = payload.status
            ticket.resolved_at = utcnow() if payload.status in TERMINAL else None
        if "assigned_to_id" in fields:
            if payload.assigned_to_id is None:
                ticket.assigned_to_id = None
            else:
                assignee = await self.users.get(payload.assigned_to_id)
                if assignee is None or Role(assignee.role) != Role.ADMIN:
                    raise ValidationFailed(
                        "Assignee must be a BookLeaf admin.",
                        details=[{"field": "assigned_to_id", "message": "not an admin"}],
                    )
                ticket.assigned_to_id = assignee.id
                if ticket.status == TicketStatus.OPEN:
                    ticket.status = TicketStatus.IN_PROGRESS  # picking up a ticket starts work on it
        ticket.last_activity_at = utcnow()
        await self.db.commit()
        await self.db.refresh(ticket)
        await self._notify(ticket, "ticket.updated")
        return ticket

    async def admin_add_message(self, ctx: AuthContext, ticket_id: uuid.UUID, payload: AdminMessageCreate) -> Ticket:
        ticket = await self.get_admin(ticket_id)
        await self.tickets.add_message(
            TicketMessage(ticket_id=ticket.id, sender_id=ctx.user.id, kind=payload.kind, body=payload.body)
        )
        if payload.kind == MessageKind.ADMIN_REPLY:
            if ticket.status == TicketStatus.OPEN:
                ticket.status = TicketStatus.IN_PROGRESS
            if ticket.assigned_to_id is None:
                ticket.assigned_to_id = ctx.user.id  # replying implicitly takes ownership
        ticket.last_activity_at = utcnow()
        await self.db.commit()
        await self.db.refresh(ticket)
        # Internal notes don't ping the author channel, but the admin queue still refreshes.
        if payload.kind == MessageKind.INTERNAL_NOTE:
            event = {
                "type": "note.created",
                "ticket_id": str(ticket.id),
                "number": ticket.number,
                "status": ticket.status,
                "at": utcnow().isoformat(),
            }
            await broker.publish(ticket_channel(ticket.id), event)
            await broker.publish(ADMIN_QUEUE_CHANNEL, event)
        else:
            await self._notify(ticket, "message.created")
        return ticket
