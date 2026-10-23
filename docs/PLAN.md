# BookLeaf Author Support & Communication Portal — Build Plan

Assignment: BookLeaf Publishing, Full-Stack Developer, Assignment 1 of 2.
Deadline: 4 days from receipt (received 2026-10-23 → target submission 2026-10-27).
Deliverables: public GitHub repo (yash564), live URL, README, 1-page write-up.

Scoring weights drive priority: AI integration 25%, architecture/code quality 25%,
API design 15%, functionality 15%, product thinking 10%, docs 10%.

---

## 1. Stack (recommended)

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 15 (App Router, TypeScript), Tailwind + shadcn/ui, TanStack Query | Clean, functional UI (brief says not pixel-perfect); typed API client generated from the backend's OpenAPI |
| Backend | FastAPI (Python 3.12 via uv), SQLAlchemy 2 async + asyncpg, Alembic migrations, Pydantic v2 | Clean REST layer with free Swagger/OpenAPI at `/docs`; matches the stack you can explain line-by-line |
| DB | PostgreSQL (Docker locally, Neon free tier in prod) | Relational schema is the point (authors→books→tickets→messages); Alembic for migrations, a seed script for the JSON dataset |
| Auth | Email/password, bcrypt, JWT bearer (access token in memory + httpOnly refresh cookie), FastAPI dependency `get_current_user` / `require_role` | Simple, no third-party auth; RBAC via `role` claim enforced in dependencies and at the repository layer |
| Validation | Pydantic request/response models on every route; shared error envelope `{ "error": { "code", "message", "details" } }` via exception handlers | Meaningful 400/401/403/404/409/422 instead of generic 500s |
| AI | Anthropic Claude Haiku 4.5 via the `anthropic` Python SDK, backend-only | Cheap, fast, strict JSON via tool-use; prompt caching for the static knowledge base |
| Real-time | SSE via `sse-starlette`; in-process async broker publishes ticket events; `EventSource` on the client with auto-reconnect; polling fallback | Native in FastAPI, no extra infra; Redis pub/sub upgrade path for multi-instance noted in the write-up |
| API docs | FastAPI-generated OpenAPI at `/docs` and `/openapi.json` + README endpoint table | Explicit requirement, zero manual drift |
| Deploy | Vercel (frontend) + Render free web service (backend, Dockerfile) + Neon (db) | All free; Render free tier cold-starts after idle (~30–50 s) — noted in README; Railway is a drop-in alternative |

Alternative considered: Next.js full-stack with Route Handlers (one deploy). Chosen split instead
because it mirrors your day-job stack, gives a genuinely separate REST API to evaluate, and FastAPI's
OpenAPI output satisfies the documentation requirement without hand-authoring a spec.

Local dev: `docker compose up db` for Postgres 16; backend on :8000, frontend on :3000 with
`NEXT_PUBLIC_API_URL`. CORS allowlist from env.

---

## 2. Data model (SQLAlchemy / Alembic)

```
User            id, email (unique), passwordHash, role (AUTHOR|ADMIN), name, createdAt
AuthorProfile   id (AUTH001…), userId (1:1), phone, city, joinedDate
Book            id (BK001…), authorId → AuthorProfile, title, isbn, genre, publicationDate?,
                status, mrp?, royaltyPerCopy?, copiesSold, royaltyEarned, royaltyPaid,
                royaltyPending, lastPayoutDate?, printPartner?, availableOn (string[])
Ticket          id, authorId, bookId?, subject, description,
                status (OPEN|IN_PROGRESS|RESOLVED|CLOSED),
                category (enum of 6), priority (CRITICAL|HIGH|MEDIUM|LOW),
                aiCategory?, aiPriority?, aiConfidence?, aiReasoning?,   -- AI's original call
                categoryOverridden bool, priorityOverridden bool,         -- admin override audit
                aiDraft?, aiDraftGeneratedAt?, aiStatus (PENDING|DONE|FAILED|SKIPPED),
                assignedToId? → User, createdAt, updatedAt, resolvedAt?
TicketMessage   id, ticketId, senderId → User, kind (AUTHOR_MESSAGE|ADMIN_REPLY|INTERNAL_NOTE),
                body, createdAt
Attachment      id, ticketId, filename, mimeType, size   (metadata only — UI-only upload per brief)
AiCall          id, ticketId?, purpose (CLASSIFY|DRAFT), model, inputTokens, outputTokens,
                cacheReadTokens, latencyMs, status (OK|ERROR|RATE_LIMITED|TIMEOUT), error?, createdAt
```

Edge cases from the dataset handled explicitly:
- 2 books in production (`mrp`, `publicationDate`, `isbn`-only, empty `availableOn`) → "In production" badge, royalty cells show "—", book still selectable in the ticket form.
- Zero payouts with pending > 0 (BK005, BK010, BK016, BK018) → "Pending, below/above ₹1,000 threshold" hint (BK016 pending ₹850 rolls over; that's a KB fact the AI must also use).
- Fully paid books → "Nothing pending".
- Authors with one vs. many books; empty ticket list → empty states.

Seed (`backend/scripts/seed.py`, idempotent): 10 authors + 18 books verbatim from
`bookleaf_sample_data.json`, all authors with password `password123`; 2 admins
(`admin@bookleaf.com`, `ops@bookleaf.com`); ~8 realistic seeded tickets spread across
categories/priorities/statuses so the admin queue demos well on first login.

---

## 3. REST API (`/api/v1`)

Auth
- `POST /auth/login` `{email, password}` → sets cookie, returns user
- `POST /auth/logout`
- `GET  /auth/me`

Author scope (role AUTHOR; always filtered by the caller's authorId)
- `GET  /books`                          my books
- `GET  /tickets`                        my tickets (+ `?status=`)
- `POST /tickets`                        create `{bookId?, subject, description, attachments?[]}` → 201; AI classify runs after response
- `GET  /tickets/:id`                    ticket + messages (internal notes excluded for authors)
- `POST /tickets/:id/messages`           author follow-up
- `GET  /tickets/:id/events`             SSE stream

Admin scope (role ADMIN)
- `GET   /admin/tickets`                 queue; filters `status, category, priority, assignedTo, from, to, q`; sort default = priority desc, createdAt asc (urgent + oldest first)
- `GET   /admin/tickets/:id`             full ticket incl. internal notes, AI meta, author + book context
- `PATCH /admin/tickets/:id`             `{status?, category?, priority?, assignedToId?}` — sets override flags
- `POST  /admin/tickets/:id/messages`    `{kind: ADMIN_REPLY|INTERNAL_NOTE, body}`
- `POST  /admin/tickets/:id/ai/draft`    generate (or `?regenerate=true`) the AI draft → cached on the ticket
- `POST  /admin/tickets/:id/ai/classify` re-run classification
- `GET   /admin/tickets/events`          SSE stream for the queue
- `GET   /admin/stats`                   counts by status/priority for the header strip
- `GET   /admin/ai/usage`                tokens + cost summary from `AiCall` (cost-awareness evidence)

Conventions: plural nouns, 201 on create, 204 on no-content, consistent error envelope,
`X-Request-Id` on every response, Pydantic schemas per router reused by the generated OpenAPI.

RBAC: `get_current_user` dependency verifies the JWT; `require_role(Role.ADMIN)` on admin routers;
author repositories always take `author_id` from the token (never from the request) so cross-author
leakage is structurally impossible, not just checked.

---

## 4. AI integration (the 25%)

`backend/app/ai/` as a self-contained package: `client.py` (SDK + timeouts + retry on 429/529 +
circuit breaker), `prompts/` (system prompts as versioned files), `knowledge_base.py` (KB split into
sections keyed by category), `classify.py`, `draft.py`, `fallback.py`, `usage.py`.

1. **Classification + priority in ONE call** using tool-use with a strict JSON schema
   `{category, priority, confidence, reasoning}`. Runs as a FastAPI `BackgroundTask` after ticket creation, never
   blocks the 201. Prompt includes the 6 category definitions, priority rubric (money overdue / ISBN
   error / unavailable listing = high+; bio updates = low), and 2–3 few-shot pairs from the brief.
2. **Draft response** generated lazily when an admin opens the ticket, cached in `aiDraft`,
   "Regenerate" button. Prompt =
   - static system block (tone guidelines + full KB) marked with `cache_control` → Anthropic prompt
     caching makes repeated calls ~10x cheaper on input,
   - the matching sample query→response example for the classified category,
   - **structured author/book context** pulled from the DB (status, pending royalty, last payout,
     next payout date computed from the quarterly cycle, platforms listed) so the draft is specific
     ("your pending ₹3,570 from Q3 will be paid by 14 Nov"), not generic,
   - the ticket subject/description + only the last 3 messages, each truncated to ~600 chars.
3. **Graceful degradation**: AI failure → `aiStatus=FAILED`, keyword-rule fallback sets a provisional
   category/priority flagged "auto (rule-based)"; draft panel shows "AI unavailable — write manually".
   Ticket creation and replies never depend on the AI call. Circuit-breaker: after N consecutive
   failures skip calls for 2 min.
4. **Cost awareness**: one call per ticket for classify, one per draft (cached), prompt caching on
   the static KB, truncated history, `AiCall` table logs every call's tokens → `/admin/ai/usage` and
   a line in the README with measured ₹/ticket.
5. **Key security**: `ANTHROPIC_API_KEY` only in the backend's env (pydantic-settings); the
   frontend never talks to Anthropic; `.env.example` committed, `.env` ignored.

---

## 5. UI

Author portal (`/author/*`): Login → My Books (table/cards with royalty summary strip: earned/paid/
pending across all books) → Submit Query (book dropdown incl. "General / Account Level", subject,
description, attachment picker UI-only, success toast linking to the ticket) → My Tickets (list with
status chips + detail with the conversation thread; live via SSE).

Admin portal (`/admin/*`): Queue (stats strip, filters: status/category/priority/date/assignee/
search, default sort urgent+oldest first, "Unassigned" and "Mine" quick filters, SLA-age column) →
Ticket detail (left: conversation + internal notes tab; right: AI panel with category/priority
chips showing AI value + override dropdown + confidence, draft editor with Regenerate / Send,
author + book context card, assign-to-me, status select).

---

## 6. Repo layout

```
bookleaf-support-portal/
  backend/
    app/
      main.py, config.py, db/ (session, base), models/, schemas/,
      api/v1/ (auth, books, tickets, admin_tickets, admin_stats, events),
      core/ (security, deps, errors, request_id), repositories/, services/,
      ai/ (client, prompts/, knowledge_base, classify, draft, fallback, usage), realtime/ (broker, sse)
    alembic/, scripts/seed.py, data/bookleaf_sample_data.json, tests/, Dockerfile, pyproject.toml
  frontend/
    src/app/ (auth)/login, (author)/author/{books,tickets,tickets/new,tickets/[id]}, (admin)/admin/{tickets,tickets/[id]}
    src/lib/ api-client (generated from openapi.json), auth, sse
    src/components/ ...
  docker-compose.yml (db), docs/ ARCHITECTURE.md, WRITEUP.md, PLAN.md
  README.md, backend/.env.example, frontend/.env.example
```

---

## 7. Schedule

| Day | Work | Commits (progressive history is a plus) |
|---|---|---|
| 1 (Oct 23–24) | Repo + backend/frontend scaffolds, docker-compose Postgres, SQLAlchemy models + Alembic migration, seed from JSON, auth + RBAC deps, My Books page | `chore: scaffold`, `feat(db): schema + seed`, `feat(auth): …`, `feat(author): my books` |
| 2 (Oct 25) | Tickets API (author + admin), submit form, my tickets, admin queue + filters, AI classify/priority + fallback | `feat(tickets): …`, `feat(ai): classification`, `feat(admin): queue` |
| 3 (Oct 26) | AI draft w/ KB + caching, reply/notes/assign/status, SSE real-time, usage logging, empty states | `feat(ai): drafts`, `feat(realtime): sse`, `feat(admin): ticket detail` |
| 4 (Oct 27) | Deploy Render (backend) + Vercel (frontend) + Neon, seed prod, README (endpoint table + OpenAPI link), write-up, test creds, final QA of every scored criterion | `docs: …`, `chore: deploy` |

---

## 8. Open inputs needed from you

1. ~~Stack~~ → Next.js + FastAPI (confirmed 2026-10-23).
2. `ANTHROPIC_API_KEY` for `backend/.env` (confirmed provider; key still needed).
3. Accounts for Vercel, Render and Neon (free; I can drive the CLIs once you log in).
4. ~~Repo~~ → `github.com/yash564/bookleaf-support-portal`, local `/Users/yash/bookleaf-support-portal`,
   commits authored as yash564 (noreply email). Confirmed.
