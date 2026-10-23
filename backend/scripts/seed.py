"""Seed the database from the BookLeaf sample dataset.

Usage:  uv run python -m scripts.seed
Idempotent by design: wipes app tables and re-inserts, so the demo always starts from the exact
records the evaluators will test with. Adds two admin logins and a handful of realistic tickets so
the admin queue is meaningful on first login.

Test credentials (also in README):
  authors  -> <email from dataset> / password123
  admins   -> admin@bookleaf.com / admin123, ops@bookleaf.com / admin123
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, text

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    AiCall,
    AiStatus,
    Attachment,
    AuthorProfile,
    Book,
    MessageKind,
    Role,
    Ticket,
    TicketCategory,
    TicketMessage,
    TicketPriority,
    TicketStatus,
    User,
)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "bookleaf_sample_data.json"
AUTHOR_PASSWORD = "password123"
ADMIN_PASSWORD = "admin123"

ADMINS = [
    {"email": "admin@bookleaf.com", "name": "Aarav Mehta"},
    {"email": "ops@bookleaf.com", "name": "Nisha Verma"},
]


def _d(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


def _money(v: int | float | None) -> Decimal | None:
    return Decimal(str(v)) if v is not None else None


def _ago(**kw) -> datetime:
    return datetime.now(UTC) - timedelta(**kw)


# Realistic queue so the admin portal demos well. (author_id, book_id, ...) reference dataset ids.
SAMPLE_TICKETS: list[dict] = [
    {
        "author_id": "AUTH002",
        "book_id": "BK003",
        "subject": "No royalty received since September",
        "description": (
            "Hi team, my last payout for Code & Karma was on 1 September. My dashboard shows ₹5,280 pending "
            "but nothing has arrived in my bank account. It has been well over a quarter now. Can you tell me "
            "what is going on and when I will be paid?"
        ),
        "category": TicketCategory.ROYALTY_PAYMENTS,
        "priority": TicketPriority.HIGH,
        "confidence": 0.94,
        "reasoning": "Overdue royalty payout with a specific pending amount; money owed to the author.",
        "status": TicketStatus.OPEN,
        "created": _ago(days=6, hours=3),
    },
    {
        "author_id": "AUTH003",
        "book_id": "BK005",
        "subject": "Amazon lists a different ISBN than my printed copy",
        "description": (
            "The ISBN printed on the back cover of Between Two Temples is 978-93-5XXXX-05-9, but the Amazon "
            "India listing shows a completely different ISBN. Readers are confused and I'm worried sales are "
            "being attributed to the wrong book."
        ),
        "category": TicketCategory.ISBN_METADATA,
        "priority": TicketPriority.CRITICAL,
        "confidence": 0.97,
        "reasoning": "ISBN mismatch between listing and physical copy is a data integrity issue per policy.",
        "status": TicketStatus.OPEN,
        "created": _ago(days=3, hours=5),
    },
    {
        "author_id": "AUTH004",
        "book_id": "BK006",
        "subject": "Author copies arrived with blurry images and misaligned pages",
        "description": (
            "I received 20 author copies of Debugging Life yesterday. The diagrams in chapters 3-5 are blurry "
            "and several pages are printed off-centre. I can't gift these. What are my options?"
        ),
        "category": TicketCategory.PRINTING_QUALITY,
        "priority": TicketPriority.HIGH,
        "confidence": 0.95,
        "reasoning": "Print defects on delivered copies; eligible for verification and free reprint.",
        "status": TicketStatus.IN_PROGRESS,
        "created": _ago(days=4, hours=1),
        "assign_to": "admin@bookleaf.com",
        "messages": [
            {
                "kind": MessageKind.INTERNAL_NOTE,
                "by": "admin@bookleaf.com",
                "at": _ago(days=3, hours=22),
                "body": "Batch printed in-house on the 14th. Checking with print floor whether other orders from that run were affected.",
            },
            {
                "kind": MessageKind.ADMIN_REPLY,
                "by": "admin@bookleaf.com",
                "at": _ago(days=3, hours=20),
                "body": (
                    "Hi Vikram, I'm really sorry your author copies arrived in that condition — that's not the "
                    "standard we hold ourselves to. Could you share 2–3 photos of the blurry diagrams and one of a "
                    "misaligned page? Once verified (usually same day), we'll arrange a free reprint of all 20 copies, "
                    "which takes 5–7 business days from confirmation. I'll keep this ticket updated at each step."
                ),
            },
            {
                "kind": MessageKind.AUTHOR_MESSAGE,
                "by": "AUTH004",
                "at": _ago(days=3, hours=2),
                "body": "Thanks — photos attached. Please let me know once the reprint is confirmed.",
            },
        ],
        "attachments": [("defect_ch3_p41.jpg", "image/jpeg", 812_344), ("defect_ch5_p97.jpg", "image/jpeg", 905_120)],
    },
    {
        "author_id": "AUTH009",
        "book_id": "BK015",
        "subject": "Raising Roots has been in typesetting for 3 weeks",
        "description": (
            "My book has shown 'In Production - Typesetting' for three weeks now with no email update. "
            "Is something stuck? I'd like a realistic date for when it moves to proofreading."
        ),
        "category": TicketCategory.BOOK_STATUS_PRODUCTION,
        "priority": TicketPriority.MEDIUM,
        "confidence": 0.91,
        "reasoning": "Production stage delay inquiry; not blocking revenue but needs a concrete timeline.",
        "status": TicketStatus.OPEN,
        "created": _ago(days=2, hours=4),
    },
    {
        "author_id": "AUTH010",
        "book_id": "BK018",
        "subject": "Howrah Nights showing 'Currently Unavailable' on Amazon India",
        "description": (
            "Since Tuesday the Amazon India page for Howrah Nights says Currently Unavailable. I have a book "
            "launch event on Saturday and people are asking where to buy it. Please help urgently."
        ),
        "category": TicketCategory.DISTRIBUTION_AVAILABILITY,
        "priority": TicketPriority.HIGH,
        "confidence": 0.93,
        "reasoning": "Listing unavailable with a time-bound sales event; likely a stock sync issue.",
        "status": TicketStatus.OPEN,
        "created": _ago(days=1, hours=2),
    },
    {
        "author_id": "AUTH001",
        "book_id": None,
        "subject": "Can I update my author bio?",
        "description": "I'd like to refresh the author bio that appears on my book pages. Where do I do that?",
        "category": TicketCategory.GENERAL_INQUIRY,
        "priority": TicketPriority.LOW,
        "confidence": 0.96,
        "reasoning": "Routine profile update request; no financial or production impact.",
        "status": TicketStatus.OPEN,
        "created": _ago(hours=5),
    },
    {
        "author_id": "AUTH009",
        "book_id": "BK016",
        "subject": "₹850 pending on The Nagpur Notebooks — when is it paid?",
        "description": "My dashboard shows ₹850 pending royalty for The Nagpur Notebooks but no payout date. When will I receive it?",
        "category": TicketCategory.ROYALTY_PAYMENTS,
        "priority": TicketPriority.MEDIUM,
        "confidence": 0.9,
        "reasoning": "Pending amount is below the ₹1,000 payout threshold; needs the rollover explanation.",
        "status": TicketStatus.OPEN,
        "created": _ago(hours=12),
    },
    {
        "author_id": "AUTH007",
        "book_id": "BK013",
        "subject": "When will I receive cover proofs for Midnight in Mysore?",
        "description": "Status says Cover Design. Do I need to do anything on my side, or is the designer still working?",
        "category": TicketCategory.BOOK_STATUS_PRODUCTION,
        "priority": TicketPriority.LOW,
        "confidence": 0.92,
        "reasoning": "Status clarification during cover design stage.",
        "status": TicketStatus.RESOLVED,
        "created": _ago(days=10),
        "resolved": _ago(days=9, hours=4),
        "assign_to": "ops@bookleaf.com",
        "messages": [
            {
                "kind": MessageKind.ADMIN_REPLY,
                "by": "ops@bookleaf.com",
                "at": _ago(days=9, hours=4),
                "body": (
                    "Hi Sneha, thanks for checking in. Midnight in Mysore is with our cover designer and the first "
                    "two concepts will be emailed to you by Thursday. The next step is yours: pick a direction or "
                    "share feedback, and we move to typesetting within 2 business days of your approval."
                ),
            },
        ],
    },
    {
        "author_id": "AUTH005",
        "book_id": "BK009",
        "subject": "Royalty for 201 copies of Letters from Lakshadweep seems low",
        "description": "I sold 201 copies at ₹550 MRP but total royalty earned is only ₹11,055. Can you explain how that was calculated?",
        "category": TicketCategory.ROYALTY_PAYMENTS,
        "priority": TicketPriority.MEDIUM,
        "confidence": 0.95,
        "reasoning": "Royalty calculation question; needs the net-profit breakdown, no overdue payment.",
        "status": TicketStatus.CLOSED,
        "created": _ago(days=20),
        "resolved": _ago(days=18),
        "assign_to": "admin@bookleaf.com",
        "messages": [
            {
                "kind": MessageKind.ADMIN_REPLY,
                "by": "admin@bookleaf.com",
                "at": _ago(days=18, hours=6),
                "body": (
                    "Hi Meera, happy to walk you through it. Royalty is 80% of net profit per copy, where net profit "
                    "is MRP minus printing cost, platform commission (Amazon/Flipkart) and shipping. For Letters from "
                    "Lakshadweep that works out to ₹55 per copy × 201 copies = ₹11,055. I've emailed you the "
                    "line-by-line breakdown per platform; reply here if any line doesn't add up."
                ),
            },
            {
                "kind": MessageKind.AUTHOR_MESSAGE,
                "by": "AUTH005",
                "at": _ago(days=18, hours=1),
                "body": "That makes sense now, thank you for the breakdown.",
            },
        ],
    },
]


async def seed() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    async with SessionLocal() as db:
        # Wipe in FK-safe order.
        for model in (AiCall, Attachment, TicketMessage, Ticket, Book, AuthorProfile, User):
            await db.execute(delete(model))
        await db.execute(text("ALTER SEQUENCE ticket_number_seq RESTART WITH 1001"))

        author_pw = hash_password(AUTHOR_PASSWORD)
        admin_pw = hash_password(ADMIN_PASSWORD)

        admins: dict[str, User] = {}
        for a in ADMINS:
            u = User(id=uuid.uuid4(), email=a["email"], password_hash=admin_pw, role=Role.ADMIN, name=a["name"])
            db.add(u)
            admins[a["email"]] = u

        authors: dict[str, AuthorProfile] = {}
        author_users: dict[str, User] = {}
        for a in data["authors"]:
            u = User(
                id=uuid.uuid4(), email=a["email"].lower(), password_hash=author_pw, role=Role.AUTHOR, name=a["name"]
            )
            p = AuthorProfile(
                id=a["author_id"],
                user=u,
                phone=a.get("phone"),
                city=a.get("city"),
                joined_date=_d(a.get("joined_date")),
            )
            db.add_all([u, p])
            authors[a["author_id"]] = p
            author_users[a["author_id"]] = u
            for b in a["books"]:
                db.add(
                    Book(
                        id=b["book_id"],
                        author_id=a["author_id"],
                        title=b["title"],
                        isbn=b.get("isbn"),
                        genre=b.get("genre"),
                        publication_date=_d(b.get("publication_date")),
                        status=b["status"],
                        mrp=_money(b.get("mrp")),
                        royalty_per_copy=_money(b.get("author_royalty_per_copy")),
                        copies_sold=b.get("total_copies_sold") or 0,
                        royalty_earned=_money(b.get("total_royalty_earned")) or Decimal(0),
                        royalty_paid=_money(b.get("royalty_paid")) or Decimal(0),
                        royalty_pending=_money(b.get("royalty_pending")) or Decimal(0),
                        last_payout_date=_d(b.get("last_royalty_payout_date")),
                        print_partner=b.get("print_partner"),
                        available_on=list(b.get("available_on") or []),
                    )
                )
        await db.flush()

        for t in SAMPLE_TICKETS:
            created = t["created"]
            msgs = t.get("messages", [])
            last_activity = max([created] + [m["at"] for m in msgs])
            ticket = Ticket(
                id=uuid.uuid4(),
                author_id=t["author_id"],
                book_id=t["book_id"],
                subject=t["subject"],
                description=t["description"],
                status=t["status"],
                category=t["category"],
                priority=t["priority"],
                ai_category=t["category"],
                ai_priority=t["priority"],
                ai_confidence=t["confidence"],
                ai_reasoning=t["reasoning"],
                ai_status=AiStatus.DONE,
                assigned_to_id=admins[t["assign_to"]].id if t.get("assign_to") else None,
                resolved_at=t.get("resolved"),
                created_at=created,
                updated_at=last_activity,
                last_activity_at=last_activity,
            )
            db.add(ticket)
            for m in msgs:
                sender = admins.get(m["by"]) or author_users[m["by"]]
                db.add(
                    TicketMessage(
                        ticket=ticket, sender_id=sender.id, kind=m["kind"], body=m["body"], created_at=m["at"]
                    )
                )
            for fname, mime, size in t.get("attachments", []):
                db.add(Attachment(ticket=ticket, filename=fname, mime_type=mime, size_bytes=size, created_at=created))

        await db.commit()

    n_books = sum(len(a["books"]) for a in data["authors"])
    print(
        f"Seeded {len(data['authors'])} authors, {n_books} books, {len(ADMINS)} admins, {len(SAMPLE_TICKETS)} tickets."
    )


if __name__ == "__main__":
    asyncio.run(seed())
