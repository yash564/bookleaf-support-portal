"""Import every model so SQLAlchemy metadata (and Alembic autogenerate) sees all tables."""

from app.db.base import Base
from app.models.ai_call import AiCall
from app.models.book import Book
from app.models.enums import (
    AiCallStatus,
    AiPurpose,
    AiStatus,
    MessageKind,
    Role,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.models.ticket import Attachment, Ticket, TicketMessage
from app.models.user import AuthorProfile, User

__all__ = [
    "Base",
    "AiCall",
    "AiCallStatus",
    "AiPurpose",
    "AiStatus",
    "Attachment",
    "AuthorProfile",
    "Book",
    "MessageKind",
    "Role",
    "Ticket",
    "TicketCategory",
    "TicketMessage",
    "TicketPriority",
    "TicketStatus",
    "User",
]
