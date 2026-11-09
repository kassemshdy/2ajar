# Implementation backlog

Each item is written as an issue: ID, title, acceptance criteria (AC). Status: ✅ done · 🟡 partial · ⬜ todo.
Items can be converted to GitHub issues later (one issue per heading).

## M0 — Foundations

### B-001 ✅ Planning docs
AC: PRD, ARCHITECTURE, DATABASE (ERD), API, ROADMAP, DECISIONS, DEPLOYMENT, BACKLOG exist in `docs/`.

### B-002 ✅ Monorepo scaffold
AC: `apps/web`, `apps/api`, `apps/worker`, `packages/contracts`, `infra`, `tests` exist; root README explains local setup;
`.env.example` files with no real secrets; `.gitignore` covers env files, venvs, node_modules, media.

### B-003 🟡 CI pipeline (workflow written; not yet observed running on GitHub Actions)
AC: GitHub Actions runs on PR and `main`: ruff, mypy, pytest (Postgres service), alembic up/down/up, web lint,
typecheck, build, Playwright smoke. Fails on any error.

## M1 — Vertical slice

### B-010 ✅ API core
AC: settings via env (pydantic-settings); refuses to start with `ENV=production` and `DEMO_MODE=true` or default
`JWT_SECRET`; JSON logging with request id; `/healthz`, `/readyz`; uniform error envelope.

### B-011 ✅ Initial schema migration
AC: Alembic migration creates M1 tables with UUID PKs, UTC timestamps, indexes from DATABASE.md; downgrade drops
cleanly; CI runs upgrade → downgrade → upgrade.

### B-012 ✅ Registration & login
AC: register seeker/owner/broker; broker may create organization and becomes `agency_admin`; argon2id hashes;
duplicate email → 409; weak password → 422; login sets httpOnly cookies + CSRF cookie; wrong password → 401 with
generic message; login/register rate-limited (429).

### B-013 ✅ Refresh rotation & logout
AC: refresh rotates token; reusing a rotated token revokes the family (401); logout revokes and clears cookies.

### B-014 ✅ Authorization policies
AC: central policy module; unit-tested matrix (creator, agent of same org, agency admin, other org, seeker,
platform admin); private resources return 404 to unauthorized callers.

### B-015 ✅ Locations
AC: seed of Lebanese governorates/districts/areas with EN/AR names; `GET /locations`; search by parent slug
includes descendants.

### B-016 ✅ Listing CRUD & lifecycle
AC: create draft (property + listing); patch; publish validates required fields (title in ≥ 1 language, price > 0,
location, bedrooms for residential, WhatsApp number, ≥ 1 photo when `PUBLISH_REQUIRES_MEDIA=true`); pause;
confirm extends `expires_at`; audit log entries for publish/pause.

### B-017 ✅ Image uploads
AC: JPEG/PNG/WebP only by content sniffing (not extension); > 8 MB → 413; non-image/polyglot → 422;
decompression bomb rejected; re-encoded to WebP without EXIF; max 20 per listing; storage backend abstraction
(local + S3).

### B-018 ✅ Public search & detail
AC: filters (transaction, location, price range, bedrooms_min, bathrooms_min, furnished, property type), sort,
pagination; only published, non-expired listings; demo listings hidden unless `DEMO_MODE`; contact number not
present in payload.

### B-019 ✅ WhatsApp handoff
AC: endpoint logs `whatsapp_click` event and returns `wa.me` URL with prefilled reference text in the user's
language; rate-limited; 404 for non-public listing.

### B-020 ✅ Lead capture with consent & dedupe
AC: `consent` must be `true` (422 otherwise); stores consent timestamp + text version; phone normalized to E.164
(LB default), invalid → 422; same phone + listing within 24h → returns existing lead (200), increments
`duplicate_count`; rate-limited; lead visible to listing manager via `/me/leads`, not to others.

### B-021 ✅ Demo seed
AC: `python -m app.seed` idempotent; ~30 demo listings across Beirut/Metn/Baabda/Keserwan with `is_demo=true`;
refuses to run with `ENV=production`.

### B-022 ✅ Web: i18n + RTL shell
AC: `/en` and `/ar` routes; `<html lang dir>` correct; language switcher; logical CSS properties; Arabic font.

### B-023 ✅ Web: search & listing detail
AC: filter form syncs to URL query; listing cards; detail page with gallery, facts, WhatsApp button, lead form
with mandatory consent checkbox; demo badge; mobile layout at 375px without horizontal scroll.

### B-024 ✅ Web: auth & dashboard
AC: register (role choice, optional agency name), login, logout; dashboard lists my listings with status and
actions (publish/pause/edit) and recent leads; create/edit listing form with image upload.

### B-025 ✅ Playwright smoke
AC: desktop + mobile projects; AR page has `dir=rtl`; broker registers → creates listing → uploads image →
publishes → visitor finds it → submits lead with consent → broker sees lead.

### B-026 ✅ Contracts generation
AC: `pnpm contracts:gen` writes TS types from API OpenAPI; web imports types from `@2ajar/contracts`; CI drift check.

## M1.5 — Launch

### B-027 ✅ Test coverage gates
AC: API ≥ 90% line+branch coverage, web unit tests ≥ 85% on `lib/` and client components, enforced in CI.

### B-028 ✅ Telegram monitoring
AC: messages for new accounts, listings created/published, leads (masked phone, no message), CSV imports; disabled
without env vars; failures never break requests; untrusted text escaped.

### B-029 ✅ Broker CSV bulk import
AC: template download; dry-run preview with per-row errors; import creates drafts; location by slug/EN/AR name;
≤ 200 rows / 1 MB; authz + rate limit; EN/AR UI.

### B-030 🟡 Deploy to 2ajar.halyoon.com
AC: Railway project with Postgres, bucket, api, web; health checks green; custom domain verified with TLS;
demo mode labeled; go-live switch documented.

### B-031 ✅ Engineering hardening
AC: service/repository layering with DI; publish policy strategy (auto/moderation); domain events + bus; bounded
caches and rate limiter; measured, query-driven indexes (migration 0002); N+1 guard test; ≥ 95% API coverage.

### B-032 ✅ Back office: superuser, users & permissions, tickets, MCP
AC: superuser bootstrapped from env; staff role + named permissions + per-user grants; admin user management
with lock-out guards; floating bug button (signed-in) → tickets with private screenshots, internal notes and
triage; MCP server with personal tokens and permission-checked tools; EN/AR UI; tests ≥ gates; e2e flow.

### B-035 ✅ Plain-text smart search + living factors
AC: home page free-text box (EN/AR/Arabizi) with predefined prompts, no paid API; hard filters in SQL, preferences
rank; reasons with match/miss/unknown and source; reported relaxation; clarification for vague queries; query log;
living factors on listings (electricity, water, sewage, parking, solar, elevator backup, comfort, highlights);
staff-curated area profiles (safety, thefts, noise, garbage, flooding) with admin editor; MCP `ask_search`;
tests ≥ gates; e2e.
Follow-ups: CSV import columns for living factors; grow phrase tables from `search_queries`.

### B-036 ✅ Rentals of any length + Airbnb-style discovery
AC: rentals only (sale rejected, legacy hidden); hourly→yearly periods, stays filter, max guests; chalet areas and demo
chalets/day-use; home category bar and rows (near you, recently added, chalets, by the hour, most viewed, great
value, top-rated neighbourhoods); favorites (heart, Saved page); listing page photo mosaic, sticky contact card,
similar homes nearby; EN/AR; tests ≥ gates; e2e.
Follow-ups: availability calendar / booking requests for short stays; guest reviews once stays exist.

### B-037 ✅ Growth dashboard (admin)
AC: north star + scoreboard vs plan targets; Hormozi value equation for renters and owners computed from data;
funnel; supply gaps from logged searches; wishes vs data coverage; quiet listings; rule-based next steps with
lever/channel/evidence; 90-day playbook checklist (persisted, measured steps auto-tick); Business Model Canvas,
revenue streams and revenue calculator; EN/AR; tests ≥ gates; e2e.

## M2 — Seeker polish
- B-031a ✅ Favorites (done in B-036).
- B-031 ⬜ Email verification & password reset (no paid provider until approved; SMTP via env).
- B-032 ⬜ SEO: metadata, OpenGraph per listing, sitemap.xml of public listings, hreflang ar/en.
- B-033 ⬜ Presigned direct uploads + worker image processing (thumbnails).
- B-034 ⬜ Listing share links with UTM, saved searches.

## M3 — AI search
- B-040 ⬜ `LLMProvider` protocol + Anthropic adapter + FakeProvider. AC: provider/model via env; timeouts; retries; cost/latency recorded.
- B-041 ⬜ Intent extraction schema (Pydantic) AR/EN/Arabizi. AC: eval set ≥ 100 queries, ≥ 90% hard-filter accuracy.
- B-042 ⬜ Location resolver with aliases (e.g. "ashrafieh", "achrafiyeh", "الاشرفية"). AC: deterministic, unit tested.
- B-043 ⬜ Grounded tools (`search_listings`, `get_listing`, `resolve_location`, `create_lead`) running with user principal. AC: tool authorization tests.
- B-044 ⬜ Deterministic ranking + templated match reasons. AC: reasons reference only returned fields.
- B-045 ⬜ Clarification policy. AC: asks at most one question, only when hard constraints missing and results ambiguous.
- B-046 ⬜ Consent-token lead creation from AI flow. AC: model cannot create lead without UI-issued token.
- B-047 ⬜ Prompt-injection suite. AC: malicious listing descriptions cannot change tool calls, reveal system prompt, or create leads.
- B-048 ⬜ AI telemetry table + dashboard query (cost, latency, CTR by rank).
- B-049 ⬜ Web chat-style search UI (AR/EN), fallback to filters when AI disabled.

## M4 — Trust & admin
- B-050 ⬜ Moderation queue (`MODERATION_REQUIRED`), admin approve/reject with reason, audit logged.
- B-051 ⬜ Freshness worker: expire listings past `expires_at`; reminder to publisher 3 days before (channel TBD).
- B-052 ⬜ Duplicate listing heuristic (same location, rooms, area ±5%, price ±10%, image hash).
- B-053 ⬜ Lead status workflow (new/contacted/qualified/closed/spam) and broker notes.
- B-054 ⬜ Organization management (invite agents, remove, transfer listings).
- B-055 ⬜ Report-listing flow for visitors.

## M5 — Analytics
- B-060 ✅ Per-listing stats (visitors, WhatsApp taps, contact requests, saves; 30 days) and a monthly-report card on the dashboard.
- B-062 ✅ Verified badges (agency + owner, staff-set) and public agency pages `/agencies/{slug}`.
- B-061 ✅ Platform funnel metrics for admins (Growth page, with ⓘ explanations of each term).

## M6 — Deploy & monetization
- B-070 ⬜ Railway staging + production provisioning (approval required).
- B-071 ⬜ Shared rate limiter for multi-replica.
- B-072 ⬜ Backups verified + restore drill.
- B-073 ⬜ Subscriptions/payments (blocked on Q1/Q7).
