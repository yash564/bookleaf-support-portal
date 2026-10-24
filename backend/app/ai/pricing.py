"""Published per-million-token prices used to turn the usage ledger into money.

Only an estimate for the dashboard; billing truth lives in the provider console.
Cache reads: Anthropic bills 10% of input, OpenAI 50%. Cache writes (Anthropic only): 125%.
"""

from __future__ import annotations

from decimal import Decimal

# model -> (input $/MTok, output $/MTok, cache-read multiplier on input price)
PRICES: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "claude-haiku-5-5": (Decimal("0.10"), Decimal("0.50"), Decimal("0.10")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00"), Decimal("0.10")),
    "claude-sonnet-5-5": (Decimal("2.00"), Decimal("10.00"), Decimal("0.10")),
    "claude-opus-5-5": (Decimal("4.00"), Decimal("20.00"), Decimal("0.05")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60"), Decimal("0.50")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("1.60"), Decimal("0.25")),
    "gpt-4.1-nano": (Decimal("0.10"), Decimal("0.40"), Decimal("0.25")),
}
DEFAULT_PRICE = PRICES["claude-haiku-5-5"]
_M = Decimal(1_000_000)


def price_for(model: str) -> tuple[Decimal, Decimal, Decimal]:
    return PRICES.get(model, DEFAULT_PRICE)


def estimate_cost_usd(
    model: str, *, input_tokens: int, output_tokens: int, cache_read: int, cache_write: int
) -> Decimal:
    inp, out, cache_mult = price_for(model)
    cost = (
        Decimal(input_tokens) * inp
        + Decimal(output_tokens) * out
        + Decimal(cache_read) * inp * cache_mult
        + Decimal(cache_write) * inp * Decimal("1.25")
    ) / _M
    return cost.quantize(Decimal("0.000001"))
