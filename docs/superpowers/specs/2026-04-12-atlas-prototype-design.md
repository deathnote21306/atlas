# Atlas Prototype — Design Spec

**Date:** 2026-04-12
**Status:** Approved for implementation planning
**Derived from:** ATLAS PRD v2.0
**Scope:** Prototype subset of Phase 1 Core — informational value loop only

---

## 0. Purpose & Scope

Build a working Atlas prototype that demonstrates the PRD's central insight to a design partner (first target: an analyst at OPEC Fund, Vienna) within weeks rather than months. The prototype validates whether Atlas's informational workflow — country intelligence, scenario testing, news-in-context, committee-ready brief — saves a senior sovereign analyst meaningful time and produces defensible outputs.

### In scope

1. **Data Engine (lite)** — World Bank + IMF WEO + ExchangeRate.host ingestion with vintage versioning, 10 curated countries.
2. **Country Intelligence** — full page per PRD §6.3 (header, exec synopsis, ratings, macro grid, FX section, risk decomposition, news & impact).
3. **Dashboard (lite)** — global indicators strip, top movers within our 10, narrative panels (AI-generated).
4. **Scenario Engine — manual mode only** — 5 sliders, <500ms deterministic feedback, save/load.
5. **News & Event Intelligence** — GDELT + RSS ingestion, semantic dedup via pgvector, 4-axis impact scoring via Claude, surfaced on country page.
6. **Reports — Country Brief template only** — <10s PDF generation with embedded provenance manifest.

### Explicitly out of scope (for prototype)

- Deal Analysis module (Module 4 of PRD). Deferred to Phase 1.
- Live Monitoring Layer (WebSocket, Redis Streams, alert rules engine, email/Slack delivery). Deferred to Phase 1.
- Scenario Engine AI-assisted mode. Deferred to Phase 1.
- Report templates other than Country Brief (Deal Memo, Executive Dashboard, Scenario Report, News Impact Digest). Deferred to Phase 1.
- TimescaleDB. Plain Postgres is sufficient for the prototype's data volume; schema is compatible when promoted.
- MFA, full RBAC, audit logging at enterprise grade. Prototype ships with a single demo user.
- Pen testing, SOC 2, licensed news feeds. All Phase 1+ concerns.

### Target users (prototype)

- **You** (developer / product) for iteration and self-demo.
- **Design partner analyst** (sovereign / DFI) for guided evaluation demos.
- Not end-users yet. No signup flow, no billing.

### Success criteria

- End-to-end demo flow (Dashboard → Country page → Scenario → Country Brief PDF) completes in under 5 minutes with zero runtime errors.
- Country Brief PDF is presentable to a DFI analyst without caveats or apology.
- 10 countries render fully with current data, or render honestly as partial when source data is sparse.
- Provenance traceable end-to-end: every number → source + vintage; every AI output → prompt trace.

---

## 1. Architecture

Modular monolith, three planes (Data, Serving, AI) running as one FastAPI application plus one React SPA.

```
Frontend (Vercel, fra1)
  React 18 + Vite + TS + Tailwind + Recharts + React Query
       │
       │ REST + JSON
       ▼
FastAPI gateway (Railway EU-West)
  ├── Country Service        ├── Scenario Service
  ├── News Service           ├── Reports Service
  ├── Ingestion Workers      ├── AI Orchestration
  └── Auth Service

       │          │               │
       ▼          ▼               ▼
  Postgres 15   Redis       Local disk (dev) / R2 (prod)
  + pgvector    (cache)     PDF outputs
       │
       │ pulls
       ▼
  World Bank API | IMF WEO | ExchangeRate.host | GDELT | RSS | Anthropic Claude
```

### Key architectural decisions

- **Modular monolith, not microservices.** One FastAPI deploy unit, one Postgres connection pool, Python-package-level service boundaries (`services/country/`, `services/scenario/`, etc.) with clean public APIs. Avoids premature distributed-systems complexity.
- **Ingestion runs in-process** via APScheduler. Promotable to a separate worker without changing the jobs.
- **No WebSocket, no Redis Streams, no TimescaleDB in the prototype.** All three are Phase 1 additions. The schema does not depend on them.
- **Shared types** flow Pydantic → generated TypeScript via `datamodel-code-generator` in the monorepo build step. Frontend cannot drift from backend contracts.
- **Hosting**: Vercel (frontend) + Railway (backend + Postgres + Redis), all EU-West / fra1 region. Cloudflare R2 (EU jurisdiction) for PDF storage at deploy time.

---

## 2. Repo Structure

Single private monorepo at `github.com/deathnote21306/atlas`, pnpm workspaces + Python workspace.

```
atlas/
├── apps/
│   ├── web/                 # React + Vite frontend
│   └── api/                 # FastAPI backend
├── packages/
│   ├── schemas/             # Pydantic source of truth; generates TS types
│   └── design-system/       # Tailwind config, palette, typography, primitives
├── infra/
│   ├── docker/
│   ├── migrations/          # Alembic
│   └── seed/                # Countries, FX regimes, ratings JSON
├── docs/
│   └── superpowers/specs/
├── .github/workflows/
├── package.json             # pnpm workspace
├── pyproject.toml           # Python workspace (uv)
└── README.md
```

---

## 3. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind | Per PRD §5.1 |
| Charts | Recharts primary, D3 where custom | Per PRD §5.1 |
| Server state | TanStack Query (React Query) | Per PRD §5.1 |
| Backend | FastAPI + Pydantic v2 | Per PRD §5.2 |
| ORM | SQLAlchemy 2.0 + Alembic migrations | — |
| DB | PostgreSQL 15 + `pgvector` extension | Timescale deferred |
| Cache | Redis (cache-only in prototype) | Streams deferred |
| Ingestion | APScheduler in-process jobs | Separate worker deferred |
| PDF | Playwright-Python + headless Chrome | Drives the frontend with a `?for-pdf=1` flag for chart parity |
| AI | Anthropic Claude Sonnet 4.5 via `anthropic` SDK | `AIProvider` abstraction for later providers |
| Embeddings | `all-MiniLM-L6-v2` via `sentence-transformers` (local) | Free, adequate for GDELT dedup |
| Entity extraction | spaCy (`en_core_web_sm` + `fr_core_news_sm`) | Free, good enough for country recognition |
| Auth | JWT in httpOnly cookie, argon2 password hashing | Single demo user, no MFA |
| Package mgmt | pnpm (JS), uv (Python) | — |
| CI | GitHub Actions | — |
| Hosting | Vercel (frontend, fra1) + Railway (backend+DB, EU-West) | — |
| Storage | Local disk (dev), Cloudflare R2 EU (prod) | — |

---

## 4. Component Inventory

### Frontend routes

| Route | Component | Purpose |
|---|---|---|
| `/login` | Login | Email + password, single demo user |
| `/` | Dashboard | Global indicators strip, top movers (from our 10), 4 narrative panels |
| `/countries` | CountryList | Filter chips + fuzzy search across the 10 countries |
| `/countries/:iso3` | CountryProfile | Header, synopsis, ratings, macro grid, FX section, risk decomposition, news |
| `/scenarios/new?country=XXX` | ScenarioEngine | 5-slider manual scenario with live deterministic output |
| `/scenarios/:id` | ScenarioView | Saved scenario with reproducible inputs |
| `/reports` | ReportsList | Generated Country Briefs, linked to vintages |
| `/reports/new` | ReportGenerator | 3-step flow: template → country → generate → download PDF |
| `/admin/synopses` | SynopsisReview | Demo-prep view: approve/edit/reject proposed synopses |

Deep linking mandatory per PRD §4.2.

### Backend service packages

| Service | Responsibility |
|---|---|
| `country_service` | Country CRUD, macro reads (latest + as-of), composite rating, Risk Score |
| `ingestion_service` | Scheduled pulls, vintage writes, circuit breakers |
| `news_service` | GDELT + RSS polling, pgvector dedup, entity extraction, relevance filter, triggers AI impact scoring |
| `scenario_service` | Deterministic shock engine, scenario persistence |
| `ai_service` | Claude wrapper with typed schemas, prompt lineage, cost guardrail, circuit breaker |
| `reporting_service` | Country Brief rendering (Jinja2 → headless Chrome → PDF), provenance manifest embedding |
| `auth_service` | JWT lifecycle, password hashing, role stubs |

### Shared packages

- `packages/schemas/` — Pydantic v2 models as the single source of truth. TS types generated at `pnpm build:types`.
- `packages/design-system/` — Tailwind config implementing PRD §7 palette/typography, plus reusable primitives: `KpiCard`, `RatingBadge`, `RiskGauge`, `InstitutionalTable`, `NewsItemCard`, `StalenessChip`.

---

## 5. Data Model

Vintage versioning is non-negotiable per PRD §2.3 and §8.3. Two read paths: `get_latest(indicator, country)` for monitoring/dashboards, `get_as_of(indicator, country, vintage_id)` for reproducible reports.

### Core tables

**`country`** — reference
- `iso3` PK (e.g. `"GHA"`)
- `name`, `capital`, `region`, `tags[]`, `tier`
- `status` enum: `performing | negotiating | selective_default | default | restructured`
- `fx_regime` enum per PRD §6.3.2.F
- `fx_regime_notes`, `fx_parallel_premium` (nullable, for parallel-market countries)

**`data_vintage`** — groups a coherent snapshot
- `id` UUID PK (e.g. `"2026-04-12T03:00:00Z/worldbank-weo"`)
- `created_at`, `source`, `notes`

**`macro_indicator_vintage`** — append-only macro series
- `id` PK, `iso3` FK, `indicator` (string key), `value` numeric nullable
- `source`, `source_date`, `ingested_at`, `period`, `vintage_id` FK
- UNIQUE `(iso3, indicator, period, vintage_id)`
- Index: `(iso3, indicator, period DESC, ingested_at DESC)`

**`rating_history`** — append-only ratings
- `id` PK, `iso3` FK, `agency` (S&P/Moodys/Fitch)
- `rating`, `outlook`, `action`, `action_date`, `source_url`

**`fx_rate`** — daily FX
- `iso3`, `ccy`, `usd_per_ccy`, `observation_date`, `source`, `ingested_at`
- UNIQUE `(iso3, observation_date)`

**`news_item`** — ingested news
- `id` PK, `url` UNIQUE, `title`, `source`, `published_at`, `body_text`
- `embedding` vector(384) — HNSW index for dedup
- `primary_iso3` FK nullable (after entity extraction)
- `event_type` enum: Monetary / Fiscal / Political / External / Rating / IMF / Market
- `raw_payload` JSONB
- Index: `(primary_iso3, published_at DESC)`

**`news_impact_score`** — 4-axis scoring
- `news_item_id` FK UNIQUE
- `fiscal_impact`, `external_impact`, `fx_impact`, `political_impact` each enum L/M/H
- `rationale` JSONB (per-axis sentence)
- `scorer` ("claude-sonnet-4-5" | "heuristic"), `scored_at`

**`synopsis`** — AI-generated country narrative
- `id` PK, `iso3` FK, `text`, `key_points` JSONB
- `generated_at`, `vintage_id` FK, `prompt_trace_id` FK
- `approval_state` enum: `proposed | human_approved | auto_approved_similarity | auto_approved_stable_country | rejected`
- `approved_by` nullable, `approved_at` nullable

**`prompt_trace`** — AI lineage
- `id` PK, `purpose` (`synopsis` | `news_impact` | `narrative_panel`)
- `model`, `prompt_hash`, `input_hash`, `input` JSONB (redacted where needed), `output` JSONB
- `user_id` nullable, `approval_state`, `created_at`

**`scenario_run`** — scenario executions
- `id` PK, `iso3` FK, `input_vintage_id` FK
- `shocks` JSONB `{gdp_shock, inflation_shock, fx_depreciation, rate_shock, commodity_shock}`
- `outputs` JSONB `{new_risk_score, distress_probability, deltas}`
- `created_by`, `created_at`, `saved` bool

**`report`** — generated report artifacts
- `id` PK, `template`, `iso3` FK, `vintage_id` FK
- `generated_at`, `generated_by`, `pdf_path`, `manifest` JSONB

**`user`** — single demo user in prototype
- `id` PK, `email` UNIQUE, `password_hash` (argon2), `role` (default `Analyst`), `created_at`

### Multi-tenancy hooks

Per PRD §14.3. Add `tenant_id UUID NOT NULL DEFAULT 'prototype-tenant'` to user-owned tables: `scenario_run`, `report`, `synopsis` (for approvals), `user`. Do NOT add to shared reference tables (`country`, `macro_indicator_vintage`, `rating_history`, `news_item`). Lets us enable multi-tenancy in Phase 1 without schema migration of reference data.

---

## 6. Data Flows

### 6.1 Nightly ingestion — 03:00 UTC

1. Create `data_vintage` row.
2. For each of 10 countries:
   - World Bank API → `macro_indicator_vintage` rows.
   - IMF WEO API → `macro_indicator_vintage` rows.
   - ExchangeRate.host → `fx_rate` rows.
3. Load manual ratings JSON → diff against `rating_history` → insert new actions.
4. Log structured summary.

Each source is wrapped with 3-retry exponential backoff. Three consecutive-run failures trip a circuit breaker that logs but does not block the rest. Missing values are recorded as missing (never zeroed).

### 6.2 News pipeline — every 10 minutes

1. Poll GDELT + configured RSS feeds.
2. Dedupe by URL hash against last 30 days.
3. Fetch + parse new items.
4. Generate embedding (local MiniLM).
5. Semantic dedup: collapse items with cosine similarity >0.92 against last 7 days.
6. Entity extraction (spaCy); set `primary_iso3` if in our 10.
7. Relevance filter (sovereign/macro keyword gate).
8. Event-type classification (rule-based for prototype).
9. Enqueue AI impact scoring.
10. `ai_service` calls Claude with typed schema → persist `news_impact_score` + `prompt_trace`.
11. If Claude unavailable → heuristic fallback (keyword-weighted), `scorer="heuristic"`, badge shown in UI.

Target: <5 minutes source → scored in DB (per PRD §12.1).

### 6.3 Synopsis generation — 03:30 UTC after ingestion

1. For each country, pull latest vintage macro bundle + last 7d scored news + current ratings + FX state.
2. Build grounded prompt with structured context block.
3. Claude call, typed output `{text, key_points[], coverage_notes[]}`.
4. Persist `synopsis` with `approval_state=proposed` + `prompt_trace`.
5. Pre-demo: reviewer opens `/admin/synopses`, sees all proposed with diff vs. last approved, clicks approve/edit/reject.

Country page shows only approved synopses; unapproved renders "AI draft, pending review" placeholder.

### 6.4 Country page load

- `GET /api/countries/:iso3` assembles: country row, latest approved synopsis, latest vintage macro bundle (12 tiles), FX latest + 1d/7d/30d/YTD deltas (client-computed), rating history (latest + 5y), composite rating (S&P×0.4 + Moody×0.35 + Fitch×0.25, rescaled), Risk Score (6-dimension deterministic), last-30d news items with impact scores, events timeline (seeded for prototype).
- Response target <2s. React Query caches with 5-min stale time.

### 6.5 Scenario run — manual mode

- User moves sliders → debounced `POST /api/scenarios/preview` with shock vector.
- Deterministic engine applies shocks to baseline → returns new Risk Score, Δ Debt/GDP, Δ Fiscal Balance, Δ Current Account, Probability of Debt Distress (or `N/A` for distressed countries).
- Response target <500ms (pure computation).
- "Save" → persists `scenario_run` row.

### 6.6 Report generation — Country Brief

- `POST /api/reports/generate {template: "country_brief", iso3, vintage_id}` (vintage_id defaults to latest, pinned on generation).
- Render Jinja2 HTML template with country bundle + approved synopsis + scored-news digest.
- Playwright-Python loads the frontend at `/countries/:iso3?for-pdf=1&vintage=<id>`, waits for charts to render, exports PDF.
- Embed provenance manifest JSON in PDF metadata + as structured appendix page.
- Persist `report` row; save PDF to local disk (dev) or R2 (prod).
- Target <10s.

---

## 7. AI Governance

Three touchpoints: synopsis generation, news impact scoring, dashboard narrative panels. All obey *AI proposes, deterministic engines decide* (PRD §2.4).

**Typed contracts.** Every Claude call uses tool-use mode with a strict JSON schema. Schema violation → retry once → fallback (heuristic for news, placeholder for synopsis).

**Grounding.** Prompts always include a structured context block (macro snapshot with dates + sources, recent ratings, FX state, top scored news). Model is instructed to emit `coverage_notes` citing which context items support each claim.

**Human-in-the-loop for synopses.** All synopses land in `approval_state=proposed`. Only approved synopses render publicly. Review UI at `/admin/synopses` supports approve / edit / reject. Schema supports future automation tiers (`auto_approved_similarity`, `auto_approved_stable_country`) without migration — approval policy is a later code change, not a schema change.

**Lineage.** Every AI output writes `prompt_trace` with model version, prompt hash, input hash (input itself stored when not sensitive), output, approval state, timestamps. Country page exposes "View AI lineage" per synopsis and per scored news item. Reports embed trace IDs in the provenance manifest.

**Cost guardrail.** Daily token cap in env config (default 200k tokens ≈ a few USD/day). Per-day counter in Redis; exceeding trips circuit breaker → heuristic news fallback, "pending refresh" on synopses. Demonstrates the governance story on demo day.

**Model.** Claude Sonnet 4.5 (`claude-sonnet-4-5`). `AIProvider` interface exists for Phase 1 provider swaps.

---

## 8. Error Handling & Edge Cases

Scoped to PRD §11 cases that matter for a prototype.

| Case | Handling |
|---|---|
| Data source failure | 3-retry backoff → keep last good vintage → yellow (>6mo) / red (>12mo) staleness badge. Missing = `—`, never 0. |
| Distressed sovereign (Ghana SD, Ethiopia) | `country.status` controls PoD: shows "Not applicable — country in [status]". Rating ladder renders SD/RD/C/D. Risk Score flags Liquidity Risk dimension. |
| Hyperinflation (Egypt, borderline) | Inflation tile uses log scale above 50% or caps at 100% with explicit marker. |
| FX parallel market (Nigeria, Egypt) | Curated `fx_parallel_premium` field, second FX number with explicit label. |
| AI unavailable | News → heuristic scorer with "heuristic" badge. Synopsis → yesterday's approved stays, retry next cycle. |
| PDF render failure | 10s hard timeout → 502 with which section failed in structured log. No partial PDFs. |
| News duplicate flood | pgvector cosine >0.92 collapse. Dedup rate >90% trips circuit breaker + alert in logs. |
| Sparse country data | <60% indicator coverage shows "Limited data coverage" banner. Risk Score dimensions marked unknown. |

**Observability.** Structured JSON logs to stdout (Railway auto-ingests). Every ingestion, AI call, report carries correlation ID. No APM in prototype.

---

## 9. Security Posture

### Prototype

- HTTPS via Vercel/Railway defaults.
- JWT in httpOnly, `SameSite=Lax` cookies.
- Argon2 password hashing.
- Single demo user seed; no signup flow.
- Role field exists (`Analyst`) but no enforcement branching yet.
- All secrets via env vars; `.env.example` committed, `.env` gitignored.
- All queries parameterized via SQLAlchemy.
- All endpoint inputs Pydantic-validated.
- `tenant_id` in schema so multi-tenancy is a later switch, not a rewrite.

### Explicitly deferred (Phase 1 / pre-paid-pilot)

MFA, full RBAC enforcement server-side, audit logging, SAST + dependency scanning in CI, rate limiting, CORS hardening, external pen test, SOC 2 preparation, DPA template, formal incident response plan.

### EU data residency

Frankfurt hosting (Vercel `fra1`, Railway EU-West, Cloudflare R2 EU jurisdiction) from day one.

---

## 10. Testing Strategy

Protects determinism (PRD's defining property) and provenance (PRD's trust story). Everything else gets lighter coverage.

**Golden scenario tests (mandatory, PRD §9.6).** Pytest, runs on every PR:
- Composite rating across all agency combinations including missing-agency rescaling.
- Risk Score for 10 country fixtures against hand-calculated values.
- Probability of Debt Distress for 5 macro states + explicit N/A case.
- Scenario engine: fixed baseline + fixed shock vector → committed expected output to 4 decimal places.
- News impact classifier against ~30 labeled items, target >80% agreement.

**Report reproducibility test.** Generate Country Brief for GHA at pinned vintage. Hash structured content (text + chart data, not pixels). Re-run → hash must match.

**Integration tests (small).** Testcontainers Postgres, one country fixture. Verify ingestion writes vintages, both read paths, news dedup collapses known near-duplicates.

**Frontend.** Vitest + React Testing Library on 6–8 reusable components. One Playwright smoke test covering the demo path: login → country list → GHA → scenario → report → PDF downloads.

**AI contract tests.** Mock Claude, verify malformed response rejection, retry path, fallback activation. Model itself not tested.

**Out of scope for prototype.** Load tests, alert-fatigue sim, mobile responsive, a11y audit, pen tests.

**CI.** GitHub Actions on PR: ruff + eslint → mypy + tsc → unit → golden → integration → frontend smoke. Target <5 min total.

---

## 11. Delivery Assumptions

- Anthropic API key created at `console.anthropic.com` (separate from Claude.ai / Claude Code subscription). Minimal spend expected (~$5–20/mo during prototype).
- GitHub CLI `gh` authenticated as `deathnote21306`.
- Hosting accounts (Vercel, Railway, Cloudflare) created when we reach deployment stage; local dev requires none of them.
- ExchangeRate.host used for FX (free, no key required).
- Ratings data: manually curated JSON in `infra/seed/ratings.json`, updated monthly. Public references only (legal posture per PRD §10.3).

---

## 12. Open Questions (resolved in this spec, for the record)

| PRD §21 question | Resolution |
|---|---|
| World map on Dashboard | Deferred post-prototype. Not critical path. |
| Editorial curation ownership | AI-generated synopses with manual pre-demo approval; "Head of Research" role deferred to Phase 1. |
| Scenario families in AI mode | AI mode out of prototype scope. |
| Demo dataset | Live data; no frozen golden dataset in prototype. Reproducibility via vintage pinning on reports. |
| Slack integration | Out of scope. |
| Semantic dedup threshold | Cosine 0.92 starting point, tunable after we have real GDELT data. |
| Alert severity schema | Out of scope. |

---

## 13. Next Step

Hand off to `superpowers:writing-plans` to produce the implementation plan broken down by stage (Foundation → Data + Country → Scenario + Reports → News + AI → Hardening).
