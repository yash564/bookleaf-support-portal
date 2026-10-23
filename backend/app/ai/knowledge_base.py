"""The BookLeaf Knowledge Base, structured so prompts can include exactly the slice they need.

Source: the assignment brief's "BookLeaf Knowledge Base" section, reproduced faithfully. The full KB
is ~1.2k tokens; the tone guidelines + one category example are what actually steer a draft, so the
draft prompt sends: tone (always) + the full policy KB (stable, cache-marked) + ONE matched example.
"""

from __future__ import annotations

from app.models.enums import TicketCategory

COMPANY = """\
COMPANY OVERVIEW
- BookLeaf Publishing is a self-publishing company operating in India and the US.
- Publishing packages: Standard Free (no upfront cost) and Bestseller Breakthrough (premium, paid package with marketing and distribution add-ons).
- BookLeaf handles cover design, typesetting, ISBN assignment, printing, distribution, and royalty management.
- In-house printing facility and warehouse are in Delhi. Print partners: Repro India and Epitome Books."""

ROYALTY = """\
ROYALTY POLICY
- 80/20 royalty split: 80% of the net profit per book goes to the author, 20% to BookLeaf.
- Net profit = MRP minus printing cost, platform commission (Amazon/Flipkart), and shipping charges.
- Royalties are calculated quarterly and paid within 45 days of the quarter ending.
- Minimum payout threshold: ₹1,000. Accumulated royalties below this roll over to the next quarter.
- Payouts are made via bank transfer to the account linked in the author's dashboard.
- Authors can view a detailed royalty breakdown in their dashboard, showing sales figures per platform."""

ISBN = """\
ISBN POLICY
- Every book published through BookLeaf receives a unique ISBN assigned by BookLeaf.
- ISBNs are registered under BookLeaf's publisher imprint. An author who wants an ISBN under their own imprint must obtain it independently.
- An ISBN error (duplicate, wrong book linked) is a high-priority issue and is escalated to the production team."""

PRINTING = """\
PRINTING & QUALITY
- In-house printing handles most orders. Overflow or specific format requirements go to Repro India or Epitome Books.
- Standard print turnaround: 5–7 business days from order confirmation.
- Quality issues (misprints, binding defects, color inconsistency): BookLeaf arranges a free reprint after verification. The author may need to share photos of the defective copy."""

DISTRIBUTION = """\
DISTRIBUTION & AVAILABILITY
- Books are listed on Amazon India, Flipkart, Amazon US, Amazon UK, and the BookLeaf Store.
- New listings typically go live within 7–10 business days after publication is complete.
- A book showing as unavailable on a platform usually indicates a stock sync issue; BookLeaf's team can trigger a re-sync within 24–48 hours.
- Metadata updates (e.g. book description) can be submitted through the dashboard or by emailing BookLeaf; changes reflect on platforms within 3–5 business days."""

PRODUCTION = """\
PRODUCTION STAGES
- Stages: Manuscript Received → Editing (if opted) → Cover Design → Typesetting → Proofreading → ISBN Assignment → Printing → Distribution Setup → Published & Live.
- Authors are updated at each stage via email. Delays typically happen at Cover Design (waiting for author approval) and Proofreading (revision rounds)."""

TONE = """\
COMMUNICATION TONE (how BookLeaf writes to authors)
- Always empathetic and professional. Authors are partners, not customers to be managed.
- Acknowledge the author's concern before jumping to solutions.
- Be specific: include actual numbers, dates, and statuses wherever possible rather than vague reassurances.
- If something is BookLeaf's fault (delayed royalties, ISBN error), own it directly. No corporate deflection.
- If the issue needs escalation or investigation, give a clear timeline ("within 48 hours"), never an open-ended promise.
- Always end with a clear next step for the author and/or the BookLeaf team."""

FULL_KB = "\n\n".join([COMPANY, ROYALTY, ISBN, PRINTING, DISTRIBUTION, PRODUCTION])

# Calibration examples from the brief, keyed by category. One is injected per draft call.
EXAMPLES: dict[TicketCategory, list[tuple[str, str]]] = {
    TicketCategory.ROYALTY_PAYMENTS: [
        (
            "I published my book 4 months ago and still haven't received any royalty. What's going on?",
            "Acknowledge the frustration. Explain the quarterly royalty cycle and 45-day payout window. Check if their bank "
            "details are linked. Provide the specific next payout date. If the payment is genuinely overdue, escalate with a "
            "48-hour resolution timeline.",
        ),
        (
            "My royalty amount seems too low. I sold 200 copies but only received ₹3,000.",
            "Explain the net profit calculation: MRP minus printing, platform commission, and shipping. Offer to share a "
            "detailed line-by-line royalty breakdown. Don't be defensive—offer transparency.",
        ),
    ],
    TicketCategory.ISBN_METADATA: [
        (
            "My book is showing a different ISBN on Amazon than what's on the physical copy.",
            "Treat as high priority. Acknowledge this is a serious data issue. Confirm you are escalating to the production "
            "team immediately. Provide a 48-hour resolution timeline.",
        ),
    ],
    TicketCategory.PRINTING_QUALITY: [
        (
            "I received my author copies and the print quality is terrible. The images are blurry and pages are misaligned.",
            "Apologise sincerely. Ask the author to share photos of the defective copies. Confirm that BookLeaf will arrange "
            "a free reprint once verified. Provide a timeline of 5–7 business days for the reprint.",
        ),
    ],
    TicketCategory.DISTRIBUTION_AVAILABILITY: [
        (
            'My book is published but it\'s showing as "Currently Unavailable" on Amazon.',
            "Explain that this is typically a stock sync issue. Confirm you're triggering a re-sync with the distribution "
            "team. Set expectation: 24–48 hours for it to go live again.",
        ),
    ],
    TicketCategory.BOOK_STATUS_PRODUCTION: [
        (
            "It's been 3 weeks and my book is still in typesetting. When will it be done?",
            "Check the actual production status. If it's delayed, be honest about why (e.g., waiting on author approval for "
            "proofs). Provide a specific updated timeline. Don't blame the author even if the delay is on their side—frame "
            "it collaboratively.",
        ),
    ],
    TicketCategory.GENERAL_INQUIRY: [
        (
            "Can I update the description of my book on Amazon after it's already live?",
            "Yes, metadata updates can be submitted through the dashboard or by emailing the BookLeaf team. Changes "
            "typically reflect on platforms within 3–5 business days.",
        ),
    ],
}


def example_for(category: TicketCategory) -> str:
    pairs = EXAMPLES.get(category) or EXAMPLES[TicketCategory.GENERAL_INQUIRY]
    return "\n\n".join(f'Author wrote: "{q}"\nA good BookLeaf reply would: {a}' for q, a in pairs)
