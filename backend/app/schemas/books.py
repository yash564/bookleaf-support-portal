from datetime import date
from decimal import Decimal

from app.models.book import Book
from app.schemas.common import ApiModel

PAYOUT_THRESHOLD = Decimal("1000")


class BookOut(ApiModel):
    id: str
    title: str
    isbn: str | None
    genre: str | None
    publication_date: date | None
    status: str
    is_published: bool
    mrp: Decimal | None
    royalty_per_copy: Decimal | None
    copies_sold: int
    royalty_earned: Decimal
    royalty_paid: Decimal
    royalty_pending: Decimal
    last_payout_date: date | None
    print_partner: str | None
    available_on: list[str]

    @classmethod
    def from_model(cls, b: Book) -> "BookOut":
        return cls(
            id=b.id,
            title=b.title,
            isbn=b.isbn,
            genre=b.genre,
            publication_date=b.publication_date,
            status=b.status,
            is_published=b.is_published,
            mrp=b.mrp,
            royalty_per_copy=b.royalty_per_copy,
            copies_sold=b.copies_sold,
            royalty_earned=b.royalty_earned,
            royalty_paid=b.royalty_paid,
            royalty_pending=b.royalty_pending,
            last_payout_date=b.last_payout_date,
            print_partner=b.print_partner,
            available_on=list(b.available_on or []),
        )


class BooksSummary(ApiModel):
    """Roll-up shown at the top of My Books. Computed server-side so the UI stays dumb."""

    total_books: int
    published_books: int
    in_production_books: int
    total_copies_sold: int
    total_royalty_earned: Decimal
    total_royalty_paid: Decimal
    total_royalty_pending: Decimal
    payout_threshold: Decimal = PAYOUT_THRESHOLD
    # True when pending > 0 but under the ₹1,000 threshold → it rolls to next quarter (KB policy).
    pending_below_threshold: bool

    @classmethod
    def from_books(cls, books: list[Book]) -> "BooksSummary":
        pending = sum((b.royalty_pending for b in books), Decimal(0))
        return cls(
            total_books=len(books),
            published_books=sum(1 for b in books if b.is_published),
            in_production_books=sum(1 for b in books if not b.is_published),
            total_copies_sold=sum(b.copies_sold for b in books),
            total_royalty_earned=sum((b.royalty_earned for b in books), Decimal(0)),
            total_royalty_paid=sum((b.royalty_paid for b in books), Decimal(0)),
            total_royalty_pending=pending,
            pending_below_threshold=Decimal(0) < pending < PAYOUT_THRESHOLD,
        )


class BooksResponse(ApiModel):
    items: list[BookOut]
    summary: BooksSummary
