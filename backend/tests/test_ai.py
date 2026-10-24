"""AI layer: graceful degradation, override preservation, draft caching, unit rules.

The model is never called in tests; `classify`/`draft_reply` are monkeypatched where a success
path is needed, and left unconfigured (no key) where the failure path is under test.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.ai import client as ai_client
from app.ai.classify import Classification
from app.ai.context import next_payout_deadline
from app.ai.fallback import classify_by_rules
from app.ai.pricing import estimate_cost_usd
from app.config import get_settings
from app.models.enums import AiCallStatus, TicketCategory, TicketPriority
from app.services import ai_service
from tests.conftest import NEW_TICKET


def _ok_outcome(**usage):
    return ai_client.AiOutcome(AiCallStatus.OK, "claude-haiku-5-5", 120, usage=ai_client.Usage(**usage))


@pytest.fixture
def ai_on(monkeypatch):
    """Pretend a key is configured so the service takes the 'call the model' branch."""
    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    yield
    get_settings.cache_clear()


# ---------- degradation (no key configured) ----------


async def test_draft_returns_503_when_ai_unconfigured(client, author_h, admin_h):
    t = (await client.post("/api/v1/tickets", json=NEW_TICKET, headers=author_h)).json()
    r = await client.post(f"/api/v1/admin/tickets/{t['id']}/ai-draft", headers=admin_h)
    assert r.status_code == 503 and r.json()["error"]["code"] == "AI_DISABLED"
    r = await client.post(f"/api/v1/admin/tickets/{t['id']}/ai-classify", headers=admin_h)
    assert r.status_code == 503


# ---------- success path with a patched model ----------


async def test_classification_persists_and_respects_admin_override(client, author_h, admin_h, monkeypatch, ai_on):
    async def fake_classify(subject, description, book_line):
        return Classification(
            category=TicketCategory.ROYALTY_PAYMENTS,
            priority=TicketPriority.HIGH,
            confidence=0.91,
            reasoning="Overdue royalty.",
        ), _ok_outcome(input_tokens=700, output_tokens=60)

    monkeypatch.setattr(ai_service, "classify", fake_classify)
    t = (await client.post("/api/v1/tickets", json=NEW_TICKET, headers=author_h)).json()
    body = (await client.get(f"/api/v1/admin/tickets/{t['id']}", headers=admin_h)).json()
    assert body["ai"]["status"] == "DONE" and body["ai"]["confidence"] == 0.91
    assert body["category"] == "ROYALTY_PAYMENTS" and body["priority"] == "HIGH"

    # Admin overrides priority, then re-runs classification: the override must survive.
    await client.patch(f"/api/v1/admin/tickets/{t['id']}", json={"priority": "LOW"}, headers=admin_h)
    body = (await client.post(f"/api/v1/admin/tickets/{t['id']}/ai-classify", headers=admin_h)).json()
    assert body["priority"] == "LOW" and body["ai"]["priority"] == "HIGH" and body["ai"]["priority_overridden"] is True

    usage = (await client.get("/api/v1/admin/ai/usage", headers=admin_h)).json()
    row = next(r for r in usage["rows"] if r["purpose"] == "CLASSIFY")
    assert row["calls"] == 2 and row["ok"] == 2 and row["input_tokens"] == 1400
    assert Decimal(usage["total_cost_usd"]) > 0


async def test_model_failure_falls_back_to_rules_and_is_logged(client, author_h, admin_h, monkeypatch, ai_on):
    async def failing_classify(subject, description, book_line):
        err = ai_service.AiUnavailableError("down")
        err.outcome = ai_client.AiOutcome(AiCallStatus.RATE_LIMITED, "claude-haiku-5-5", 50, error="429")
        raise err

    monkeypatch.setattr(ai_service, "classify", failing_classify)
    t = (await client.post("/api/v1/tickets", json=NEW_TICKET, headers=author_h)).json()
    assert t["status"] == "OPEN"  # ticket creation unaffected
    body = (await client.get(f"/api/v1/admin/tickets/{t['id']}", headers=admin_h)).json()
    assert body["ai"]["status"] == "FALLBACK" and body["category"] == "ROYALTY_PAYMENTS"
    usage = (await client.get("/api/v1/admin/ai/usage", headers=admin_h)).json()
    row = next(r for r in usage["rows"] if r["purpose"] == "CLASSIFY")
    assert row["calls"] == 1 and row["failed"] == 1


async def test_draft_is_cached_until_regenerate(client, author_h, admin_h, monkeypatch, ai_on):
    calls = []

    async def fake_draft(ticket, *, agent_name, today=None):
        calls.append(agent_name)
        return f"Hi Priya, draft #{len(calls)} from {agent_name}.", _ok_outcome(
            input_tokens=2000, output_tokens=250, cache_read_tokens=1500
        )

    monkeypatch.setattr(ai_service, "draft_reply", fake_draft)
    t = (await client.post("/api/v1/tickets", json=NEW_TICKET, headers=author_h)).json()
    url = f"/api/v1/admin/tickets/{t['id']}/ai-draft"
    first = (await client.post(url, headers=admin_h)).json()
    assert first["cached"] is False and "Ada Admin" in first["draft"]
    second = (await client.post(url, headers=admin_h)).json()
    assert second["cached"] is True and second["draft"] == first["draft"]
    third = (await client.post(url, params={"regenerate": "true"}, headers=admin_h)).json()
    assert third["cached"] is False and "draft #2" in third["draft"]
    assert len(calls) == 2
    # Draft also visible on the ticket for the UI, and the author never sees it.
    assert (await client.get(f"/api/v1/admin/tickets/{t['id']}", headers=admin_h)).json()["ai_draft"] == third["draft"]
    assert "ai_draft" not in (await client.get(f"/api/v1/tickets/{t['id']}", headers=author_h)).json()


# ---------- unit: rules, dates, pricing, breaker ----------


@pytest.mark.parametrize(
    "subject,desc,cat,prio",
    [
        (
            "No royalty for 6 months",
            "I haven't received any royalty in six months.",
            TicketCategory.ROYALTY_PAYMENTS,
            TicketPriority.CRITICAL,
        ),
        (
            "Can I update my author bio?",
            "Where do I change the bio?",
            TicketCategory.GENERAL_INQUIRY,
            TicketPriority.LOW,
        ),
        (
            "Can I update my author bio?",
            "I'd like to refresh the bio that appears on my book pages.",
            TicketCategory.GENERAL_INQUIRY,
            TicketPriority.LOW,
        ),
        (
            "Wrong ISBN on Amazon",
            "Amazon shows a different ISBN than the printed copy.",
            TicketCategory.ISBN_METADATA,
            TicketPriority.CRITICAL,
        ),
        (
            "Blurry print",
            "Author copies arrived with blurry images and misaligned pages.",
            TicketCategory.PRINTING_QUALITY,
            TicketPriority.MEDIUM,
        ),
        (
            "Currently Unavailable",
            "My book shows unavailable on Amazon since Tuesday.",
            TicketCategory.DISTRIBUTION_AVAILABILITY,
            TicketPriority.HIGH,
        ),
        (
            "Stuck in typesetting",
            "Three weeks in typesetting, when will it be done?",
            TicketCategory.BOOK_STATUS_PRODUCTION,
            TicketPriority.MEDIUM,
        ),
    ],
)
def test_rule_based_classifier(subject, desc, cat, prio):
    c, p, reasoning = classify_by_rules(subject, desc)
    assert (c, p) == (cat, prio) and "Rule-based" in reasoning


def test_next_payout_deadline_follows_quarterly_45_day_policy():
    assert next_payout_deadline(date(2026, 10, 23)) == (date(2026, 9, 30), date(2026, 11, 14))
    assert next_payout_deadline(date(2026, 11, 20)) == (date(2026, 12, 31), date(2027, 2, 14))
    assert next_payout_deadline(date(2026, 1, 5)) == (date(2025, 12, 31), date(2026, 2, 14))


def test_pricing_estimate():
    cost = estimate_cost_usd("claude-haiku-5-5", input_tokens=1_000_000, output_tokens=0, cache_read=0, cache_write=0)
    assert cost == Decimal("0.10")
    cached = estimate_cost_usd("claude-haiku-5-5", input_tokens=0, output_tokens=0, cache_read=1_000_000, cache_write=0)
    assert cached == Decimal("0.01")


def test_circuit_breaker_opens_after_threshold_and_resets():
    b = ai_client.CircuitBreaker(threshold=2, cooldown_seconds=60)
    b.record_failure()
    assert not b.is_open
    b.record_failure()
    assert b.is_open
    b.record_success()
    assert not b.is_open
