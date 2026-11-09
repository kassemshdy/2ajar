# Decisions (ADRs) and open questions

Format: context → decision → consequences. Status: Accepted unless noted.

## ADR-001 Monorepo with pnpm workspaces + uv
Web/contracts are a pnpm workspace; Python apps use uv with `pyproject.toml`. The worker depends on the API
package (path dependency) to share models. *Consequence*: one repo, two toolchains; CI caches both.

## ADR-002 Self-hosted auth (argon2id + JWT access + rotating refresh)
No paid identity vendor. Cookies are httpOnly/SameSite=Lax with CSRF double-submit for mutations.
*Consequence*: we own password reset / email verification (M2). Social login deferred.

## ADR-003 Integer USD cents
`price_usd_cents BIGINT`. API exposes whole dollars. LBP and "lollar" prices are not supported (open question Q5).

## ADR-004 PostGIS deferred
Railway's standard Postgres image may not ship PostGIS; the local dev cluster doesn't either. M1 uses a
location hierarchy plus `lat/lng` numeric columns. Radius search ("within 2 km of AUB") is added later by enabling
PostGIS (or an earthdistance/cube fallback) in a dedicated migration.

## ADR-005 No vector database in MVP
AI search = LLM intent extraction → deterministic SQL filters → deterministic ranking. Add `pgvector` only if the
eval set shows recall gaps that structured fields can't close.

## ADR-006 Listings separate from properties
A property is the physical unit; a listing is an advertisement with its own lifecycle and moderation state.

## ADR-007 In-process rate limiter
Single API replica in MVP, so an in-memory sliding window is sufficient. Must be replaced by a shared store
(Postgres table or Redis) before running > 1 replica. Tracked in BACKLOG (M6).

## ADR-008 Uploads proxied through API in M1
Simpler validation (Pillow sniffing, re-encode to WebP, EXIF strip) at the cost of API bandwidth. Presigned direct
uploads + async processing in worker planned for M2.

## ADR-009 Auto-publish in M1, moderation in M4
Publishing goes straight to `published` after completeness validation. `pending_review` exists in the enum so
M4 can switch the flow behind a setting (`MODERATION_REQUIRED=true`) without a schema change.

## ADR-010 Private-resource authorization failures return 404
Prevents listing/lead ID enumeration.

## ADR-011 WhatsApp handoff via tracked endpoint
Publisher numbers are not embedded in public listing payloads; the client calls `POST /listings/{id}/contact/whatsapp`
to get the `wa.me` link. Deters bulk scraping and lets us measure contact intent. (Determined scrapers can still
call the endpoint; it is rate-limited.)

## ADR-012 LLM provider abstraction, Anthropic first
`LLMProvider` protocol with an Anthropic adapter and a deterministic `FakeProvider`. Using a paid model API requires
owner approval and an API key in env (`LLM_PROVIDER`, `ANTHROPIC_API_KEY`); without it, AI search is disabled and
the UI falls back to filter search.

## ADR-013 Sync vs async SQLAlchemy
Async SQLAlchemy with psycopg 3. Tests run against a real Postgres (no SQLite) to match production behaviour.

## ADR-014 In-process caching for reference data only
Locations and public config are read on most requests and change only on deploy. They are cached in-process
(`TTLCache`, LRU-bounded, single-flight) and via HTTP `Cache-Control`. No Redis yet: one replica, and a cache miss
costs one tiny query. User-specific and authorization data is never cached. *Consequence*: with N replicas each
holds its own copy, which is acceptable for read-only reference data.

## ADR-015 Domain events on an in-process bus
Services record immutable events after commit; subscribers (Telegram now; analytics or e-mail later) react in
background tasks. *Consequence*: delivery is best-effort and not durable. If a notification must never be lost,
introduce an outbox table drained by the worker.

## ADR-016 Service layer with repositories and constructor injection
Routes are adapters, services hold use cases and authorization, repositories own SQL, and dependencies are wired
in `app/api/providers.py`. *Consequence*: slightly more files, but HTTP, CSV import and the future AI tools share
one implementation of every rule, and services are testable without HTTP.

## ADR-017 Index changes are evidence-based
Every index must be justified by an `EXPLAIN ANALYZE` on realistic volume (see DATABASE.md). Superseded indexes
are dropped, because each extra index slows writes and wastes cache.

## ADR-018 RBAC = roles + named permissions + per-user grants
Roles alone forced new roles for every combination (e.g. "a broker who helps with support"), while full ACLs
were overkill. Roles map to named permissions; admins add individual grants. `users.manage` is role-only, so a
grant can never escalate someone to admin.

## ADR-019 MCP server inside the API, authenticated by personal tokens
The MCP server runs in the API process and reuses its services, so there is one set of rules and no second
deployment. Personal tokens (hashed, expiring, revocable) act as their owner with the owner's *current*
permissions. We did not use OAuth for MCP yet: it adds an authorization server for a handful of staff users.
Writes are limited to ticket comments and status; there is no SQL access and no deletes.

## ADR-020 Superuser from environment variables
The bootstrap admin is declared in env (`SUPERUSER_EMAIL/PASSWORD`) and re-asserted on every deploy, so access
can always be recovered by changing a variable, with no shell into the container.

## ADR-021 Plain-text search is rule-based first
The home page answers free-text requests in Arabic, English and Arabizi without any LLM or paid API: a
normalising parser (Arabic letter folding, proclitics such as بال/وال, Arabic digits, "1.2k") extracts hard filters
and preference keywords from curated phrase tables; SQL applies the filters; a deterministic score ranks by
preferences; reasons are generated only from stored fields with match / miss / unknown. *Consequence*: answers are
explainable, free and fast, but phrasing outside the tables is missed. Queries are logged (`search_queries`) to
grow the tables; ADR-012's LLM intent extraction can later replace the parser behind the same response schema.

## ADR-022 Area facts are staff-curated, dated and sourced
Safety, theft reports, noise, garbage collection and flood risk are per-area facts, not per-listing claims, so
they live in `area_profiles`, editable by `areas.manage`, inherited by child areas, shown with an update date and
a source note, and labelled as coming from the 2ajar team. Demo profiles are synthetic, marked `[DEMO]`, hidden
unless `DEMO_MODE=true`, and purged with demo data.

## ADR-023 Rentals of any length, nothing for sale
2ajar rents places from an hour (day-use chalets, pools, rooms) to years. Sale listings are rejected and legacy ones
hidden; enums keep `sale`/`total` so no data is destroyed (expand-only migrations). Search groups periods into
three stays (hours / nights / months) because people ask "for the weekend", not "nightly or weekly". There are no
bookings or calendars yet: contact still goes through WhatsApp or a consented lead.

## ADR-024 Discovery rows only show what the data supports
Airbnb-style rows are honest by construction: "most viewed" counts distinct daily visitor hashes, "great value"
needs at least three comparable homes in the same area, "top-rated neighbourhoods" uses the staff-curated scores
(2ajar has no stays, so no guest ratings are shown or invented), and an empty row is hidden rather than padded.
"Near you" asks for location only on click and never stores it.

## ADR-025 Airbnb-like UI, 2ajar's own brand
The interface follows Airbnb's patterns (ar.airbnb.com): slim header with a ☰ + avatar menu, a "Where · When · Who"
pill, icon categories, rows per place, square two-line cards with a heart, phone tab bar, light link footer, and
neutral greys (#222 / #6a6a6a / #ddd). Airbnb Cereal is proprietary, so we self-host free lookalikes (Nunito Sans,
IBM Plex Sans Arabic) via next/font. The logo and the teal accent stay 2ajar's own: we copy patterns, not the brand.
2ajar is mainly monthly apartment rentals, so apartments lead (categories, area rows); chalets and hourly come after.
No availability calendar for now (owner decision).

## ADR-026 Growth dashboard measures, never estimates
Admin → Growth applies Alex Hormozi's value equation (dream × likelihood ÷ time × effort) and the growth plan to
2ajar's own data: listings, visits (distinct daily visitor hashes), WhatsApp taps, consented leads and logged
smart searches. Each factor maps to a stated, measurable proxy; when data is missing the API returns null and
the UI says "not enough data yet". Recommendations are explicit rules over those numbers (thresholds in
`app/services/growth.py`), so every suggestion can be traced to its evidence. Playbook ticks are stored; measured
steps tick themselves. The business-model section (canvas, revenue streams, calculator) is guidance: pricing
stays an owner decision (Q1, Q7) and calculator outputs are labelled as assumptions.

## ADR-027 Verified badges, agency pages and a monthly report for publishers
Brokers are the supply side, so they get three things that make 2ajar worth their time: a **verified badge**
(agency `organizations.is_verified`, private owner `users.is_verified`, migration 0007), a **public agency page**
(`/{locale}/agencies/{slug}`) they can share on WhatsApp/Instagram, and a **monthly report** on their dashboard
(visitors, WhatsApp taps, contact requests, saves per listing over 30 days). Badges are set only by staff after an
off-platform identity check (Q2); there is no self-serve verification. Stats reuse `listing_events` (distinct
visitor hashes, so reloads don't inflate numbers). Admin growth terms (Hormozi vocabulary) each have an ⓘ
explanation in EN/AR so the team can act on the dashboard without the book.

---

## Assumptions

- Fresh USD is the market's de-facto rental currency.
- WhatsApp is the dominant contact channel; in-app chat is not needed for MVP.
- Most Beirut brokers list 5–100 units; agencies have < 20 agents.
- Phone numbers default to region `LB` when no country code is given.
- Listing freshness window: 30 days (configurable `LISTING_TTL_DAYS`).
- Demo locations use real Lebanese place names (public geography); all listings, people, and numbers are synthetic.

## Open business decisions (owner input needed; none block M1)

| # | Question | Default until decided |
|---|---|---|
| Q1 | Monetization model (subscription / per-lead / featured) | Free during beta |
| Q2 | Broker verification requirements | Staff set the agency / owner badge in the back office after checking registration, office and phone |
| Q3 | Free listing cap for individual owners | No cap (soft-limit later) |
| Q4 | Must broker commission be disclosed? | Optional free-text in description |
| Q5 | Non-USD pricing | USD only |
| Q6 | When to launch sales | Supported, not marketed |
| Q7 | Payment provider in Lebanon | Not integrated |
| Q8 | Lead data retention | 12 months then anonymize (to implement M4) |
| Q9 | Production domain & brand assets | `2ajar` working name |
| Q10 | Object storage vendor (Railway bucket vs Cloudflare R2 vs AWS S3) | S3-compatible adapter; vendor chosen at deploy |
