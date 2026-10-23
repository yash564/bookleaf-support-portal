"""End-to-end ticket lifecycle with AI disabled (rule-based fallback path)."""

from tests.conftest import NEW_TICKET


async def _create(client, h, **overrides):
    r = await client.post("/api/v1/tickets", json={**NEW_TICKET, **overrides}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_ticket_is_201_and_classified_by_rules_when_ai_off(client, author_h, admin_h):
    t = await _create(client, author_h)
    assert t["number"] >= 1001 and t["status"] == "OPEN" and t["book"]["id"] == "BK001"
    # BackgroundTasks run inside the ASGI transport before the response completes in tests.
    r = await client.get(f"/api/v1/admin/tickets/{t['id']}", headers=admin_h)
    body = r.json()
    assert body["ai"]["status"] == "SKIPPED"
    assert body["category"] == "ROYALTY_PAYMENTS"
    assert body["priority"] == "CRITICAL"  # "6 months" of missing money → top of the rubric
    assert "Rule-based" in body["ai"]["reasoning"]


async def test_general_ticket_without_book(client, author_h):
    t = await _create(
        client,
        author_h,
        book_id=None,
        subject="Can I update my author bio?",
        description="Where do I edit the bio shown on my book pages?",
    )
    assert t["book"] is None


async def test_validation_errors_are_422_with_field_details(client, author_h):
    r = await client.post("/api/v1/tickets", json={"subject": "x", "description": "short"}, headers=author_h)
    assert r.status_code == 422
    fields = {d["field"] for d in r.json()["error"]["details"]}
    assert {"subject", "description"} <= fields


async def test_cannot_file_ticket_against_another_authors_book(client, author2_h):
    r = await client.post("/api/v1/tickets", json=NEW_TICKET, headers=author2_h)
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["field"] == "book_id"


async def test_author_isolation(client, author_h, author2_h):
    t = await _create(client, author_h)
    assert (await client.get(f"/api/v1/tickets/{t['id']}", headers=author2_h)).status_code == 404
    mine = (await client.get("/api/v1/tickets", headers=author2_h)).json()
    assert mine["total"] == 0 and mine["items"] == []


async def test_internal_notes_hidden_from_author_and_reply_visible(client, author_h, admin_h):
    t = await _create(client, author_h)
    url = f"/api/v1/admin/tickets/{t['id']}/messages"
    assert (
        await client.post(url, json={"kind": "INTERNAL_NOTE", "body": "finance is checking"}, headers=admin_h)
    ).status_code == 201
    r = await client.post(url, json={"kind": "ADMIN_REPLY", "body": "Hi Priya, looking into it."}, headers=admin_h)
    assert r.status_code == 201
    admin_view = r.json()
    assert [m["kind"] for m in admin_view["messages"]] == ["INTERNAL_NOTE", "ADMIN_REPLY"]
    assert admin_view["status"] == "IN_PROGRESS"  # replying starts work
    assert admin_view["assigned_to"]["name"] == "Ada Admin"  # and takes ownership

    author_view = (await client.get(f"/api/v1/tickets/{t['id']}", headers=author_h)).json()
    assert [m["kind"] for m in author_view["messages"]] == ["ADMIN_REPLY"]
    assert author_view["message_count"] == 1


async def test_override_sets_audit_flags(client, author_h, admin_h):
    t = await _create(client, author_h)
    r = await client.patch(f"/api/v1/admin/tickets/{t['id']}", json={"priority": "LOW"}, headers=admin_h)
    assert r.status_code == 200
    body = r.json()
    assert body["priority"] == "LOW" and body["ai"]["priority_overridden"] is True
    assert body["ai"]["category_overridden"] is False
    assert body["ai"]["priority"] == "CRITICAL"  # the AI's original call is preserved for audit


async def test_patch_rejects_unknown_enum_and_non_admin_assignee(client, author_h, admin_h):
    t = await _create(client, author_h)
    r = await client.patch(f"/api/v1/admin/tickets/{t['id']}", json={"priority": "URGENT"}, headers=admin_h)
    assert r.status_code == 422
    r = await client.patch(
        f"/api/v1/admin/tickets/{t['id']}",
        json={"assigned_to_id": "00000000-0000-0000-0000-000000000000"},
        headers=admin_h,
    )
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "assigned_to_id"


async def test_assign_to_self_moves_open_to_in_progress(client, author_h, admin_h):
    t = await _create(client, author_h)
    me = (await client.get("/api/v1/auth/me", headers=admin_h)).json()["id"]
    body = (await client.patch(f"/api/v1/admin/tickets/{t['id']}", json={"assigned_to_id": me}, headers=admin_h)).json()
    assert body["status"] == "IN_PROGRESS" and body["assigned_to"]["id"] == me
    body = (
        await client.patch(f"/api/v1/admin/tickets/{t['id']}", json={"assigned_to_id": None}, headers=admin_h)
    ).json()
    assert body["assigned_to"] is None


async def test_lifecycle_resolve_reopen_close(client, author_h, admin_h):
    t = await _create(client, author_h)
    url = f"/api/v1/admin/tickets/{t['id']}"
    body = (await client.patch(url, json={"status": "RESOLVED"}, headers=admin_h)).json()
    assert body["status"] == "RESOLVED" and body["resolved_at"]
    # Author replying to a resolved ticket reopens it.
    body = (
        await client.post(f"/api/v1/tickets/{t['id']}/messages", json={"body": "Still nothing."}, headers=author_h)
    ).json()
    assert body["status"] == "OPEN" and body["resolved_at"] is None
    await client.patch(url, json={"status": "CLOSED"}, headers=admin_h)
    r = await client.post(f"/api/v1/tickets/{t['id']}/messages", json={"body": "Hello?"}, headers=author_h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "TICKET_CLOSED"


async def test_queue_sorts_urgent_and_oldest_first_and_filters(client, author_h, admin_h):
    low = await _create(
        client,
        author_h,
        subject="Can I update my author bio?",
        description="I'd like to refresh my bio, how do I do it?",
    )
    crit = await _create(client, author_h)
    q = (await client.get("/api/v1/admin/tickets", headers=admin_h)).json()
    assert [t["number"] for t in q["items"]] == [crit["number"], low["number"]]
    assert q["total"] == 2
    q = (await client.get("/api/v1/admin/tickets", params={"priority": "LOW"}, headers=admin_h)).json()
    assert [t["number"] for t in q["items"]] == [low["number"]]
    q = (await client.get("/api/v1/admin/tickets", params={"q": "bio"}, headers=admin_h)).json()
    assert q["total"] == 1
    q = (await client.get("/api/v1/admin/tickets", params={"assigned": "unassigned"}, headers=admin_h)).json()
    assert q["total"] == 2
    stats = (await client.get("/api/v1/admin/tickets/stats", headers=admin_h)).json()
    assert stats["by_status"]["OPEN"] == 2 and stats["unassigned_open"] == 2


async def test_unknown_ticket_is_404(client, admin_h):
    r = await client.get("/api/v1/admin/tickets/00000000-0000-0000-0000-000000000000", headers=admin_h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "TICKET_NOT_FOUND"
