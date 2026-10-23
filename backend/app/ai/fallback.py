"""Rule-based classifier used when the model is unavailable.

Deliberately simple and transparent: keyword hits per category, plus a priority rubric that mirrors
the AI prompt. It is clearly labelled in the UI as "rule-based" so nobody mistakes it for the model.
"""

from __future__ import annotations

import re

from app.models.enums import TicketCategory, TicketPriority

_KEYWORDS: dict[TicketCategory, tuple[str, ...]] = {
    TicketCategory.ROYALTY_PAYMENTS: (
        "royalt",
        "payout",
        "payment",
        "paid",
        "bank",
        "money",
        "₹",
        "rs.",
        "earning",
        "amount",
    ),
    TicketCategory.ISBN_METADATA: ("isbn", "metadata", "wrong title", "author name", "description", "listing shows"),
    TicketCategory.PRINTING_QUALITY: (
        "print",
        "binding",
        "blurry",
        "misalign",
        "quality",
        "defect",
        "pages",
        "cover is",
        "copies arrived",
    ),
    TicketCategory.DISTRIBUTION_AVAILABILITY: (
        "unavailable",
        "out of stock",
        "amazon",
        "flipkart",
        "listing",
        "not showing",
        "available on",
        "stock",
    ),
    TicketCategory.BOOK_STATUS_PRODUCTION: (
        "typesetting",
        "proofread",
        "cover design",
        "production",
        "status",
        "manuscript",
        "when will",
        "stage",
        "editing",
    ),
}

_HIGH_SIGNALS = (
    "not received",
    "haven't received",
    "havent received",
    "no royalty",
    "overdue",
    "months",
    "isbn",
    "wrong book",
    "unavailable",
    "urgent",
    "launch",
    "refund",
    "legal",
)
_LOW_SIGNALS = ("bio", "update my", "how do i", "can i", "where do i", "profile", "question")


def classify_by_rules(subject: str, description: str) -> tuple[TicketCategory, TicketPriority, str]:
    text = f"{subject}\n{description}".lower()
    scores = {cat: sum(1 for kw in kws if kw in text) for cat, kws in _KEYWORDS.items()}
    best, best_score = max(scores.items(), key=lambda kv: kv[1])
    category = best if best_score > 0 else TicketCategory.GENERAL_INQUIRY

    if any(s in text for s in _HIGH_SIGNALS):
        priority = TicketPriority.HIGH
        # Money owed for a long time, or an ISBN data error, is the top of the rubric.
        if re.search(r"\b([3-9]|1[0-2])\s*months?\b", text) or (
            "isbn" in text and ("wrong" in text or "different" in text)
        ):
            priority = TicketPriority.CRITICAL
    elif any(s in text for s in _LOW_SIGNALS):
        priority = TicketPriority.LOW
    else:
        priority = TicketPriority.MEDIUM

    hits = ", ".join(f"{c.value.lower()}={n}" for c, n in scores.items() if n)
    reasoning = f"Rule-based fallback (AI unavailable). Keyword hits: {hits or 'none'}."
    return category, priority, reasoning
