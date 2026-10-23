from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.models.enums import (
    CATEGORY_LABELS,
    AiStatus,
    MessageKind,
    Role,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.models.ticket import Attachment, Ticket, TicketMessage
from app.schemas.books import BookOut
from app.schemas.common import ApiModel

GENERAL_BOOK_ID = None  # "General / Account Level" is represented by book_id = null


# ---------- inputs ----------


class AttachmentIn(ApiModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=120)
    size_bytes: int | None = Field(default=None, ge=0, le=25 * 1024 * 1024)


class TicketCreate(ApiModel):
    book_id: str | None = Field(default=None, description="Omit or null for 'General / Account Level'.")
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    attachments: list[AttachmentIn] = Field(default_factory=list, max_length=5)

    @field_validator("subject", "description")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class MessageCreate(ApiModel):
    body: str = Field(min_length=1, max_length=5000)

    @field_validator("body")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class AdminMessageCreate(MessageCreate):
    kind: Literal[MessageKind.ADMIN_REPLY, MessageKind.INTERNAL_NOTE] = MessageKind.ADMIN_REPLY


class AdminTicketUpdate(ApiModel):
    """PATCH semantics: only fields present in the request body are applied."""

    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    assigned_to_id: uuid.UUID | None = Field(default=None, description="Admin user id, or null to unassign.")


# ---------- outputs ----------


class BookRef(ApiModel):
    id: str
    title: str
    status: str


class AuthorRef(ApiModel):
    id: str
    name: str
    email: str
    city: str | None


class UserRef(ApiModel):
    id: uuid.UUID
    name: str


class AttachmentOut(ApiModel):
    id: uuid.UUID
    filename: str
    mime_type: str | None
    size_bytes: int | None

    @classmethod
    def from_model(cls, a: Attachment) -> AttachmentOut:
        return cls(id=a.id, filename=a.filename, mime_type=a.mime_type, size_bytes=a.size_bytes)


class MessageOut(ApiModel):
    id: uuid.UUID
    kind: MessageKind
    body: str
    sender_name: str | None
    sender_role: Role | None
    created_at: datetime

    @classmethod
    def from_model(cls, m: TicketMessage) -> MessageOut:
        return cls(
            id=m.id,
            kind=m.kind,
            body=m.body,
            created_at=m.created_at,
            sender_name=m.sender.name if m.sender else None,
            sender_role=Role(m.sender.role) if m.sender else None,
        )


class AiMeta(ApiModel):
    status: AiStatus
    category: TicketCategory | None
    priority: TicketPriority | None
    confidence: float | None
    reasoning: str | None
    category_overridden: bool
    priority_overridden: bool
    draft_generated_at: datetime | None


def _category_label(c: TicketCategory) -> str:
    return CATEGORY_LABELS[TicketCategory(c)]


class TicketListItem(ApiModel):
    """Compact row for lists. Shared by author and admin list endpoints."""

    id: uuid.UUID
    number: int
    subject: str
    status: TicketStatus
    category: TicketCategory
    category_label: str
    priority: TicketPriority
    book: BookRef | None
    author: AuthorRef | None = None  # admin view only
    assigned_to: UserRef | None = None  # admin view only
    message_count: int
    created_at: datetime
    last_activity_at: datetime

    @classmethod
    def from_model(cls, t: Ticket, *, admin: bool) -> TicketListItem:
        visible = t.messages if admin else [m for m in t.messages if m.kind != MessageKind.INTERNAL_NOTE]
        return cls(
            id=t.id,
            number=t.number,
            subject=t.subject,
            status=t.status,
            category=t.category,
            category_label=_category_label(t.category),
            priority=t.priority,
            book=BookRef(id=t.book.id, title=t.book.title, status=t.book.status) if t.book else None,
            author=AuthorRef(id=t.author.id, name=t.author.user.name, email=t.author.user.email, city=t.author.city)
            if admin
            else None,
            assigned_to=UserRef(id=t.assigned_to.id, name=t.assigned_to.name) if admin and t.assigned_to else None,
            message_count=len(visible),
            created_at=t.created_at,
            last_activity_at=t.last_activity_at,
        )


class TicketOut(TicketListItem):
    """Author's view of a ticket. Internal notes are stripped; no AI metadata."""

    description: str
    messages: list[MessageOut]
    attachments: list[AttachmentOut]
    resolved_at: datetime | None

    @classmethod
    def from_model(cls, t: Ticket, *, admin: bool = False) -> TicketOut:
        base = TicketListItem.from_model(t, admin=admin).model_dump()
        msgs = t.messages if admin else [m for m in t.messages if m.kind != MessageKind.INTERNAL_NOTE]
        return cls(
            **base,
            description=t.description,
            resolved_at=t.resolved_at,
            messages=[MessageOut.from_model(m) for m in msgs],
            attachments=[AttachmentOut.from_model(a) for a in t.attachments],
        )


class AdminTicketOut(TicketOut):
    """Admin's view: everything, plus AI metadata and the cached draft."""

    ai: AiMeta
    ai_draft: str | None
    # Full royalty facts for the linked book, so the admin can check the draft against real numbers.
    book_detail: BookOut | None

    @classmethod
    def from_model(cls, t: Ticket, *, admin: bool = True) -> AdminTicketOut:
        base = TicketOut.from_model(t, admin=True).model_dump()
        return cls(
            **base,
            ai_draft=t.ai_draft,
            book_detail=BookOut.from_model(t.book) if t.book else None,
            ai=AiMeta(
                status=t.ai_status,
                category=t.ai_category,
                priority=t.ai_priority,
                confidence=t.ai_confidence,
                reasoning=t.ai_reasoning,
                category_overridden=t.category_overridden,
                priority_overridden=t.priority_overridden,
                draft_generated_at=t.ai_draft_generated_at,
            ),
        )


class DraftOut(ApiModel):
    draft: str
    generated_at: datetime
    cached: bool = Field(description="True when served from the ticket's cached draft (zero tokens spent).")
    model: str | None = None


class QueueStats(ApiModel):
    by_status: dict[TicketStatus, int]
    open_by_priority: dict[TicketPriority, int]
    unassigned_open: int
    oldest_open_created_at: datetime | None


class AiUsageRow(ApiModel):
    purpose: str
    calls: int
    ok: int
    failed: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    estimated_cost_usd: Decimal


class AiUsageOut(ApiModel):
    model: str
    since: date | None
    rows: list[AiUsageRow]
    total_cost_usd: Decimal
    pricing_note: str
