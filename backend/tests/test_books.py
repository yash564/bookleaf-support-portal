async def test_my_books_with_summary_and_in_production_edge_case(client, author_h):
    r = await client.get("/api/v1/books", headers=author_h)
    assert r.status_code == 200
    body = r.json()
    by_id = {b["id"]: b for b in body["items"]}
    assert set(by_id) == {"BK001", "BK013"}
    live, prod = by_id["BK001"], by_id["BK013"]
    assert live["is_published"] is True and live["royalty_pending"] == "3570.00"
    assert prod["is_published"] is False and prod["mrp"] is None and prod["isbn"] is None and prod["available_on"] == []
    s = body["summary"]
    assert s["total_books"] == 2 and s["published_books"] == 1 and s["in_production_books"] == 1
    assert s["total_royalty_pending"] == "3570.00" and s["pending_below_threshold"] is False


async def test_author_with_no_books_gets_empty_state(client, author2_h):
    r = await client.get("/api/v1/books", headers=author2_h)
    assert r.status_code == 200
    assert r.json()["items"] == [] and r.json()["summary"]["total_books"] == 0
