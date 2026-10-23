"""Builds the *structured* author/book facts that make a draft specific instead of generic.

Everything here comes from the database, not the model, so numbers in a draft (pending ₹, last
payout, platforms) are real. The output is compact plain text: ~100-200 tokens per ticket.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.models.book import Book
from app.models.ticket import Ticket
from app.schemas.books import PAYOUT_THRESHOLD

QUARTER_ENDS = ((3, 31), (6, 30), (9, 30), (12, 31))
PAYOUT_WINDOW_DAYS = 45


def last_quarter_end(today: date) -> date:
    candidates = [date(today.year, m, d) for m, d in QUARTER_ENDS] + [date(today.year - 1, 12, 31)]
    return max(q for q in candidates if q <= today)


def next_payout_deadline(today: date) -> tuple[date, date]:
    """(quarter_end, payout_by) for the next payout the author can expect under the 45-day policy."""
    q_end = last_quarter_end(today)
    payout_by = q_end + timedelta(days=PAYOUT_WINDOW_DAYS)
    if payout_by < today:  # that window already passed → the next quarter's payout
        nxt = [date(today.year, m, d) for m, d in QUARTER_ENDS] + [date(today.year + 1, 3, 31)]
        q_end = min(q for q in nxt if q > today)
        payout_by = q_end + timedelta(days=PAYOUT_WINDOW_DAYS)
    return q_end, payout_by


def _inr(v: Decimal | int | None) -> str:
    return "₹0" if v is None else f"₹{Decimal(v):,.0f}"


def book_facts(b: Book, today: date) -> str:
    lines = [f"- Title: {b.title} (id {b.id}); genre: {b.genre or 'n/a'}; status: {b.status}"]
    if b.is_published:
        lines.append(
            f"  ISBN {b.isbn or 'n/a'}; published {b.publication_date}; MRP {_inr(b.mrp)}; author royalty/copy {_inr(b.royalty_per_copy)}"
        )
        lines.append(
            f"  Copies sold {b.copies_sold}; royalty earned {_inr(b.royalty_earned)}; paid {_inr(b.royalty_paid)}; pending {_inr(b.royalty_pending)}"
        )
        lines.append(f"  Last payout: {b.last_payout_date or 'never'}; print partner: {b.print_partner or 'In-House'}")
        lines.append(f"  Listed on: {', '.join(b.available_on) if b.available_on else 'no platforms yet'}")
        if Decimal(0) < b.royalty_pending < PAYOUT_THRESHOLD:
            lines.append(
                f"  NOTE: pending {_inr(b.royalty_pending)} is below the ₹1,000 threshold → rolls over to next quarter"
            )
        elif b.royalty_pending >= PAYOUT_THRESHOLD:
            q_end, by = next_payout_deadline(today)
            lines.append(f"  Pending amount is above threshold → due in the payout for quarter ending {q_end}, by {by}")
    else:
        lines.append("  Not yet published: no ISBN/MRP/sales yet (in production)")
    return "\n".join(lines)


def ticket_context(ticket: Ticket, today: date) -> str:
    author = ticket.author
    parts = [
        "AUTHOR",
        f"- {author.user.name} ({author.user.email}); city {author.city or 'n/a'}; BookLeaf author since {author.joined_date}",
        f"- Total books: {len(author.books)}",
    ]
    if ticket.book is not None:
        parts += ["", "BOOK THIS TICKET IS ABOUT", book_facts(ticket.book, today)]
    else:
        parts += ["", "TICKET SCOPE: General / account level (no specific book)"]
        if author.books:
            parts += ["AUTHOR'S BOOKS (brief)"] + [
                f"- {b.title}: {b.status}; pending {_inr(b.royalty_pending)}" for b in author.books
            ]
    return "\n".join(parts)
