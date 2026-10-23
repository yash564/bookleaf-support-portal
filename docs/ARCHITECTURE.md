# Architecture notes

Companion to the README. This is the "why", organised by the things an evaluator will ask about.

## 1. Request flow

```
                     ┌───────────────────────── Next.js (Vercel) ─────────────────────────┐
                     │  client components · TanStack Query · EventSource · JWT in storage │
                     └──────────────┬───────────────────────────────▲─────────────────────┘
                                    │ REST /api/v1 (Bearer)         │ SSE  /…/events (?token=)
┌───────────────────────────────────▼───────────────────────────────┴─────────────────────┐
│ FastAPI                                                                                 │
│  RequestIdMiddleware → CORS → router                                                    │
│  api/v1/*.py      HTTP concerns only: parse, auth dependency, call service, shape reply │
│  core/deps.py     get_current_user → AuthContext(user, role, author_id)                 │
│  services/        TicketService (lifecycle, authorization, broker signals)              │
│                   AuthService · ai_service (persist AI results, ledger, fallback)       │
│  repositories/    SQL only. Author methods always take author_id.                       │
│  realtime/        EventBroker (in-process pub/sub) · sse.event_stream (heartbeat 15s)   │
│  ai/              client (SDK + breaker) · prompts · knowledge_base · context ·          │
│                   classify · draft · fallback · pricing                                  │
└───────────────┬───────────────────────────────────────────────┬─────────────────────────┘
                │ SQLAlchemy async (asyncpg)                    │ anthropic SDK (HTTPS)
          PostgreSQL 16                                    Anthropic API
```

Rule of thumb used throughout: a router never touches a model; a repository never raises an HTTP error; the AI package never imports FastAPI or SQLAlchemy.

## 2. Data model

```
users ──1:0..1── author_profiles ──1:N── books
  │                    │
  │ (admins)           └──1:N── tickets ──1:N── ticket_messages
  └── tickets.assigned_to_id            └──1:N── attachments
                                        └──0:N── ai_calls (ledger; SET NULL on delete)
```

Design choices:
- **Dataset ids are preserved** (`AUTH001`, `BK001`) as natural primary keys so evaluators can cross-reference the JSON; users get UUIDs.
- **In-production books** are the same table with nullable `isbn`, `mrp`, `royalty_per_copy`, `publication_date`; `available_on` is JSON (`[]`). A single `is_published` property derives from the status string so UI and AI context agree.
- **Tickets carry two sets of triage fields**: `ai_*` (what the model said, with confidence/reasoning) and the effective `category`/`priority` plus `*_overridden` flags. Re-classification updates `ai_*` and only writes through to the effective fields when not overridden.
- `tickets.number` is a Postgres sequence starting at 1001: humans say "#1004", URLs use the UUID.
- `last_activity_at` drives list ordering and "updated 3h ago"; `resolved_at` supports future SLA reporting.
- Enums are stored as strings (readable in SQL, no migration per new value).

## 3. Authorization

- JWT payload: `sub`, `role`, `author_id`, `iat`, `exp`. Verified on every request; the user is re-read from the DB so a deleted account is locked out immediately.
- `CurrentAuthor` requires role AUTHOR **and** a linked profile; `CurrentAdmin` requires ADMIN. Routers declare the one they need, so the OpenAPI spec itself documents which role each endpoint serves.
- Author data access is structural: `TicketRepository.get_for_author(ticket_id, author_id)` and `BookRepository.get_for_author` filter on both keys. There is no code path that returns another author's row to an author, as opposed to a check that could be forgotten.
- Internal notes are filtered in the author schema (`TicketOut.from_model(admin=False)`) and never counted in `message_count`.

## 4. Realtime

Signals, not state. The broker publishes `{type, ticket_id, number, status, at}` to:
- `ticket:<id>` — both portals' ticket pages
- `author:<AUTHxxx>` — the author's list page
- `admin:queue` — the queue and stats

Browsers `EventSource` the matching stream (JWT via `?token=` since the API cannot set headers) and on any signal invalidate the relevant TanStack Query keys, which refetch over REST. Benefits: one serialisation path, no divergence between "pushed" and "fetched" representations, tiny payloads, and internal notes are trivially excluded from the author channel. `ping` every 15 s keeps proxies (Render/Vercel) from closing idle connections; `refetchInterval: 30s` covers the disconnected case. Drop-on-full queues mean a slow consumer never blocks a request. Scale-out path: replace `EventBroker` with a Redis-backed implementation of the same two methods.

## 5. AI pipeline

```
POST /tickets ──201──▶ BackgroundTask classify_ticket_task
                          │ messages.parse(system=[rubric, cache_control], user=ticket, output_format=Classification)
                          ├─ OK → ai_* fields, effective category/priority (unless overridden), ai_status=DONE, ledger row
                          └─ fail → rule-based fallback, ai_status=FALLBACK, ledger row with error, breaker++
POST /admin/tickets/{id}/ai-draft
                          │ cached? → return (0 tokens)
                          │ messages.create(system=[persona+tone+KB+examples, cache_control],
                          │                 user=[date, author/book facts, ticket, last 3 msgs])
                          ├─ OK → ticket.ai_draft (+generated_at), ledger row
                          └─ fail → 503 AI_UNAVAILABLE, ledger row; UI says "write manually"
```

Prompt-caching layout follows the rule "stable prefix first, volatile last": tools (none) → system (frozen text, cache-marked) → messages (per ticket). Nothing time-dependent lives in the system block; the date is in the user turn. The ledger records `cache_read_input_tokens` so cache effectiveness is observable, not assumed.

Why one classification call and not two: category and priority are correlated (an ISBN mismatch is high-priority *because* of the category), the structured schema makes the output deterministic to parse, and it halves the per-ticket cost.

Why facts from the DB and not from the model: the brief's tone guide says "be specific: include actual numbers and dates". A model can only be specific if it is handed the numbers; it must never be in a position to invent a payout date. `context.py` computes the next payout deadline from the quarterly cycle and flags sub-threshold rollover, so the draft can state them.

## 6. Error handling

`core/errors.py` converts `AppError` subclasses, FastAPI validation errors, Starlette HTTP errors and unhandled exceptions into one envelope. Service code raises domain errors (`NotFoundError("…", code="TICKET_NOT_FOUND")`, `ConflictError(code="TICKET_CLOSED")`, `ValidationFailed(details=[{field, message}])`) and never builds responses. Unhandled exceptions are logged with the request id and returned as a generic 500 with that id so the author can quote it.

## 7. Testing

`backend/tests` runs the real ASGI app over httpx against a throwaway `bookleaf_test` database (schema from metadata, same as the migration). The AI layer is tested in three modes: unconfigured (503s and fallback), model failure (monkeypatched to raise → fallback + ledger), model success (monkeypatched to return a `Classification` → persistence, override preservation, draft caching). Pure functions (rules, payout dates, pricing, breaker) have unit tests.

## 8. Frontend structure

```
src/lib/        api.ts (fetch wrapper + error envelope + token) · types.ts · auth.tsx (session, RequireRole)
                realtime.ts (useLiveEvents) · format.ts (labels, money, dates, badge tones)
src/components/ ui.tsx (Button, Badge, Card, Field, Select, …) · thread.tsx · app-shell.tsx · toast.tsx
src/app/        login · author/{books, tickets, tickets/new, tickets/[id]} · admin/{tickets, tickets/[id], usage}
```

Every page is a client component under a role-gated layout; server state lives in TanStack Query and is invalidated by SSE signals. The API client is the only module that knows URLs or the error envelope, and types mirror the Pydantic schemas (the OpenAPI spec is the contract).
