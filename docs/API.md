# API contract (v1)

Base path: `/api/v1`. JSON only (except media upload: `multipart/form-data`).
The machine-readable contract is FastAPI's OpenAPI at `/api/v1/openapi.json`; TypeScript types are generated
into `packages/contracts/src/schema.d.ts` (`pnpm contracts:gen`).

## Conventions

- **Auth**: cookies `access_token`, `refresh_token` (httpOnly) + `csrf_token` (readable). Mutating cookie-authenticated
  requests must send `X-CSRF-Token: <csrf_token>`. Non-browser clients may send `Authorization: Bearer <access>`.
- **Errors**: `{"error": {"code": "string", "message": "string", "details": any}}` with HTTP status.
  Codes: `validation_error` (422), `unauthorized` (401), `forbidden` (403), `not_found` (404), `conflict` (409),
  `rate_limited` (429).
- **Pagination**: `?page=1&page_size=20` (max 50) → `{"items": [...], "total": n, "page": 1, "page_size": 20}`.
- **Money**: `price_usd` in responses is an integer number of whole USD; stored as cents internally.
- **IDs**: UUID strings. **Timestamps**: ISO-8601 UTC.

## Media

`GET /media/{key}` serves listing photos from storage (local disk or private S3 bucket) with immutable caching.

## Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/healthz` | – | Process liveness |
| GET | `/readyz` | – | DB connectivity |

## Auth

| Method | Path | Auth | Body / Notes |
|---|---|---|---|
| POST | `/auth/register` | – | `{email, password, full_name, phone?, role: seeker\|owner\|broker, organization_name?, locale?}` → `201 User` + cookies. Broker with `organization_name` becomes `agency_admin` of a new org. |
| POST | `/auth/login` | – | `{email, password}` → `User` + cookies. Rate-limited. |
| POST | `/auth/refresh` | refresh cookie | Rotates refresh token. |
| POST | `/auth/logout` | user | Revokes refresh family, clears cookies. |
| GET | `/me` | user | Current user + memberships. |

## Meta

| GET | `/config` | – | `{consent_text_version, demo_mode, max_upload_bytes, max_media_per_listing}` |

## Locations

| GET | `/locations` | – | Flat list `{id, parent_id, level, slug, name_en, name_ar, path}` (cacheable) |

## Listings — public

| Method | Path | Notes |
|---|---|---|
| GET | `/listings` | Filters: `transaction_type`, `location` (slug, includes descendants), `price_min`, `price_max` (USD), `bedrooms_min`, `bathrooms_min`, `furnished`, `property_type`, `sort=newest\|price_asc\|price_desc`, pagination |
| GET | `/listings/{id}` | Published listing detail; owners/admins also see non-published ones |
| POST | `/listings/{id}/contact/whatsapp` | Logs `whatsapp_click`, returns `{url}` (`https://wa.me/<number>?text=...`). Rate-limited. |
| POST | `/listings/{id}/leads` | `{name, phone, email?, message?, consent: true, consent_text_version}` → `201 {id, deduplicated:false}` or `200 {id, deduplicated:true}`. `422` if consent is not the JSON boolean `true` or the consent text version is outdated. Rate-limited. |
| POST | `/listings/{id}/view` | Logs a `view` event (fire-and-forget from client) |

### `ListingPublic`
```json
{
  "id": "uuid", "status": "published", "transaction_type": "rent",
  "price_usd": 1200, "price_period": "monthly",
  "title": {"en": "...", "ar": "..."}, "description": {"en": "...", "ar": "..."},
  "property": {"property_type": "apartment", "bedrooms": 2, "bathrooms": 2, "area_sqm": 140,
               "floor": 4, "furnished": "furnished", "amenities": ["generator_24_7", "parking"]},
  "location": {"slug": "achrafieh", "name_en": "Achrafieh", "name_ar": "الأشرفية", "path": "beirut/beirut-district/achrafieh"},
  "media": [{"id": "uuid", "url": "https://...", "width": 1600, "height": 1200}],
  "publisher": {"type": "broker|owner", "display_name": "...", "organization_name": "...|null"},
  "published_at": "...", "last_confirmed_at": "...", "is_demo": true
}
```
The publisher's WhatsApp number is **not** included; it is only exposed through the tracked handoff endpoint.

## Listings — owner/broker

| Method | Path | Notes |
|---|---|---|
| POST | `/listings` | Create property + listing as `draft`. Role owner/broker/admin. |
| PATCH | `/listings/{id}` | Partial update of listing and property fields. |
| POST | `/listings/{id}/publish` | Validates completeness → `published`, sets `published_at`, `last_confirmed_at`, `expires_at`. |
| POST | `/listings/{id}/pause` | `published → paused`. |
| POST | `/listings/{id}/confirm` | Re-confirm availability (extends `expires_at`). |
| POST | `/listings/{id}/media` | multipart `file`; JPEG/PNG/WebP, ≤ 8 MB, ≤ 20 per listing. |
| DELETE | `/listings/{id}/media/{media_id}` | |
| GET | `/listings/import/template` | CSV template (header + example row). |
| POST | `/listings/import?dry_run=true\|false` | multipart `file` (CSV, UTF-8 or cp1256, ≤ 1 MB, ≤ 200 rows). Rows become drafts. Returns `{dry_run,total,valid,created,rows:[{row,ok,listing_id,title,errors}]}`. |
| GET | `/me/listings` | Own listings; agency admins get all org listings. |
| GET | `/me/leads` | Leads for listings the user may manage. Filter `listing_id`. |

All of these return **404** for resources the caller cannot manage.

## Rentals only, any length

2ajar lists rentals only: `transaction_type` defaults to `rent` and `sale` is rejected (422); legacy sale listings
are never public. `price_period` is `hourly | daily | nightly | weekly | monthly | yearly`, grouped into stays:
`hours` (hourly, daily), `nights` (nightly, weekly), `months` (monthly, yearly). `GET /listings` accepts
`stay` and `guests_min` (matches `property.max_guests`).

## Discovery and favorites

| Method | Path | Notes |
|---|---|---|
| GET | `/discover` | Home rows: `recent`, `nights`, `hours`, `most_viewed[{listing, visitors_30d}]` (distinct visitors, 30 days), `great_value[{listing, below_area_median_pct}]` (≥15% under the area median price per m² among ≥3 monthly homes), `top_areas[{area, listing_count}]` (staff safety + quiet scores). Empty rows mean "nothing honest to show". |
| GET | `/discover` → `by_area` | Up to 4 rows "Popular homes in X" / "Places to stay in X" (`kind`: `stays` when most homes there are rented by the night or hour) for places with ≥ 3 public homes, busiest first, with the parent district as subtitle. |
| GET | `/listings/nearby?lat&lng&stay?&limit?` | Closest public rentals within 40 km → `[{listing, distance_km}]`. Coordinates are not stored. Rate-limited. |
| GET | `/listings/{id}/similar` | Nearest public rentals for the same kind of stay (404 if not public). |
| GET | `/me/favorites`, `/me/favorites/ids` | Saved listings that are still public, newest save first. |
| PUT / DELETE | `/me/favorites/{listing_id}` | Idempotent save / remove (`204`). Only public listings can be saved. |

## Smart search (plain text, rule-based, no LLM)

| Method | Path | Notes |
|---|---|---|
| POST | `/search/ask` | `{query (1–300 chars), locale: en\|ar}` → `AskResponse`: `understood` (parsed filters + preferences), `summary_en/ar`, `clarification_en/ar`, `relaxed[]`, `results[{listing, score, reasons[]}]`, `total`, `query_id`. Rate-limited (60 / 10 min). Logged in `search_queries`. |
| GET | `/search/suggestions` | Predefined EN/AR example prompts (cacheable). |

Each reason is `{key, label_en, label_ar, status: match\|miss\|unknown, source: filter\|listing\|area}`. Hard
constraints are SQL filters; preferences only rank. `unknown` means the data was not reported. If nothing matches,
budget (+20%), area (parent) and bedrooms (−1) are relaxed in that order and listed in `relaxed`.

Listing payloads carry `property.living` (publisher-reported electricity, water, sewage, parking, solar-ready,
elevator backup, winter/summer comfort, highlights, things to know) and, on detail and search results, `area`
(staff-curated profile of the listing's area or its nearest ancestor). Demo area profiles are only returned when
`DEMO_MODE=true`.

## Tickets (signed-in users)

| Method | Path | Notes |
|---|---|---|
| POST | `/tickets` | `{category: bug\|feedback\|question, title, description, page_url?, context?}` → `201 Ticket`. Rate-limited. |
| GET | `/me/tickets` | My tickets, newest first. |
| GET | `/tickets/{id}` | Reporter or `tickets.read`; internal notes only for staff; otherwise 404. |
| POST | `/tickets/{id}/comments` | `{body, is_internal?}`. A reporter reply reopens a resolved ticket. Internal notes need `tickets.manage`. |
| POST / GET | `/tickets/{id}/attachment` | Upload (image, re-encoded) / fetch the private screenshot (`Cache-Control: private, no-store`). |

## API tokens (`mcp.access`)

`GET/POST /me/api-tokens`, `DELETE /me/api-tokens/{id}`. The raw token is returned once at creation.

## Admin (permission per route)

| Method | Path | Permission |
|---|---|---|
| GET | `/admin/users?q=&role=&is_active=&page=` | `users.read` |
| GET | `/admin/users/{id}` | `users.read` |
| PATCH | `/admin/users/{id}` `{role?, is_active?, extra_permissions?, full_name?}` | `users.manage` |
| GET | `/admin/permissions` | `users.read` |
| GET | `/admin/tickets?status=&priority=&q=&assignee_id=` | `tickets.read` |
| PATCH | `/admin/tickets/{id}` `{status?, priority?, category?, assignee_user_id?}` | `tickets.manage` |
| GET | `/admin/stats` | `analytics.read` |
| GET | `/admin/areas` | `areas.manage` |
| PUT | `/admin/areas/{location_id}` `{safety_score?, quiet_score?, theft_reports_12m?, noise_notes_en/ar?, garbage_collection?, flood_risk?, summary_en/ar?, source_note?}` (replaces; audit logged) | `areas.manage` |

## MCP

`POST /mcp` — Model Context Protocol (Streamable HTTP, stateless JSON). Bearer API token required. See DEPLOYMENT.md.

## Planned (later milestones)

- `POST /ai/search` (M3): `{query, conversation_id?, locale}` → `{intent, clarification?, results:[{listing, reasons[]}]}`
- `POST /ai/consent-token` (M3): issued after explicit user click; required by the AI `create_lead` tool.
- `GET/POST/DELETE /me/favorites` (M2)
- `/admin/listings?status=pending_review`, `/admin/listings/{id}/approve|reject`, `/admin/analytics` (M4/M5)
