# Database

PostgreSQL 16. All primary keys are UUID (generated in the app, `uuid4`), all timestamps `timestamptz` in UTC.
Schema changes only through Alembic migrations in `apps/api/migrations`. Migrations follow
**expand → migrate → contract** so a previous API release keeps working during rollback.

## Principles

- **Property vs. listing**: `properties` describe the physical unit (location, rooms, area). `listings` are
  advertisements of a property (transaction type, price, status, publisher, text). One property can have
  several listings over time (rent now, sale later; re-listed next year) and moderation acts on listings.
- **Tenancy**: `listings.organization_id` (nullable for individual owners) scopes broker data.
- **Demo data**: `is_demo` boolean on users, organizations, properties, listings.
- **No vector store** in MVP; AI search uses structured filters. Revisit with `pgvector` only when
  evaluation shows semantic recall problems (ADR-005).
- **Geo**: `lat/lng numeric(9,6)`; PostGIS optional later (ADR-004).

## ERD

Tables marked *(M1)* are created in the first migration; others are designed and added in their milestone.

```mermaid
erDiagram
  users ||--o{ organization_members : "belongs"
  organizations ||--o{ organization_members : "has"
  users ||--o{ refresh_tokens : "has"
  users ||--o{ properties : "owns"
  organizations ||--o{ properties : "manages"
  locations ||--o{ locations : "parent"
  locations ||--o{ properties : "located in"
  properties ||--o{ listings : "advertised by"
  users ||--o{ listings : "created"
  organizations ||--o{ listings : "scoped to"
  listings ||--o{ listing_media : "has"
  listings ||--o{ leads : "receives"
  listings ||--o{ listing_events : "tracks"
  users ||--o{ leads : "submits (optional)"
  users ||--o{ favorites : "saves"
  listings ||--o{ favorites : "saved"
  leads ||--o| conversations : "may open"
  conversations ||--o{ messages : "contains"
  organizations ||--o{ subscriptions : "pays"
  users ||--o{ subscriptions : "pays (owner)"
  subscriptions ||--o{ payments : "billed"
  users ||--o{ audit_logs : "acts"

  users {
    uuid id PK
    text email UK "lowercased"
    text phone_e164
    text password_hash
    text full_name
    enum role "seeker|owner|broker|platform_admin"
    text locale "en|ar"
    bool is_active
    bool is_demo
    timestamptz created_at
    timestamptz updated_at
  }
  organizations {
    uuid id PK
    text name
    text slug UK
    text phone_e164
    bool is_verified
    bool is_demo
  }
  organization_members {
    uuid id PK
    uuid organization_id FK
    uuid user_id FK
    enum role "agency_admin|agent"
  }
  refresh_tokens {
    uuid id PK
    uuid user_id FK
    uuid family_id
    text token_hash UK
    timestamptz expires_at
    timestamptz revoked_at
  }
  locations {
    uuid id PK
    uuid parent_id FK
    enum level "governorate|district|area"
    text slug UK
    text name_en
    text name_ar
    text path "slash-joined ancestor slugs"
    numeric lat
    numeric lng
  }
  properties {
    uuid id PK
    uuid owner_user_id FK
    uuid organization_id FK
    uuid location_id FK
    enum property_type "apartment|studio|duplex|house|villa|chalet|office|shop|land"
    int bedrooms
    int bathrooms
    int area_sqm
    int floor
    enum furnished "unfurnished|semi|furnished"
    jsonb amenities "string[]"
    numeric lat
    numeric lng
    bool is_demo
  }
  listings {
    uuid id PK
    uuid property_id FK
    uuid created_by_user_id FK
    uuid organization_id FK
    enum transaction_type "rent|sale"
    bigint price_usd_cents
    enum price_period "monthly|yearly|total"
    enum status "draft|pending_review|published|paused|archived|rejected"
    text title_en
    text title_ar
    text description_en
    text description_ar
    text contact_whatsapp_e164
    timestamptz published_at
    timestamptz last_confirmed_at
    timestamptz expires_at
    bool is_demo
  }
  listing_media {
    uuid id PK
    uuid listing_id FK
    text storage_key
    text content_type
    int width
    int height
    int byte_size
    int position
  }
  leads {
    uuid id PK
    uuid listing_id FK
    uuid seeker_user_id FK
    text name
    text phone_e164
    text email
    text message
    enum source "web|whatsapp|ai"
    enum status "new|contacted|qualified|closed|spam"
    timestamptz consent_at
    text consent_text_version
    int duplicate_count
    timestamptz last_contact_at
  }
  listing_events {
    uuid id PK
    uuid listing_id FK
    enum event_type "view|whatsapp_click|lead|favorite|share"
    uuid user_id
    text session_hash
    timestamptz created_at
  }
  audit_logs {
    uuid id PK
    uuid actor_user_id FK
    text action
    text resource_type
    uuid resource_id
    jsonb data
    text ip_hash
  }
  favorites {
    uuid user_id PK
    uuid listing_id PK
  }
  conversations {
    uuid id PK
    uuid lead_id FK
    uuid listing_id FK
  }
  messages {
    uuid id PK
    uuid conversation_id FK
    uuid sender_user_id FK
    text body
  }
  subscriptions {
    uuid id PK
    uuid organization_id FK
    uuid user_id FK
    text plan
    enum status "trialing|active|past_due|canceled"
    timestamptz current_period_end
  }
  payments {
    uuid id PK
    uuid subscription_id FK
    bigint amount_usd_cents
    text provider
    text provider_ref
    enum status "pending|succeeded|failed|refunded"
  }
```

## Milestone mapping

| Table | Milestone |
|---|---|
| users, organizations, organization_members, refresh_tokens, locations, properties, listings, listing_media, leads, listing_events, audit_logs | M1 |
| favorites | M2 |
| ai_requests (telemetry) | M3 |
| conversations, messages | M4 (optional; WhatsApp is primary) |
| subscriptions, payments | M6 (pending monetization decision) |

## Indexes (M1)

- `users(email)` unique (stored lowercased)
- `locations(parent_id)`, `locations(path text_pattern_ops)` for descendant `LIKE 'beirut/%'`
- `properties(location_id)`, `properties(bedrooms)`
- `listings(status, transaction_type, published_at desc)` — main public query
- `listings(price_usd_cents)`, `listings(created_by_user_id)`, `listings(organization_id)`, `listings(expires_at)`
- `listing_media(listing_id, position)`
- `leads(listing_id, created_at)`, `leads(listing_id, phone_e164, created_at)` (dedupe lookup)
- `listing_events(listing_id, event_type, created_at)`
- `audit_logs(resource_type, resource_id)`

## Lead deduplication

Within a transaction the API takes `pg_advisory_xact_lock(hash('lead:' || listing_id || ':' || phone_e164))`,
then looks for a lead for the same listing and normalized phone created in the last 24 hours. If found it increments
`duplicate_count`, updates `last_contact_at`, appends the new message, and returns the existing lead (HTTP 200 instead
of 201). The advisory lock makes concurrent duplicate submissions race-free without a unique constraint.

## Demo data

`apps/api/app/seed.py` inserts Lebanese locations (real geography, public knowledge) and ~30 synthetic listings with
`is_demo = true`, placeholder publisher accounts `*@demo.2ajar.invalid`, and fake phone numbers in the `+961 70 000 xxx`
range. The production configuration refuses to run the seed (`ENV=production` guard) and public endpoints hide
`is_demo` rows unless `DEMO_MODE=true`.

## Backups

Railway Postgres: enable scheduled backups (daily, 7-day retention minimum) plus a manual `pg_dump` before every
migration that drops or rewrites data. See DEPLOYMENT.md.
