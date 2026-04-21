# ATLAS — Project Memory

> **Read this file at the start of every new session before making changes.** If a decision or phase isn't here but exists in the codebase, add it. If something gets deferred or a new gotcha is discovered, update the relevant section in the same commit. This file is the single source of truth — treat it like a migration log for intent, not just code.

---

## 1. Project status snapshot

ATLAS is an emerging-markets sovereign-finance intelligence platform covering 10 African countries (ETH, GHA, KEN, NGA, CIV, SEN, RWA, ZAF, MAR, EGY). The country intelligence page has been redesigned from a flat layout into a tabbed analyst workstation with a global FX ticker, redesigned sidebar, and dense country header. Four of eight tabs are live (Overview, Macro, News, Events); four remain placeholders (FX Intelligence, Risk Decomposition, Economic Structure, Forecasts). News ingestion runs via GDELT DOC 2.0 + RSS with Claude Sonnet 4.5 scoring and heuristic fallback. Phase 2b.1 (FX Intelligence tab + daily re-scoring cron) is next.

---

## 2. Phase ledger

| Phase | Status | Summary |
|---|---|---|
| **Phase 1** | ✅ Done | Country header (risk gauge, spread, IMF pill, ratings cards), sidebar rewrite, FX ticker, data model extensions (10 new Country columns), Alembic migration 0010 |
| **Phase 1 cleanup** | ✅ Done | Sidebar auto-expand on route, exact sub-item highlighting, context tags for all countries, comparison page macro key fix |
| **Phase 2a** | ✅ Done | Tab shell (8 tabs, URL routing, WAI-ARIA), Overview tab (risks/opportunities/risk decomposition rings/synopsis), Macro tab (6 cards + Recharts sparklines + warnings), News tab (article cards + side panel + deep linking), Events tab. Migration 0011 |
| **Phase 2a.1 cleanup** | ✅ Done | News backfill (GDELT + RSS, 450 articles), synopsis seeding (all 10 countries), ratings drift fix (stale duplicate deletion), composite rating NR crash fix |
| **Phase 2a.2 cleanup** | ✅ Done | Claude scoring path fixed (root cause: backfill scripts bypassed AI scorer), 19 articles Claude-scored batch 1, CIV coverage fixed (GDELT apostrophe bug, 1→51 articles), scoring method surfaced in UI |
| **Phase 2b.1** | ✅ Done | FX Intelligence tab (spot, change ladder, regime, parallel premium, REER, reserves, intervention), daily Claude re-scoring cron (03:30 UTC), 12-month FX history backfill, migration 0012 |
| **Phase 2b.1.1 cleanup** | ✅ Done | Replaced synthetic FX history with real yfinance data for all 10 currencies, added data provenance to FX history API (`primary_source`, `has_synthetic_data`), provenance flag in chart UI |
| **Phase 2b.2** | ✅ Done | REER ingester: IMF IFS primary + BIS fallback, `reer_history` table (migration 0013), monthly cron (15th at 04:00 UTC), deviation computed from 10yr trailing mean, source/base_period surfaced in UI |
| **Phase 2c** | ✅ Done | Full Risk Decomposition tab: 6 deterministic formulas, input provenance tracking, analyst-authored descriptions/sub_drivers/warnings, PoD override, nightly recomputation at 03:15 UTC |
| **Phase 2c.1 calibration** | ✅ Done | Fixed null-value macro query (get_latest returning null projections), restored ETH REER to -42.5, tuned fiscal debt multiplier (0.5→0.8) and growth volatility weight (5→7), methodology bumped to v2.1. Spread 38pts (ETH 83 → MAR 45). |
| **Phase 3a** | ✅ Done | Economic Structure tab: trade_annual table (migration 0014), HHI diversification + commodity dependency, top exports/imports/partners, seed data for all 10 countries. Comtrade ingester ready but needs API key. |
| **Phase 3b** | ✅ Done | Forecasts tab: 4 indicators × 2 years, bull/bear via risk-scaled dispersion (baseline ± base_width × risk/50), direction-aware, clamping, methodology footer. All 8 tabs now live. |
| **Phase 4a** | ✅ Done | Dashboard unification: risk ranking from composite_risk_score, portfolio avg, staleness index, intelligence feed from real news, rating actions from DB. Market tiles + alerts = Phase 4b/4c placeholders. |
| **Phase 4b** | ⬜ Pending | Admin panel + market data ingestion (Brent, DXY, EMBI, etc.) |
| **Phase 4c** | ⬜ Pending | Alerts service (threshold detection, notifications) |

---

## 3. Deferred items & known gaps

| Item | Target phase | Notes |
|---|---|---|
| Dashboard Portfolio Risk Ranking scores disagree with `composite_risk.score` | Phase 4 | `// TODO: unify with composite_risk.score in Phase 3` in `Dashboard.tsx:315` |
| Dashboard "EMBI+ SPREAD 398bps" is hardcoded | Phase 4 | Admin entry or real feed |
| Dashboard market indicators (Brent, 10Y, DXY, Gold, SSA CDS) all mock | Phase 4 | `// TODO: integrate real market data feed` in `Dashboard.tsx:41` |
| "5 Active" alerts pill in country header is hardcoded | Phase 4 | `// TODO: Phase 3 — count comes from user alerts service` in `CountryProfile.tsx:240` |
| ~431 articles still heuristic-scored | Phase 2b.1 | Daily re-scoring cron will clear backlog in ~10 days |
| REER values seeded manually | Phase 2b.2 | BIS/IMF IFS ingester replaces manual seed |
| Francophone news coverage gap | Unassigned | RSS sources are Anglophone-biased. Future: Jeune Afrique, RFI Afrique, Agence Ecofin |
| Events calendar grid view | Unassigned | Phase 2a shipped list view only |
| Real-time FX, FX options term structure, intervention time-series | Out of scope | No phase assigned |
| Bloomberg / paid feeds (EMBI, rating agency APIs, FX IV) | Phase 4 | No free alternatives; manual entry via admin panel |
| IMF SDMX API unreachable from dev network | Pre-deploy | TCP timeout to `dataservices.imf.org:443`. REER ingester falls back to seed. Test from VPN/cloud, or add proxy relay. |
| Dashboard Intelligence Feed reads from real news table | Phase 4 | Currently mocked data |
| Economic Diversification feeding into Growth Risk formula | Phase 3a.1 | Recalibration pass |
| GDP by sector breakdown — not in Comtrade, needs World Bank NA ingester | Phase 3a.2 | If prioritized |
| Monthly Comtrade granularity | Unassigned | Annual + YoY sufficient for sovereign risk |
| CFA peg adjustment in risk formulas | Unassigned | Contagion insulation + WAEMU anchor + restructuring base rate |

---

## 4. Architectural decisions

| Decision | Rationale |
|---|---|
| **Delta direction computed backend-side** | Business logic (inflation down = green, reserves up = green) lives on server. Frontend renders what it's told. Same for FX change-ladder signs and severity pills. |
| **Severity thresholds in one place (backend)** | Backend computes severity labels/pills; frontend renders. Avoids drift between API docs and UI. |
| **`scoring_method` field on articles** | Every article tagged `claude` or `heuristic` via `scorer` field on `NewsImpactScore`. Surfaced in UI for transparency. |
| **Tab routing via URL query param** | `?tab=macro&article=123` — shareable, back-button works, not local state only. |
| **Article detail = right-side sheet panel** | Not a new route — keeps analyst in tab context. URL updates for deep linking. |
| **News dedup by URL** | Primary key. `url_hash` (SHA-256) for uniqueness constraint. Previous ratings dedup key `(iso3, agency, rating, action_date)` caused drift. |
| **GDELT uses keyword search, not FIPS codes** | Quoted phrases required for multi-word country names. Apostrophes removed (CIV fix). |
| **FX sign convention** | USD/local: depreciation = positive = red; appreciation = negative = green. EM analyst convention. |
| **Dark mode only** | No light mode variants. Design system uses `ink-*` palette with `bg-ink-800`/`bg-ink-950`. |
| **Bull/Bear scenarios via risk-scaled dispersion** | `baseline ± base_width × composite_risk/50`. Higher risk = wider bands. Direction-aware: for "lower_better" indicators (inflation), bull is numerically lower. Alternatives considered: ±1.5σ historical, indicator-specific volatility. Risk-scaled chosen for narrative consistency. |
| **Model validator for flat→nested mapping** | Country schema uses `@model_validator(mode="before")` to assemble `composite_risk`, `atlas_spread`, `imf_program` from flat DB columns. |
| **FX spot history backfill** | `yfinance` (Yahoo Finance, free, no key) for one-time 12-month pull for all 10 currencies. `exchangerate.host` requires paid key now; `frankfurter.app` (ECB) only covers ZAR. `open.er-api.com` continues for daily. |

---

## 5. Data sources state

| Source | Status | Location | Notes |
|---|---|---|---|
| IMF WEO | ✅ Wired | `apps/api/src/atlas_api/ingestion/imf.py` | 10 countries, `datamapper` API |
| World Bank Open Data | ✅ Wired | `ingestion/worldbank.py` | Same 10 countries, API v2 |
| FX spot (daily) | ✅ Wired | `ingestion/fx.py` | `open.er-api.com`, free, no key |
| Credit ratings | ✅ Seed JSON | `infra/seed/ratings.json` | S&P/Moody's/Fitch, manual entry |
| FX parallel premium | 🟡 Schema exists | `Country.fx_parallel_premium` | Seeded manually, Phase 4 admin |
| Sovereign spreads / EMBI | ❌ Mock only | Dashboard hardcoded | Phase 4 |
| REER | ✅ Wired | `ingestion/reer.py` | IMF IFS primary (SDMX API), BIS broad fallback, seed values as last resort. Monthly cron. `reer_history` table for time series. |
| News | ✅ Wired | GDELT DOC 2.0 + RSS | Reuters Africa, IMF Blog, WB Blog. 500 articles ingested. |
| Events | ✅ Auto-classified | `services/news/nlp.py` | spaCy NER + keyword rules, 7 event types. Derived from news items. |
| AI scoring | ✅ Wired | `services/ai/news_scorer.py` | Claude Sonnet 4.5, 200k daily cap, PromptTrace audit, heuristic fallback |
| Synopses | ✅ Seeded | `Synopsis` table | All 10 countries, `human_approved` status |
| UN Comtrade | ✅ Wired | `ingestion/comtrade.py` | Annual trade data, 5-year history, quarterly refresh, 500 req/day limit. Real data for all 10 countries (2022-2023). Seed fallback for gaps. |

---

## 6. Gotchas & hard-won lessons

- **Backfill scripts bypassing the AI scorer** — two entry points existed; one called heuristic directly. Always route through `score_with_ai()` / `_score_item`.
- **Apostrophes in GDELT queries** break the parser — use quoted phrases without apostrophes for multi-word country names (`"Ivory Coast" OR "Cote Ivoire"`).
- **Dedup keys that include mutable fields** (rating letter, action_date) cause stale duplicates. Dedup should use stable identity keys.
- **`rating_to_score` crashes on `NR`/`WD`/`WR`** — skip unrated values and rescale weights, don't assume every rating is a letter grade. Fix in `composite_rating.py`.
- **Rationale fields returned as dicts, not strings** — `NewsImpactScore.rationale` is JSONB. UI must format server-side JSON into readable text, not render raw `{}`.
- **Tab badge counts need eager fetching at parent level** — if counts depend on child tab mounting, they show `(0)` until clicked. Moved to `CountryProfileTabs` with React Query.
- **CFA franc countries (CIV, SEN) have near-zero FX change** — hard peg means the change ladder is correct, not broken.
- **IMF IFS uses ISO-2 codes** — hardcoded mapping in `reer.py`. Some series codes are vintage-specific (`EREER_IX` vs `EREER_IX_CPI`).
- **REER is monthly with 1-3 month lag** — don't fake freshness. Surface the lag via `as_of` fields and staleness pills.
- **Nightly risk recomputation must NOT overwrite analyst-authored fields** — merge carefully: only recompute scores/edge_case/inputs, preserve description/sub_drivers/warning from existing JSONB.
- **PoD override forces Liquidity ≥95 for restructuring countries** — don't let the formula underflow this.
- **Formula input keys must exactly match DB keys.** Previous bug: `get_latest()` returned null projections over real historical values. Fix: skip null values in query. Audit on every formula change.
- **Comtrade uses UN M49 numeric codes, not ISO-3.** Keep `COMTRADE_REPORTER_CODES` mapping in `ingestion/comtrade.py` current.
- **Comtrade annual data has 6-12 month reporting lag** for African countries. Latest year may be 2-year-old for laggards.
- **Comtrade revises historical data** — ingester must overwrite (ON CONFLICT DO UPDATE), not dedup-skip.
- **SQLAlchemy Numeric types serialize as strings in JSON** — frontend must wrap with `Number()` before calling `.toFixed()`. Hit this on `share_pct` in Economic Structure tab.
- **Bull = optimistic, Bear = pessimistic** — for "lower_better" indicators (inflation), bull is numerically LOWER than baseline. Direction logic in `INDICATOR_DIRECTION` mapping in `services/forecast/scenarios.py`.
- **Dashboard reads from `/api/dashboard/summary` aggregate endpoint.** Don't compute aggregates in the frontend or in individual country endpoints — keeps Dashboard queries cheap.
- **Non-English articles from GDELT** — filter by `sourcelang:english` for coverage, or translate titles via Claude (~8k tokens per 122 articles).
- **GDELT rate limit** — 1 request per 5 seconds enforced. Batch fetches need delays between queries.
- **`StalenessState` enum** — design system uses `"fresh" | "yellow" | "red" | "missing"`, NOT `"stale" | "very_stale"`. Match the enum values.

---

## 7. Token budget & quotas

| Item | Budget |
|---|---|
| Claude Sonnet 4.5 daily token cap | 200k (`ai_daily_token_cap` in config) |
| Article scoring cost | ~1.5–2.5k tokens each (input + output) |
| Translation cost | ~8k per 122 articles (one-time batch) |
| Daily re-scoring cron budget | `DAILY_RESCORE_TOKEN_BUDGET` default 150k (leaves 50k headroom) |
| Disable re-scoring | Set `DAILY_RESCORE_LIMIT=0` |

---

## 8. Repo structure (key paths)

```
atlas/
├── apps/api/src/atlas_api/
│   ├── routers/          # auth, countries, fx, news, scenarios, synopses, health
│   ├── services/
│   │   ├── ai/           # news_scorer.py, synopsis.py, provider.py, trace.py
│   │   ├── news/         # gdelt.py, rss.py, pipeline.py, nlp.py, heuristic_scorer.py
│   │   ├── country/      # bundle.py, queries.py, composite_rating.py, risk_score.py
│   │   └── scenario/
│   ├── ingestion/        # imf.py, worldbank.py, fx.py, ratings.py, orchestrator.py
│   ├── models.py         # All SQLAlchemy models
│   ├── config.py         # Settings (DB, auth, AI, ingestion toggles)
│   └── main.py           # FastAPI app, router registration
├── apps/web/src/
│   ├── routes/           # Dashboard, CountryProfile, CountriesList, etc.
│   │   └── country-profile/  # CountryProfileTabs, OverviewTab, MacroTab, NewsTab, EventsTab
│   ├── components/       # Sidebar, FxTicker, RatingCard, RiskGaugeCircle, etc.
│   │   └── ui/           # Tabs (generic headless)
│   ├── api/client.ts     # Fetch wrapper
│   └── auth/             # AuthContext
├── packages/
│   ├── design-system/    # Tailwind preset, StalenessChip, RiskGauge, etc.
│   └── schemas/          # Pydantic schemas (shared between API and codegen)
├── infra/
│   ├── migrations/versions/  # 0001–0011
│   └── seed/             # countries.json, ratings.json, countries_phase2a.json
└── PROJECT_MEMORY.md     # This file
```

---

## 9. Last updated

Last updated: 2026-04-21 by Phase 4a (Dashboard unification: scores match country pages, real data everywhere, clean placeholders for Phase 4b/4c).
