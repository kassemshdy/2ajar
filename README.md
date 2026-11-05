# 2ajar (إيجار)

AI-first, trust-focused real-estate marketplace for Lebanon — residential rentals in Beirut and Mount Lebanon first.

> Status: **Milestone 1 (vertical slice)** — register → create listing → browse → contact (WhatsApp / consented lead).
> AI search is Milestone 3. Nothing is deployed yet; see `docs/DEPLOYMENT.md`.

## Repository

| Path | What |
|---|---|
| `apps/api` | FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · Alembic · PostgreSQL |
| `apps/web` | Next.js 15 App Router · Tailwind v4 · next-intl (Arabic RTL / English) |
| `apps/worker` | Scheduled jobs (freshness report) sharing the API models |
| `packages/contracts` | TypeScript types generated from the API OpenAPI schema |
| `tests/e2e` | Playwright smoke + vertical-slice tests (desktop & mobile) |
| `infra` | Dockerfiles, docker-compose for local Postgres |
| `docs` | PRD, architecture, ERD, API, roadmap, decisions, deployment plan, backlog |

## Local development

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22, pnpm 10, PostgreSQL 16
(`docker compose -f infra/docker-compose.yml up -d` creates `ajar_dev` and `ajar_test`).

```bash
# API
cd apps/api
cp .env.example .env            # DEMO_MODE=true shows synthetic listings locally
uv sync
uv run alembic upgrade head
uv run python -m app.seed       # Lebanese locations + 30 listings flagged is_demo
uv run uvicorn app.main:app --reload --port 8000

# Web (another terminal, from repo root)
pnpm install
pnpm dev:web                    # http://localhost:3000 (proxies /api/v1 and /media to :8000)
```

Set `SEED_DEMO_PASSWORD` before seeding if you want to log in as a demo broker
(e.g. `rami.broker@demo.2ajar.invalid`); otherwise demo accounts get unusable random passwords.

## Checks

```bash
cd apps/api && uv run ruff check . && uv run mypy app && uv run pytest -q   # needs ajar_test DB
pnpm lint && pnpm typecheck && pnpm build
pnpm contracts:gen                                   # regenerate API types (CI fails on drift)
pnpm e2e                                             # needs API (DEMO_MODE=true) + web running
```

## Key rules

- Demo data is always `is_demo=true` and hidden unless `DEMO_MODE=true`; the API refuses to start with demo mode in production.
- Publisher phone numbers are never in public listing payloads; WhatsApp goes through a tracked, rate-limited endpoint.
- Leads require an explicit `consent: true` and are deduplicated per listing + phone for 24h.
- Unauthorized access to private resources returns 404.

See `docs/` for the full design and `docs/DECISIONS.md` for open business questions.
