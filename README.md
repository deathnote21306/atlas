# Atlas

> Sovereign-finance decision-grade intelligence platform — prototype.

**Live demo:** [atlas-tau-dun.vercel.app](https://atlas-tau-dun.vercel.app) — log in with `analyst@atlas.test` / `change-me`.

Atlas turns a messy real-time firehose of macro data, FX, credit ratings, and news into **decision-grade country briefs** for sovereign-finance analysts (the kind of user you'd find at an institution like the OPEC Fund). It tracks 10 SSA/MENA economies (CIV, GHA, KEN, NGA, SEN, ETH, RWA, ZAF, MAR, EGY) and generates AI-scored country intelligence — with **full prompt lineage on every AI-generated figure**, so a reviewer can always see *why* a score exists, not just *what* it is.

## Highlights

- **Real-time news pipeline (runs every 10 min):** GDELT + RSS → semantic dedup (fastembed MiniLM → pgvector) → spaCy NER → relevance filter → event classification → **4-axis impact scoring**.
- **Explainable AI scoring:** country synopses and impact scores are generated with Claude and stored with full prompt lineage / provenance — a "receipt" a human reviewer can audit.
- **Data engine:** World Bank, IMF, FX, and credit-ratings ingestion with an admin review flow.
- **Production-shaped:** monorepo (pnpm + uv workspaces), GitHub Actions CI (Python + JS + Docker, all green), **219 tests** (182 pytest + 37 JS), deployed on Vercel (SPA + API proxy) + Railway (FastAPI container) + Supabase (Postgres + pgvector).

## Stack

React + Vite + Tailwind · FastAPI · Postgres + pgvector · Redis (cache) · Claude Sonnet · spaCy · fastembed (MiniLM)

## Architecture

Monorepo: `apps/web`, `apps/api`, `packages/schemas`, `packages/design-system`. Full design doc: `docs/superpowers/specs/2026-04-12-atlas-prototype-design.md`.

## Dev setup

Prerequisites: Node 20+, pnpm 9, uv 0.4+, Docker.

```bash
cp .env.example .env
docker compose up -d            # postgres + pgvector
uv sync                          # python deps across workspace
pnpm install                     # js deps across workspace
pnpm build:types                 # generate TS types from Pydantic
uv run alembic -c infra/migrations/alembic.ini upgrade head
uv run python apps/api/scripts/seed_demo_user.py
uv run uvicorn atlas_api.main:app --reload --app-dir apps/api/src
pnpm dev:web                     # in a second terminal
```

Web: http://localhost:5173 · API: http://localhost:8000/api/health

## Failure modes & what I'd fix

Atlas ingests a messy real-time firehose and turns it into scored briefs. The interesting failures were in the **data and the scoring**, not the happy path.

1. **Silent data-quality failure — the REER ingester falling back to seed data.** The IMF endpoint (`dataservices.imf.org`) times out from some networks, and my ingester "gracefully" fell back to seeded values. The result: briefs that *looked* complete but were quietly stale — a confident-but-wrong output, the worst kind of failure because nothing crashes. The fix is to treat freshness/provenance as first-class (surface a data "receipt" on every figure) and **fail loud** — flag the brief as degraded instead of silently substituting.

2. **Semantic dedup over-merging distinct events.** News dedup uses pgvector (MiniLM embeddings + a cosine threshold). Too loose merges genuinely different events; too tight floods the feed with near-duplicates. Biasing toward recall produced false merges between similarly-worded but distinct stories (e.g., two countries' rate decisions on the same day). The fix: tighten the threshold and gate merges on entity overlap from the NER step, rather than trusting cosine similarity alone.

3. **Relevance / event classifier misfires on ambiguous text.** Short headlines and mixed-language wire copy — the opposite of a tidy CSV — are where the relevance filter and event classifier are weakest. Real-world text is inconsistent and under-specified, so the honest answer is that this needs a labeled evaluation set to measure and harden, not just spot-checking.

4. **Impact-score calibration.** The 4-axis impact score is only as trustworthy as its calibration; with no labeled outcomes it's easy to produce numbers that *look* precise but aren't grounded. Storing full prompt lineage on every score is a mitigation (a reviewer can see the reasoning), but the real fix is a labeled holdout of realized outcomes to check calibration against.

**What I'd do differently:** treat data freshness and provenance as first-class, fail loud on degraded inputs, and validate any score against a labeled holdout before trusting it.

## Status

Active prototype — Foundation, Data Engine, Country Intelligence, Scenario Engine, News Pipeline, and AI Integration shipped. Portfolio / demo project.
