import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Sequence, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow
from app.models.enums import AiStatus, MessageKind, TicketCategory, TicketPriority, TicketStatus

ticket_number_seq = Sequence("ticket_number_seq", start=1001)


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Human-friendly id shown in the UI (#1001, #1002 ...). Stable, sortable, no UUID in chat.
    number: Mapped[int] = mapped_column(
        Integer, ticket_number_seq, server_default=ticket_number_seq.next_value(), unique=True, nullable=False
    )
    author_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("author_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    book_id: Mapped[str | None] = mapped_column(String(16), ForeignKey("books.id", ondelete="SET NULL"))
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[TicketStatus] = mapped_column(String(16), default=TicketStatus.OPEN, index=True, nullable=False)
    # Effective values the ops team works with. Seeded from the AI, editable by admins.
    category: Mapped[TicketCategory] = mapped_column(
        String(32), default=TicketCategory.GENERAL_INQUIRY, index=True, nullable=False
    )
    priority: Mapped[TicketPriority] = mapped_column(
        String(16), default=TicketPriority.MEDIUM, index=True, nullable=False
    )
    # What the AI originally said, kept for audit + to show "AI suggested X, admin changed to Y".
    ai_category: Mapped[TicketCategory | None] = mapped_column(String(32))
    ai_priority: Mapped[TicketPriority | None] = mapped_column(String(16))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    ai_status: Mapped[AiStatus] = mapped_column(String(16), default=AiStatus.PENDING, nullable=False)
    category_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority_overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Cached draft so re-opening a ticket costs zero tokens.
    ai_draft: Mapped[str | None] = mapped_column(Text)
    ai_draft_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bumped on every message/status change; drives "last activity" and SSE change detection.
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    author: Mapped["AuthorProfile"] = relationship(lazy="selectin")
    book: Mapped["Book | None"] = relationship(lazy="selectin")
    assigned_to: Mapped["User | None"] = relationship(lazy="selectin")
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", order_by="TicketMessage.created_at", cascade="all, delete-orphan", lazy="selectin"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", lazy="selectin"
    )


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[MessageKind] = mapped_column(String(16), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="messages")
    sender: Mapped["User | None"] = relationship(lazy="selectin")


class Attachment(Base):
    """Metadata only. The brief asks for attachment UI; binary upload is a documented bonus."""

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="attachments")


from app.models.book import Book  # noqa: E402
from app.models.user import AuthorProfile, User  # noqa: E402
