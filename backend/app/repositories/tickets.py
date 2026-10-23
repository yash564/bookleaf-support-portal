"""Ticket persistence. Author-scoped methods take author_id explicitly and always filter by it."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import String, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_call import AiCall
from app.models.enums import PRIORITY_RANK, AiCallStatus, TicketPriority, TicketStatus
from app.models.ticket import Ticket, TicketMessage
from app.models.user import AuthorProfile, User

SortKey = Literal["urgency", "newest", "oldest", "activity"]
UNRESOLVED = (TicketStatus.OPEN, TicketStatus.IN_PROGRESS)


@dataclass
class TicketQueueFilters:
    statuses: list[TicketStatus] = field(default_factory=list)
    category: str | None = None
    priority: str | None = None
    assigned: str | None = None  # "me" | "unassigned" | <admin user uuid>
    me: uuid.UUID | None = None
    q: str | None = None
    created_from: date | None = None
    created_to: date | None = None
    sort: SortKey = "urgency"
    limit: int = 50
    offset: int = 0


class TicketRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----- shared -----

    async def get(self, ticket_id: uuid.UUID) -> Ticket | None:
        return await self.db.get(Ticket, ticket_id)

    async def add(self, ticket: Ticket) -> Ticket:
        self.db.add(ticket)
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket

    async def add_message(self, msg: TicketMessage) -> TicketMessage:
        self.db.add(msg)
        await self.db.flush()
        return msg

    # ----- author scope -----

    async def get_for_author(self, ticket_id: uuid.UUID, author_id: str) -> Ticket | None:
        res = await self.db.execute(select(Ticket).where(Ticket.id == ticket_id, Ticket.author_id == author_id))
        return res.scalar_one_or_none()

    async def list_for_author(self, author_id: str, status: TicketStatus | None = None) -> list[Ticket]:
        stmt = select(Ticket).where(Ticket.author_id == author_id)
        if status:
            stmt = stmt.where(Ticket.status == status)
        res = await self.db.execute(stmt.order_by(Ticket.last_activity_at.desc()))
        return list(res.scalars())

    # ----- admin scope -----

    def _apply_filters(self, stmt, f: TicketQueueFilters):
        if f.statuses:
            stmt = stmt.where(Ticket.status.in_(f.statuses))
        if f.category:
            stmt = stmt.where(Ticket.category == f.category)
        if f.priority:
            stmt = stmt.where(Ticket.priority == f.priority)
        if f.assigned == "me" and f.me:
            stmt = stmt.where(Ticket.assigned_to_id == f.me)
        elif f.assigned == "unassigned":
            stmt = stmt.where(Ticket.assigned_to_id.is_(None))
        elif f.assigned:
            try:
                stmt = stmt.where(Ticket.assigned_to_id == uuid.UUID(f.assigned))
            except ValueError:
                pass
        if f.created_from:
            stmt = stmt.where(Ticket.created_at >= datetime.combine(f.created_from, datetime.min.time(), UTC))
        if f.created_to:
            end = datetime.combine(f.created_to + timedelta(days=1), datetime.min.time(), UTC)
            stmt = stmt.where(Ticket.created_at < end)
        if f.q:
            like = f"%{f.q.strip()}%"
            stmt = (
                stmt.join(Ticket.author)
                .join(AuthorProfile.user)
                .where(
                    or_(
                        Ticket.subject.ilike(like),
                        Ticket.description.ilike(like),
                        User.name.ilike(like),
                        func.cast(Ticket.number, String).ilike(like),
                    )
                )
            )
        return stmt

    async def list_admin(self, f: TicketQueueFilters) -> tuple[list[Ticket], int]:
        base = self._apply_filters(select(Ticket), f)
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

        priority_rank = case({p.value: r for p, r in PRIORITY_RANK.items()}, value=Ticket.priority, else_=99)
        unresolved_first = case((Ticket.status.in_(UNRESOLVED), 0), else_=1)
        order = {
            # "Most urgent and oldest unresolved should be easy to spot": unresolved → priority → age.
            "urgency": (unresolved_first, priority_rank, Ticket.created_at.asc()),
            "newest": (Ticket.created_at.desc(),),
            "oldest": (Ticket.created_at.asc(),),
            "activity": (Ticket.last_activity_at.desc(),),
        }[f.sort]
        res = await self.db.execute(base.order_by(*order).limit(f.limit).offset(f.offset))
        return list(res.scalars().unique()), total

    async def stats(self) -> dict:
        by_status = dict((await self.db.execute(select(Ticket.status, func.count()).group_by(Ticket.status))).all())
        open_by_priority = dict(
            (
                await self.db.execute(
                    select(Ticket.priority, func.count()).where(Ticket.status.in_(UNRESOLVED)).group_by(Ticket.priority)
                )
            ).all()
        )
        unassigned = (
            await self.db.execute(
                select(func.count()).where(Ticket.status.in_(UNRESOLVED), Ticket.assigned_to_id.is_(None))
            )
        ).scalar_one()
        oldest = (
            await self.db.execute(select(func.min(Ticket.created_at)).where(Ticket.status.in_(UNRESOLVED)))
        ).scalar_one()
        return {
            "by_status": {s: by_status.get(s.value, 0) for s in TicketStatus},
            "open_by_priority": {p: open_by_priority.get(p.value, 0) for p in TicketPriority},
            "unassigned_open": unassigned,
            "oldest_open_created_at": oldest,
        }

    async def ai_usage(self, since: date | None) -> list[dict]:
        stmt = select(
            AiCall.purpose,
            func.count().label("calls"),
            func.sum(case((AiCall.status == AiCallStatus.OK, 1), else_=0)).label("ok"),
            func.coalesce(func.sum(AiCall.input_tokens), 0),
            func.coalesce(func.sum(AiCall.output_tokens), 0),
            func.coalesce(func.sum(AiCall.cache_read_tokens), 0),
            func.coalesce(func.sum(AiCall.cache_write_tokens), 0),
        ).group_by(AiCall.purpose)
        if since:
            stmt = stmt.where(AiCall.created_at >= datetime.combine(since, datetime.min.time(), UTC))
        rows = (await self.db.execute(stmt)).all()
        return [
            {
                "purpose": r[0],
                "calls": r[1],
                "ok": int(r[2] or 0),
                "failed": r[1] - int(r[2] or 0),
                "input_tokens": int(r[3]),
                "output_tokens": int(r[4]),
                "cache_read_tokens": int(r[5]),
                "cache_write_tokens": int(r[6]),
            }
            for r in rows
        ]
