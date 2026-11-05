# Architecture

## 1. Overview

```
            ┌──────────────┐  HTTPS   ┌──────────────┐   SQL    ┌─────────────────┐
 Browser ──▶│  apps/web    │────────▶ │  apps/api    │────────▶ │ PostgreSQL 16   │
 (AR/EN)    │  Next.js     │  /api/v1 │  FastAPI     │          │ (Railway)       │
            └──────────────┘          └──────┬───────┘          └─────────────────┘
                                             │  S3 API                ▲
                                             ▼                        │
                                      ┌──────────────┐        ┌──────────────┐
                                      │ Object store │        │ apps/worker  │ freshness, image
                                      │ (S3-compat)  │        │ (Python)     │ processing, digests
                                      └──────────────┘        └──────────────┘
                                             ▲
                                   LLM provider (M3, via LLMProvider abstraction)
```

- **apps/web** — Next.js 15 App Router. Server Components fetch public data from the API (SSR for SEO);
  Client Components handle forms and the authenticated dashboard. Locale-prefixed routes `/en/...`, `/ar/...`;
  `<html dir>` follows locale. Next rewrites proxy `/api/v1/*` and `/media/*` to the API, so the browser only ever
  talks to the web origin: auth cookies are first-party and no CORS is needed. UI primitives in
  `components/ui` follow the shadcn/ui pattern (vendored, Tailwind v4 + cva) rather than the CLI generator.
- **apps/api** — FastAPI, Pydantic v2, SQLAlchemy 2 (async, psycopg 3), Alembic. Single source of truth for
  business rules and authorization. Publishes OpenAPI consumed by `packages/contracts`.
- **apps/worker** — Python process sharing `apps/api` models (installed as a package). M1: placeholder with
  freshness-expiry job; scheduled through Railway cron.
- **packages/contracts** — TypeScript types generated from the API's OpenAPI schema; the web app imports them.

## 2. API layering

```
app/
  api/v1/        routers (HTTP only: parse, call service, map errors)
  schemas/       Pydantic request/response models
  services/      business logic, transactions
  authz/         policy functions: can_edit_listing(user, listing) ...
  models/        SQLAlchemy ORM models
  db/            engine/session, base
  core/          config, security (hashing, JWT), logging, rate limiting, errors
  storage/       StorageBackend protocol: LocalStorage, S3Storage
  ai/            (M3) LLMProvider protocol, tools, orchestrator
```

Routers never touch the ORM directly for writes; services do. Every mutating service call receives the
authenticated principal and calls an `authz` policy before reading/writing a resource.

## 3. Authentication

- Passwords hashed with **argon2id** (`argon2-cffi`). Minimum 10 chars; checked against a short common-password list.
- On login, the API issues an **access JWT** (15 min, HS256, `sub`, `role`, `jti`) and an **opaque refresh token**
  (30 days, stored hashed in `refresh_tokens`, rotated on use; reuse of a rotated token revokes the family).
- Tokens are set as `httpOnly; Secure; SameSite=Lax` cookies. Mutating requests from browsers require a
  CSRF double-submit header (`X-CSRF-Token` must equal the `csrf_token` cookie). Bearer header auth is also
  accepted for non-browser clients/tests (CSRF not required when no cookie auth is used).

## 4. Authorization model

- **Role** on user: `seeker | owner | broker | platform_admin`.
- **Tenancy**: brokers act within an **organization**; `organization_members.role ∈ {agency_admin, agent}`.
- Policies (in `app/authz/policies.py`):
  - Listing **read (public)**: `status = published AND NOT expired AND (NOT is_demo OR demo_mode)`.
  - Listing **read (private)/edit/publish/pause/media**: creator; or `agency_admin` of the listing's
    organization; or `platform_admin`. Agents can edit only their own listings.
  - Lead **read**: the listing's creator; agency admins of its org; platform admins.
  - Create listing: role ∈ {owner, broker, platform_admin}.
- Non-authorized access to private resources returns **404** (not 403) to avoid ID enumeration.
- Tests include a policy matrix and cross-tenant integration tests.

## 5. Search (M1, deterministic)

SQL filters: transaction type, location (including descendants via materialized `path` column on `locations`),
price range, bedrooms (min), bathrooms (min), furnished, property type. Sort: newest / price asc / price desc.
Offset pagination capped at 50 per page. Indexes documented in DATABASE.md.

## 6. AI search design (M3)

Principles: **grounded**, **deterministic filtering first**, **untrusted content isolation**.

1. `extract_intent` — LLM call with a strict JSON schema (Pydantic) to extract
   `{transaction, locations[], budget_min/max, bedrooms, furnished, amenities[], must_haves[], nice_to_haves[], language}`.
   Location strings resolved against `locations` table (name_en, name_ar, aliases incl. Arabizi) — never by the LLM.
2. Clarification: only if a **hard** constraint is missing *and* result count is > N or 0 (e.g. no
   location and no budget). Max one clarifying question per turn.
3. `search_listings` tool → same deterministic service as public search (hard filters).
4. Ranking: deterministic score on soft preferences (amenities overlap, price closeness, freshness),
   optionally LLM re-rank of top-K **using only structured fields**.
5. Explanations: generated from a template over matched fields ("2 bedrooms ✓, under $1,200 ✓, Achrafieh ✓"),
   so reasons cannot contain invented facts.
6. Tools exposed to the model: `search_listings`, `get_listing`, `resolve_location`, `create_lead`.
   `create_lead` requires a server-side consent token produced only by an explicit UI click — the model
   cannot fabricate consent. Tools run with the **end user's** principal; no admin tools exposed.
7. Listing descriptions are passed inside clearly delimited `<untrusted_listing_text>` blocks and are never
   used as instructions; outputs are validated against tool results. Prompt-injection test suite in `tests/ai/`.
8. Telemetry per call: provider, model, tokens in/out, cost estimate, latency, tool calls, result count,
   clicked result rank (for matching quality). Stored in `ai_requests` (M3).

`LLMProvider` protocol has `complete(messages, tools, schema) -> Response`. Adapters: Anthropic (default),
OpenAI-compatible (optional), `FakeProvider` for tests. Provider/model chosen via env vars.

## 7. Uploads

Browser → API multipart (M1, ≤ 8 MB/image, ≤ 20 images/listing). API sniffs content with Pillow (JPEG/PNG/WebP
only), rejects mismatched/decompression-bomb images, re-encodes to WebP (strips EXIF/GPS), stores via
`StorageBackend`. Local dev: filesystem under `apps/api/var/media`, served by the API at `/media/*`.
Production: S3-compatible bucket (Railway bucket / Cloudflare R2), public-read objects with random keys.
Presigned direct uploads are a later optimization.

## 8. Rate limiting

In-process sliding-window limiter keyed by IP (+ user id when authenticated) on: login, register, lead
creation, WhatsApp handoff, AI search. Adequate for single API replica; move to Postgres/Redis-backed
limiter before scaling horizontally (ADR-007).

## 9. Observability

JSON logs to stdout (request id, user id, route, status, latency). `/healthz` (process) and `/readyz` (DB).
Audit log rows for security-relevant actions (login, listing publish/pause, role changes).
Sentry is optional and **not** enabled without approval (paid service tiers).

## 10. Internationalization

`next-intl` message catalogs `messages/en.json`, `messages/ar.json`. Tailwind logical utilities
(`ms-*`, `pe-*`, `start-*`, `text-start`) so components mirror automatically in RTL. Fonts: system stack with Noto Sans Arabic / Segoe UI / Tahoma fallbacks for Arabic
(no build-time Google Fonts fetch; can move to self-hosted `next/font/local` later). Listing content has `title_en/title_ar` and `description_en/description_ar`; the UI falls back
to the other language when one is missing.
