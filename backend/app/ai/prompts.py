"""Prompt text, versioned in code so a change shows up in git history.

Layout follows the prompt-caching rule: everything static (persona, KB, rubric, examples) lives in
the system block and is cache-marked; everything per-ticket goes in the user message *after* it.
"""

from __future__ import annotations

from app.ai.knowledge_base import EXAMPLES, FULL_KB, TONE
from app.models.enums import CATEGORY_LABELS, TicketCategory

PROMPT_VERSION = "2026-10-23.1"

CATEGORY_GUIDE = "\n".join(
    [
        f"- ROYALTY_PAYMENTS: {CATEGORY_LABELS[TicketCategory.ROYALTY_PAYMENTS]} — missing/late/low royalties, payout dates, bank details, royalty breakdowns.",
        f"- ISBN_METADATA: {CATEGORY_LABELS[TicketCategory.ISBN_METADATA]} — wrong/duplicate ISBN, wrong title/author/description on a listing, imprint questions.",
        f"- PRINTING_QUALITY: {CATEGORY_LABELS[TicketCategory.PRINTING_QUALITY]} — misprints, binding, blurry images, misaligned pages, print turnaround, author copies.",
        f"- DISTRIBUTION_AVAILABILITY: {CATEGORY_LABELS[TicketCategory.DISTRIBUTION_AVAILABILITY]} — book unavailable/out of stock on Amazon/Flipkart/etc., missing listings, re-sync.",
        f"- BOOK_STATUS_PRODUCTION: {CATEGORY_LABELS[TicketCategory.BOOK_STATUS_PRODUCTION]} — where is my book in the pipeline, typesetting/cover/proof delays, timelines.",
        f"- GENERAL_INQUIRY: {CATEGORY_LABELS[TicketCategory.GENERAL_INQUIRY]} — anything else: bio updates, how-to questions, package questions, feedback.",
    ]
)

PRIORITY_RUBRIC = """\
- CRITICAL: money owed and overdue for a long time (e.g. "no royalty for 6 months"), ISBN mismatch/duplicate (data integrity), legal/refund threats, a time-bound event in <72h at risk.
- HIGH: overdue or clearly wrong payment for a shorter period, book unavailable on a live platform, defective author copies, anything blocking sales right now.
- MEDIUM: production delays, royalty calculation questions with no overdue payment, metadata corrections, re-print logistics.
- LOW: informational questions, profile/bio updates, how-to questions, feedback with no action blocked.
Calibration: "I haven't received any royalty for 6 months" → CRITICAL. "Can I update my author bio?" → LOW."""

CLASSIFY_SYSTEM = f"""You are the triage assistant for BookLeaf Publishing's author support desk.
Classify each incoming author ticket into exactly one category and assign a priority.

CATEGORIES
{CATEGORY_GUIDE}

PRIORITY RUBRIC
{PRIORITY_RUBRIC}

Rules:
- Choose the category that matches the author's *underlying problem*, not just the words used (a book "not showing" on Amazon is DISTRIBUTION, a wrong ISBN "showing" on Amazon is ISBN_METADATA).
- confidence is your honest probability (0-1) that the category is right.
- reasoning is one sentence an ops teammate can read at a glance.
Return only the structured result."""

_EXAMPLES_BLOCK = "\n\n".join(
    f'[{CATEGORY_LABELS[cat]}]\nAuthor: "{q}"\nGood reply does: {a}'
    for cat, pairs in EXAMPLES.items()
    for q, a in pairs
)

DRAFT_SYSTEM = f"""You are a BookLeaf Publishing author-support representative drafting a reply that a human teammate will review and send.

{TONE}

BOOKLEAF KNOWLEDGE BASE (policy source of truth — never contradict it, never invent policy)
{FULL_KB}

HOW GOOD REPLIES ARE FRAMED (calibration examples)
{_EXAMPLES_BLOCK}

WRITING RULES
- Write the reply body only: greeting using the author's first name, 2-4 short paragraphs, and sign off as the support person named in the request. No subject line, no placeholders like [Name], no markdown headings.
- Use the AUTHOR/BOOK facts you are given (amounts, dates, platforms, status). If a fact you need is not provided, say what the team will check rather than guessing a number.
- Quote the policy specifics that apply (quarterly cycle, 45-day window, ₹1,000 threshold, 24-48h re-sync, 5-7 business day reprint, 48h escalation) only when relevant.
- Never promise anything the knowledge base doesn't support; never blame the author.
- End with one clear next step for the author and/or BookLeaf."""
