"""Published per-million-token prices used to turn the usage ledger into money.

Only an estimate for the dashboard; billing truth lives in the Anthropic console.
Cache reads are 10% of input price, cache writes 125%, per Anthropic's pricing page.
"""

from __future__ import annotations

from decimal import Decimal

# model -> (input $/MTok, output $/MTok)
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "claude-haiku-5-5": (Decimal("0.10"), Decimal("0.50")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
    "claude-sonnet-5-5": (Decimal("2.00"), Decimal("10.00")),
    "claude-opus-5-5": (Decimal("4.00"), Decimal("20.00")),
}
_M = Decimal(1_000_000)


def estimate_cost_usd(
    model: str, *, input_tokens: int, output_tokens: int, cache_read: int, cache_write: int
) -> Decimal:
    inp, out = PRICES.get(model, PRICES["claude-haiku-5-5"])
    cost = (
        Decimal(input_tokens) * inp
        + Decimal(output_tokens) * out
        + Decimal(cache_read) * inp * Decimal("0.10")
        + Decimal(cache_write) * inp * Decimal("1.25")
    ) / _M
    return cost.quantize(Decimal("0.000001"))
