# Railway deployment plan

> Status: **plan only**. No Railway project has been created or modified. Provisioning requires explicit owner
> approval and authorized credentials. Destructive operations (deleting services/volumes, restoring backups over
> production) always require a human approval step.

## Services

| Service | Source | Start command | Health check |
|---|---|---|---|
| `web` | `apps/web` (Dockerfile `infra/docker/web.Dockerfile`) | `node server.js` (Next standalone) | `GET /api/health` |
| `api` | `apps/api` (Dockerfile `infra/docker/api.Dockerfile`) | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers` | `GET /healthz` |
| `worker` (optional) | `apps/worker` | Railway cron: `python -m worker.jobs expire_listings` hourly | exit code |
| `postgres` | Railway PostgreSQL plugin | – | managed |
| Object storage | Railway bucket or external S3-compatible (decision Q10) | – | – |

Config-as-code: `apps/api/railway.json`, `apps/web/railway.json` (builder = DOCKERFILE, healthcheckPath, restart policy).

## Environments

`staging` (auto-deploy from `main`) and `production` (deploy by promoting a staging image / manual trigger).
Demo data allowed **only** in staging (`DEMO_MODE=true`). Production sets `ENV=production`, which makes the API
refuse to start if `DEMO_MODE=true` and makes the seed script exit.

## Environment variables

| Var | Service | Notes |
|---|---|---|
| `DATABASE_URL` | api, worker | Reference `${{Postgres.DATABASE_URL}}`; app converts to `postgresql+psycopg://` |
| `ENV` | api, worker | `development` / `staging` / `production` |
| `JWT_SECRET` | api | ≥ 32 random bytes, Railway secret |
| `CORS_ORIGINS` | api | web origin(s) |
| `COOKIE_DOMAIN`, `COOKIE_SECURE` | api | `COOKIE_SECURE=true` outside dev |
| `PUBLIC_API_BASE_URL` | api | used to build media URLs |
| `STORAGE_BACKEND` | api | `local` / `s3` |
| `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_PUBLIC_BASE_URL` | api | secrets |
| `DEMO_MODE` | api | `false` in production |
| `LISTING_TTL_DAYS` | api, worker | default 30 |
| `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `LLM_MODEL` | api | M3; unset = AI disabled |
| `NEXT_PUBLIC_API_URL` | web | public API URL (browser) |
| `API_INTERNAL_URL` | web | private network URL `http://api.railway.internal:$PORT` for SSR |

No secrets are committed. `.env.example` files list variable names with dummy values only.

## Migrations

`api` service **pre-deploy command**: `alembic upgrade head`. The deploy fails (and old version keeps serving)
if migration fails. All migrations must be backward compatible with the previous release (expand/contract):
add nullable columns → backfill → enforce constraints in a later release; never rename/drop in the same release
that stops using a column.

## Logging & monitoring

JSON logs to stdout → Railway log explorer. Request id propagated via `X-Request-ID`. Alerts: Railway
deployment-failure notifications; uptime check on `/readyz` (free tier of any uptime monitor — requires approval).

## Backups

- Enable Railway Postgres scheduled backups (daily; retain ≥ 7 days) — verify available on the plan.
- Before risky migrations: manual `pg_dump --format=custom` stored in the object bucket (private prefix).
- Quarterly restore drill into a scratch database.

## Release & rollback

1. CI green on `main` (lint, typecheck, pytest, migrations up/down, Playwright).
2. Auto-deploy to staging; smoke test (`/readyz`, search page, create listing on staging).
3. Promote to production.
4. **Rollback**: redeploy the previous successful deployment in Railway (one click / `railway redeploy`).
   Because migrations are expand-only per release, the previous API works with the new schema. If a migration
   must be reverted, run `alembic downgrade -1` only after confirming the downgrade is non-destructive; otherwise
   restore from backup (requires approval).

## Database diagnostics

If a PostgreSQL MCP server is connected for diagnostics, it must use a **read-only** role:
```sql
CREATE ROLE diag_ro LOGIN PASSWORD '<secret>';
GRANT CONNECT ON DATABASE railway TO diag_ro;
GRANT USAGE ON SCHEMA public TO diag_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO diag_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO diag_ro;
ALTER ROLE diag_ro SET default_transaction_read_only = on;
```
