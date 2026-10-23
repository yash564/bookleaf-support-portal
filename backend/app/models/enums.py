"""Domain enums. Stored as strings in the DB so they stay readable in SQL and migrations."""

from enum import StrEnum


class Role(StrEnum):
    AUTHOR = "AUTHOR"
    ADMIN = "ADMIN"


class TicketStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketCategory(StrEnum):
    """The six categories mandated by the brief."""

    ROYALTY_PAYMENTS = "ROYALTY_PAYMENTS"
    ISBN_METADATA = "ISBN_METADATA"
    PRINTING_QUALITY = "PRINTING_QUALITY"
    DISTRIBUTION_AVAILABILITY = "DISTRIBUTION_AVAILABILITY"
    BOOK_STATUS_PRODUCTION = "BOOK_STATUS_PRODUCTION"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"


CATEGORY_LABELS: dict[TicketCategory, str] = {
    TicketCategory.ROYALTY_PAYMENTS: "Royalty & Payments",
    TicketCategory.ISBN_METADATA: "ISBN & Metadata Issues",
    TicketCategory.PRINTING_QUALITY: "Printing & Quality",
    TicketCategory.DISTRIBUTION_AVAILABILITY: "Distribution & Availability",
    TicketCategory.BOOK_STATUS_PRODUCTION: "Book Status & Production Updates",
    TicketCategory.GENERAL_INQUIRY: "General Inquiry",
}


class TicketPriority(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Lower rank = more urgent. Used for queue sorting.
PRIORITY_RANK: dict[TicketPriority, int] = {
    TicketPriority.CRITICAL: 0,
    TicketPriority.HIGH: 1,
    TicketPriority.MEDIUM: 2,
    TicketPriority.LOW: 3,
}


class MessageKind(StrEnum):
    AUTHOR_MESSAGE = "AUTHOR_MESSAGE"
    ADMIN_REPLY = "ADMIN_REPLY"
    INTERNAL_NOTE = "INTERNAL_NOTE"  # never shown to authors


class AiStatus(StrEnum):
    """Lifecycle of the automatic classification for a ticket."""

    PENDING = "PENDING"  # queued / in flight
    DONE = "DONE"  # model classified it
    FALLBACK = "FALLBACK"  # model unavailable, rule-based classifier used
    SKIPPED = "SKIPPED"  # AI disabled by config


class AiPurpose(StrEnum):
    CLASSIFY = "CLASSIFY"
    DRAFT = "DRAFT"


class AiCallStatus(StrEnum):
    OK = "OK"
    ERROR = "ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
