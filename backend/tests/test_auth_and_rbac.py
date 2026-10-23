import pytest


async def test_login_returns_token_and_profile(client, seed):
    r = await client.post("/api/v1/auth/login", json={"email": "a1@test.com", "password": "pw"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "AUTHOR"
    assert body["user"]["author_id"] == "AUTH001"


async def test_bad_password_is_401_with_envelope(client, seed):
    r = await client.post("/api/v1/auth/login", json={"email": "a1@test.com", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert r.headers["x-request-id"]


async def test_invalid_email_is_422(client, seed):
    r = await client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "pw"})
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["field"] == "email"


async def test_missing_token_is_401(client, seed):
    r = await client.get("/api/v1/books")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_garbage_token_is_401(client, seed):
    r = await client.get("/api/v1/books", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


@pytest.mark.parametrize("path", ["/api/v1/admin/tickets", "/api/v1/admin/tickets/stats", "/api/v1/admin/ai/usage"])
async def test_author_cannot_use_admin_endpoints(client, author_h, path):
    r = await client.get(path, headers=author_h)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_cannot_use_author_endpoints(client, admin_h):
    r = await client.get("/api/v1/books", headers=admin_h)
    assert r.status_code == 403


async def test_me(client, admin_h):
    r = await client.get("/api/v1/auth/me", headers=admin_h)
    assert r.status_code == 200 and r.json()["role"] == "ADMIN"
