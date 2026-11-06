# Roadmap

| Milestone | Scope | Exit criteria |
|---|---|---|
| **M0 — Foundations** | Docs, monorepo scaffold, CI skeleton | Docs merged; CI runs lint + tests on PR |
| **M1 — Vertical slice** | Register, create/edit/publish/pause listing, image upload, public search & detail, WhatsApp handoff, consented lead capture with dedupe, broker dashboard (basic), AR/EN RTL UI, demo seed | pytest + Playwright smoke green; migrations up/down clean; mobile + RTL verified |
| **M2 — Seeker polish** | Favorites, saved searches (no notifications yet), SEO metadata/sitemap, listing share, image presigned uploads | Lighthouse mobile ≥ 85 perf on listing page |
| **M3 — AI search** | LLMProvider abstraction (Anthropic + Fake), intent extraction, location resolver (AR/EN/Arabizi aliases), grounded tools, deterministic ranking + reasons, consent-token lead tool, telemetry, injection test suite, eval set (≥ 100 queries) | Eval: ≥ 90% correct hard-filter extraction; 0 fabricated facts; injection tests pass |
| **M4 — Trust & admin** | Moderation queue (`pending_review`), admin dashboard, freshness worker (expire, reminders), duplicate listing detection (heuristic), broker verification flag, lead status workflow | Admin can approve/reject; stale listings auto-expire |
| **M5 — Analytics** | Listing/broker analytics (views, clicks, leads, CTR), AI cost/latency dashboard, funnel metrics | Broker sees per-listing stats |
| **M6 — Deploy & monetization** | Railway production deploy, backups verified, rollback rehearsal, subscriptions/payments (after business decision) | Staging + prod live; restore drill done |

Sales listings are supported in the model, API and rent/sale filter from M1; go-to-market focuses on
rentals until the business decides when to launch sales (see PRD open questions).
