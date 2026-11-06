# 2ajar — Product Requirements Document (MVP)

Status: Draft v0.1 · Owner: Product/Eng · Last updated: 2026-11-05

## 1. Problem

Finding a rental in Lebanon is slow and low-trust. Inventory is scattered across Facebook groups, WhatsApp
broadcasts, Instagram pages and generic classifieds. Listings are frequently stale (already rented), duplicated
by multiple brokers, priced inconsistently (fresh USD vs. "lollar" vs. LBP), and missing basic facts
(exact area, electricity/generator hours, water, parking). Brokers in turn receive many low-intent messages
and have no structured way to qualify or track them.

## 2. Product vision

2ajar (إيجار — "rent") is a **trusted property-discovery and qualified-lead platform** for Lebanon.
It is not a classifieds clone: every listing has a verified publisher, a freshness signal, and structured
facts that make AI-assisted search reliable. Seekers describe what they want in Arabic or English; the
system retrieves *real* listings with deterministic filters and explains why each one matches.

## 3. Initial market

- **Transaction**: residential **rentals** first; data model supports **sales** from day one, hidden behind a flag.
- **Geography**: Beirut and surroundings (Metn, Baabda, Keserwan coastal). Model supports all Lebanese governorates.
- **Currency**: USD (fresh dollars). Prices stored as integer USD cents.
- **Languages**: Arabic (RTL) and English (LTR). Lebanese Arabic and "Arabizi" queries must be tolerated by AI search.

## 4. Personas & roles

| Role | Description | Key needs |
|---|---|---|
| Visitor | Anonymous browser | Search, view listings, contact via WhatsApp |
| Seeker | Registered renter/buyer | Save favorites, AI search history, submit leads |
| Owner | Individual landlord | List 1–5 properties, receive leads, pause when rented |
| Broker | Independent or agency agent | Many listings, lead dashboard, WhatsApp handoff |
| Agency admin | Manages an organization | Manage agents, see all org listings & leads |
| Platform admin | 2ajar staff | Moderation, freshness, abuse handling, analytics |

## 5. MVP features

| # | Feature | Milestone |
|---|---|---|
| 1 | Public search and listing details | M1 |
| 2 | Rent/sale filters, USD pricing, Lebanese location hierarchy | M1 |
| 3 | Owner and broker registration (broker may create an agency) | M1 |
| 4 | Create / edit / publish / pause listings | M1 |
| 5 | Secure image uploads (type sniffing, size limits, EXIF strip) | M1 |
| 6 | Broker listing and lead dashboard | M1 (basic) → M4 |
| 7 | WhatsApp contact handoff (tracked click → `wa.me`) | M1 |
| 8 | AI-assisted natural-language search (AR/EN) with grounded tools | M3 |
| 9 | Lead capture with explicit consent + deduplication | M1 |
| 10 | Listing moderation and freshness checks | M4 |
| 11 | Basic analytics (views, WhatsApp clicks, leads, AI quality) | M5 |
| 12 | Responsive RTL and LTR UI | M1 |

## 6. Key user flows (M1)

1. **Broker onboarding**: register (email, phone, password, role=broker, optional agency name) → dashboard.
2. **Create listing**: choose location, type, bedrooms, bathrooms, area, furnished, amenities, price & period,
   titles/descriptions (EN and/or AR), WhatsApp number → upload photos → publish.
3. **Browse**: visitor filters by rent/sale, area, price range, bedrooms, furnished → listing detail.
4. **Contact**: "Chat on WhatsApp" (event logged, opens `wa.me` with prefilled reference) **or** lead form
   (name, phone, optional message, mandatory consent checkbox) → lead visible in broker dashboard.

## 7. Trust & quality requirements

- Listings expire after a configurable period (default 30 days) unless the publisher re-confirms availability.
- Demo/synthetic data is flagged `is_demo` and never shown as genuine inventory in production.
- The AI never invents listing facts; it only presents fields returned by backend tools.
- Leads are only created with explicit consent; consent text version and timestamp are stored.
- Phone numbers are normalized to E.164 (default region LB); duplicate leads within 24h are merged.

## 8. Success metrics (first 90 days post-launch)

- Active published, fresh listings in Beirut: ≥ 500
- Share of listings confirmed fresh in last 30 days: ≥ 80%
- Visitor → contact (WhatsApp click or lead) conversion: ≥ 4%
- Broker-reported lead quality (thumbs up): ≥ 60%
- AI search: ≥ 70% of sessions return ≥ 1 result clicked; 0 hallucinated facts in sampled audits
- p95 search API latency < 300 ms (non-AI), < 4 s (AI end-to-end)

## 9. Out of scope (MVP)

In-app payments to landlords, rental contracts / e-signature, mortgage, virtual tours, native mobile apps,
in-app chat with read receipts (conversations table is planned, WhatsApp is the primary channel), LBP pricing.

## 10. Open business questions (need product owner decision — not blocking M1)

1. **Monetization**: broker subscriptions vs. pay-per-lead vs. featured listings? (affects `subscriptions`, `payments`)
2. **Broker verification**: what proof is required (syndicate membership, ID, commercial registration)?
3. **Owner listing limits**: free cap for individual owners (proposed: 3 active listings)?
4. **Commission display**: must listings disclose broker commission (commonly one month's rent)?
5. **LBP / "lollar"**: show only fresh USD, or allow other price denominations?
6. **Sales launch**: timing and whether sales need additional verification (title deed, etc.).
7. **Payment provider** for subscriptions in Lebanon (card acquiring is limited; OMT/Whish/manual invoicing?).
8. **Data retention** for leads and messages (proposed: 12 months, then anonymize).
