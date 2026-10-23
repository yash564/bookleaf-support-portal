# BookLeaf Author Support & Communication Portal

A two-sided support desk for BookLeaf Publishing: authors raise and follow queries about their books; the ops team triages a queue where every ticket is **auto-classified and prioritised by Claude**, and every reply starts from an **AI draft grounded in the BookLeaf knowledge base and the author's real royalty data**.

| | |
|---|---|
| **Live demo** | _frontend_: `https://<vercel-app>.vercel.app` · _API docs_: `https://<render-service>.onrender.com/docs` (fill in after deploy, see [Deployment](#deployment)) |
| **Stack** | Next.js 16 (App Router, TypeScript, Tailwind 4, TanStack Query) · FastAPI (Python 3.12, SQLAlchemy 2 async, Alembic, Pydantic v2) · PostgreSQL 16 · Anthropic Claude (`claude-haiku-5-5`) · Server-Sent Events |
| **Repo layout** | `backend/` API · `frontend/` web app · `docs/` architecture, write-up, plan · `docker-compose.yml` local Postgres · `render.yaml` API deploy blueprint |

## Test credentials

| Role | Email | Password | Notes |
|---|---|---|---|
| Admin | `admin@bookleaf.com` | `admin123` | Aarav Mehta, owns a couple of seeded tickets |
| Admin | `ops@bookleaf.com` | `admin123` | Nisha Verma |
| Author | `priya.sharma@email.com` | `password123` | 2 published books, ₹3,570 pending |
| Author | `kavita.deshmukh@email.com` | `password123` | one book **in production**, one with ₹850 pending (below the ₹1,000 threshold) |
| Author | `ananya.reddy@email.com` | `password123` | one book, zero payouts so far |
| Author | any of the 10 dataset emails | `password123` | `rohit.kapoor@…`, `vikram.joshi@…`, `meera.nair@…`, `arjun.malhotra@…`, `sneha.kulkarni@…`, `farhan.sheikh@…`, `diya.chatterjee@…` |

The database is seeded with the 10 authors and 18 books from `bookleaf_sample_data.json` verbatim, plus nine realistic tickets so the admin queue is meaningful on first login.

## Run it locally

Prerequisites: Docker, Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
# 1. Postgres
docker compose up -d db                      # postgres:16 on localhost:5433

# 2. API
cd backend
cp .env.example .env                         # set ANTHROPIC_API_KEY (optional) and a 32+ char JWT_SECRET
uv sync
uv run alembic upgrade head                  # create schema
uv run python -m scripts.seed                # load the dataset + demo tickets (idempotent)
uv run uvicorn app.main:app --reload         # http://localhost:8000  ·  Swagger at /docs

# 3. Web app
cd ../frontend
cp .env.example .env.local                   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                                  # http://localhost:3000
```

Without an `ANTHROPIC_API_KEY` the app still works end to end: tickets are classified by the rule-based fallback (clearly labelled in the UI) and the draft button explains that AI is unavailable. Add a key and restart to see the model in action.

Tests (backend, 37 integration + unit tests against a throwaway `bookleaf_test` database on the same Postgres):

```bash
cd backend && uv run pytest -q && uv run ruff check app tests
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

## What's in the box

**Author portal** — `/author/*`
- Email/password login; every author-scoped query is filtered by the author id *inside the JWT*, never by a request parameter.
- **My Books**: royalty roll-up (sold / earned / paid / pending) plus a per-title table. Handles the dataset's edge cases explicitly: books in production show an "In production · stage" badge with royalty cells blank; pending amounts under ₹1,000 are flagged as rolling over; fully paid titles read "Nothing pending".
- **Submit a query**: book dropdown (or General / Account Level), subject, description, attachment picker (UI-only per the brief; filenames and sizes are stored as metadata so the ops team can see what was offered).
- **My Tickets** + ticket thread: status chips, original query, replies. Updates arrive live over SSE; replying to a resolved ticket reopens it; closed tickets are read-only.

**Admin portal** — `/admin/*`
- **Queue**: stats strip (unresolved, critical/high, unassigned, oldest waiting), filters for status, category, priority, assignee (Mine / Unassigned), date range and free-text search. Default sort is *urgency*: unresolved first → priority → oldest first, so the most urgent and oldest tickets are at the top. Hot rows are tinted; tickets waiting 2+ days show their age in red.
- **Ticket workspace**: conversation with internal notes inline (amber, lock icon, never sent to the author); composer with **AI draft / Regenerate**; triage panel with status, category, priority (each shows "AI suggested X" when overridden, with confidence and reasoning), assignee / Assign to me; author card; **book card with the real royalty numbers** so the admin can check what the draft claims.
- **AI usage**: the token ledger behind every model call, with an estimated cost.

## Architecture

```
Browser ──REST (JSON, Bearer JWT)──▶ FastAPI /api/v1 ──▶ services ──▶ repositories ──▶ Postgres
   ▲                                      │                 │
   └────── SSE (ticket signals) ◀── broker ◀────────────────┘  (publish on every ticket change)
                                                            └──▶ ai/ (Anthropic SDK; backend-only key)
```

- **Layers** (`backend/app/`): `api/v1` routers (HTTP only) → `services` (workflows, authorization, realtime signals) → `repositories` (SQL) → `models`. `schemas` are the Pydantic request/response contracts and the single source for the OpenAPI spec. `ai/` is a self-contained package (client, prompts, knowledge base, classify, draft, fallback, pricing) with no FastAPI imports, so it is unit-testable and swappable.
- **Data model**: `users` (login + role) ← `author_profiles` (dataset `AUTH001…`) ← `books` (dataset `BK001…`, nullable money/date columns for in-production titles) ← `tickets` ← `ticket_messages` / `attachments`; `ai_calls` is the cost ledger. Tickets store *both* the AI's original category/priority/confidence/reasoning and the admin-effective values, with `category_overridden` / `priority_overridden` flags, so overrides are auditable and re-classification never clobbers a human decision.
- **Auth & RBAC**: bcrypt passwords, HS256 JWT (7-day). `CurrentAuthor` / `CurrentAdmin` dependencies gate every route; author repositories take `author_id` from the token. SSE endpoints accept `?token=` because `EventSource` cannot set headers (documented in the spec).
- **Errors**: one envelope for every non-2xx — `{"error": {"code", "message", "request_id", "details"?}}` — with stable codes (`TICKET_NOT_FOUND`, `TICKET_CLOSED`, `VALIDATION_ERROR`, `AI_UNAVAILABLE`, …) and field-level validation details. `X-Request-Id` on every response for log correlation.
- **Realtime**: an in-process pub/sub broker publishes tiny *signals* (`ticket.updated`, `message.created`, `ticket.classified`, …) on three channels (per ticket, per author, admin queue). SSE streams them with a 15 s heartbeat; the browser refetches via the normal REST endpoints, so there is exactly one serialisation path and nothing can go stale between the two. Clients also poll every 30 s as a fallback. For multi-instance deployments the broker swaps for Redis pub/sub behind the same `publish`/`subscribe` interface.
- **Frontend**: all pages are client components behind a role-gated layout; TanStack Query owns server state and is invalidated by SSE signals; a small hand-written UI kit instead of a component library (less to explain, nothing hidden).

Why this shape: it mirrors how a real ops tool is built (typed contracts, thin routers, testable services), gives a genuinely separate REST API to evaluate, and FastAPI's generated OpenAPI satisfies the documentation requirement without a hand-maintained spec. More in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## AI integration

**Model**: `claude-haiku-5-5` via the official `anthropic` Python SDK, configurable with `ANTHROPIC_MODEL`. Chosen because (a) classification and support drafting are routine tasks where Haiku's quality is more than sufficient, (b) it is the cheapest current model ($0.10 / $0.50 per million input/output tokens, ~10× cheaper than Haiku 4.5), and (c) its prompt-cache minimum is 512 tokens, so the ~2k-token knowledge-base block actually gets cached (on Haiku 4.5 the minimum is 4096 and it would silently not cache). Swapping to Sonnet is one env var; prices for both are in `ai/pricing.py`.

**Prompt strategy** (`backend/app/ai/prompts.py`, `knowledge_base.py`, `context.py`):
1. **Classification + priority in one call**, using structured outputs (a Pydantic schema → `output_config.format`), not two calls and not free-text parsing. The system prompt defines the six categories by *underlying problem*, a four-level priority rubric with the brief's calibration pairs ("no royalty for 6 months" → CRITICAL, "update my bio" → LOW), and asks for an honest confidence and a one-line reasoning that the admin sees. `effort: low`, 400 max tokens.
2. **Drafts** use a *static* system block — persona, tone guidelines, the full knowledge base, and the brief's seven query→response calibration examples — marked with `cache_control`, followed by a *per-ticket* user message containing: today's date, structured **author and book facts from the database** (status, ISBN, pending royalty, last payout, whether the pending amount is below the ₹1,000 threshold, the computed next payout date under the quarterly + 45-day policy, platforms), the ticket, and only the **last 3 messages truncated to 600 chars**. The model is told to quote policy specifics only when relevant, to say "we will check" rather than invent numbers, and to end with a next step. Result: drafts like "your ₹3,570 from the quarter ending 30 Sep will reach you by 14 Nov", not generic reassurance.
3. **Drafts are generated lazily** (when an admin asks) and **cached on the ticket**; re-opening costs zero tokens; "Regenerate" is an explicit choice.

**Error handling / graceful degradation** (`ai/client.py`, `services/ai_service.py`):
- Classification runs as a FastAPI `BackgroundTask` *after* the 201 is sent — an AI outage can never block ticket creation or slow it down.
- SDK exceptions are mapped to one domain error (`AI_UNAVAILABLE`, 503) with a status for the ledger (`RATE_LIMITED`, `TIMEOUT`, `ERROR`). On failure the ticket gets a **rule-based keyword classification**, marked `FALLBACK` and labelled "Rule-based (AI was unavailable)" in the UI; the draft panel tells the admin to write manually. Admin overrides are preserved across re-classification.
- A **circuit breaker** opens after 3 consecutive failures for 2 minutes, so a dead API doesn't add a 20 s timeout to every ticket; the SDK's own retry/backoff handles transient 429/5xx.
- 20 s timeout, 2 retries, structured-output validation errors treated as failures.

**Cost awareness**: one call per ticket for triage, at most one per draft (cached), the static KB block is prompt-cached, history is truncated, the description is capped. Every call is written to `ai_calls` with input/output/cache-read/cache-write tokens and latency; `GET /admin/ai/usage` (and the AI Usage page) turns it into an estimated cost per purpose. Expected steady state with Haiku 5.5: roughly **$0.0002 per classified ticket and $0.0004 per draft** (≈ ₹0.05 per ticket end to end).

**Key security**: `ANTHROPIC_API_KEY` is read by pydantic-settings on the backend only; the frontend never talks to Anthropic; `.env` is git-ignored and `.env.example` ships blank.

## API

Interactive docs: **`/docs`** (Swagger) and `/redoc`; machine-readable spec at `/openapi.json`. All routes except login and `/health` require `Authorization: Bearer <jwt>`.

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/login` | – | `{email, password}` → `{access_token, user}` |
| GET | `/api/v1/auth/me` | any | Current user (used to restore the session) |
| POST | `/api/v1/auth/logout` | any | 204 (stateless JWT; client discards token) |
| GET | `/api/v1/books` | author | My books + royalty summary |
| GET | `/api/v1/tickets` | author | My tickets, `?status=` |
| POST | `/api/v1/tickets` | author | Create → 201; AI classification runs afterwards |
| GET | `/api/v1/tickets/{id}` | author | Ticket + thread (internal notes excluded) |
| POST | `/api/v1/tickets/{id}/messages` | author | Follow-up; reopens RESOLVED; 409 on CLOSED |
| GET | `/api/v1/tickets/events/stream` | author | SSE for all my tickets (`?token=`) |
| GET | `/api/v1/tickets/{id}/events` | author | SSE for one ticket |
| GET | `/api/v1/admin/tickets` | admin | Queue: `status` (repeatable), `category`, `priority`, `assigned` (`me`/`unassigned`/id), `q`, `created_from`, `created_to`, `sort` (`urgency`/`newest`/`oldest`/`activity`), `limit`, `offset` |
| GET | `/api/v1/admin/tickets/stats` | admin | Counts by status/priority, unassigned, oldest open |
| GET | `/api/v1/admin/tickets/events` | admin | SSE for the whole queue |
| GET | `/api/v1/admin/tickets/{id}` | admin | Full ticket incl. notes, AI metadata, cached draft, book facts |
| PATCH | `/api/v1/admin/tickets/{id}` | admin | `{status?, category?, priority?, assigned_to_id?}` (null unassigns) |
| POST | `/api/v1/admin/tickets/{id}/messages` | admin | `{kind: ADMIN_REPLY \| INTERNAL_NOTE, body}` → 201 |
| POST | `/api/v1/admin/tickets/{id}/ai-draft` | admin | AI draft (cached); `?regenerate=true`; 503 `AI_UNAVAILABLE` when down |
| POST | `/api/v1/admin/tickets/{id}/ai-classify` | admin | Re-run classification; overrides preserved |
| GET | `/api/v1/admin/tickets/{id}/events` | admin | SSE for one ticket |
| GET | `/api/v1/admin/users` | admin | Admin accounts (assignment dropdown) |
| GET | `/api/v1/admin/ai/usage` | admin | Token + cost ledger, `?since=YYYY-MM-DD` |
| GET | `/health` | – | Liveness + whether AI is configured |

Conventions: plural nouns, 201 on create, 204 on no content, PATCH for partial updates, enums as upper-snake strings, money as decimal strings, timestamps ISO-8601 UTC.

## Deployment

The app is split so each half lands on a free tier: **Neon** (Postgres) + **Render** (API, Docker) + **Vercel** (Next.js).

1. **Neon**: create a project, copy the connection string and convert it to the asyncpg form: `postgresql+asyncpg://user:pass@host/db?ssl=require`.
2. **Render**: *New → Blueprint* pointing at this repo (`render.yaml` is picked up). Set `DATABASE_URL`, `ANTHROPIC_API_KEY`, and `CORS_ORIGINS=https://<your-vercel-app>.vercel.app`. The container runs `alembic upgrade head` and, with `SEED_ON_START=true`, seeds the dataset on boot — flip it to `false` after the first deploy so demo data survives restarts. Free Render services sleep after idle; the first request can take ~30–50 s.
3. **Vercel**: import the repo, set **Root Directory** to `frontend`, add `NEXT_PUBLIC_API_URL=https://<render-service>.onrender.com`. Deploy.
4. Paste both URLs into the table at the top of this README.

## Known limitations & what I'd do next

- **Single-process realtime**: the SSE broker is in-memory. Fine for one Render instance; use Redis pub/sub (same interface) to scale out. Polling every 30 s is the safety net.
- **Attachments are metadata only** (as the brief allows). Next: S3/R2 presigned uploads, and pass defect photos to the model for printing-quality tickets (Claude is multimodal).
- **JWT in localStorage** keeps the demo simple; production would use an httpOnly refresh cookie + short-lived access token, rate limiting on login, and password reset.
- **No author-side notifications** beyond the live view (email/WhatsApp on reply would be the first ops request).
- **AI evaluation**: there is a rule-based fallback and a usage ledger, but no offline eval set yet. I'd log admin edits to drafts (edit distance) and overrides as implicit labels, build a 50-ticket golden set from them, and track classification accuracy and draft acceptance per prompt version (`PROMPT_VERSION` is already in code).
- **Draft personalisation**: the draft is signed by whichever admin generates it, but cached per ticket, so a second admin sees the first one's name — easy to re-sign on send.
- **Royalty "next payout" is computed from the quarter calendar**, not from a payouts table; a real system would read scheduled payout runs.
- SQLite is not supported for tests (the ticket-number sequence is Postgres-only); tests need the Docker Postgres.
