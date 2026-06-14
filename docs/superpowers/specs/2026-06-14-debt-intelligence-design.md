# Debt Intelligence Module — Design Spec

**Date:** 2026-06-14  
**Status:** Approved  
**Priority:** Highest gap identified in MVP review

---

## Overview

Add a Debt Intelligence tab to every country profile page. The tab surfaces debt composition, maturity structure, vulnerability flags, and AI-generated commentary sourced from real IMF DSA and World Bank IDS data. It links into the existing Scenario Engine for shock simulation.

---

## 1. Data Model

### New column: `debt_profile` (JSONB) on the `Country` model

Migration: `0015_add_debt_profile.py` (Alembic, follows the `risk_decomposition` pattern).

**JSONB shape:**

```json
{
  "vintage": "2024-Q3",
  "source": "IMF DSA / World Bank IDS",
  "headline": {
    "debt_gdp_pct": 76.4,
    "external_debt_gni_pct": 52.1,
    "debt_service_exports_pct": 23.7
  },
  "composition": {
    "domestic_pct": 42,
    "external_pct": 58,
    "currency": { "usd": 38, "eur": 23, "local": 17, "other": 22 },
    "fixed_pct": 65,
    "variable_pct": 35
  },
  "maturity": {
    "lt1yr_pct": 18,
    "yr1_3_pct": 27,
    "yr3_5_pct": 21,
    "gt5yr_pct": 34,
    "wall_year": 2025
  },
  "flags": {
    "high_fx_exposure": true,
    "near_term_maturity_wall": true,
    "market_access_restricted": false,
    "restructuring_overhang": false
  },
  "ai_commentary": null
}
```

`ai_commentary` starts as `null` and is filled nightly by Claude. Null renders a placeholder on the frontend, not a crash.

---

## 2. API Layer

No new endpoint. The existing `GET /api/countries/{iso3}` bundle endpoint gains one new key:

```json
{ "debt_profile": { ...JSONB above... } }
```

If `country.debt_profile` is `None`, the bundle returns `"debt_profile": null`.

### AI commentary generation

New service function `generate_debt_commentary(country)` in `apps/api/src/atlas_api/services/country/`. Calls Claude Sonnet with the debt profile JSONB, returns 2–3 sentences of analysis. Triggered nightly by the existing `run_nightly()` orchestrator alongside synopsis generation. Result written back to `country.debt_profile["ai_commentary"]`. Stored with model ID and timestamp for auditability.

---

## 3. Frontend Tab

**File:** `apps/web/src/routes/country-profile/DebtIntelligenceTab.tsx`  
**Route:** `?tab=debt` (registered in `CountryProfileTabs.tsx`)

### Layout (sectioned scroll)

```
┌─────────────────────────────────────────────┐
│  DEBT OVERVIEW                              │
│  Debt/GDP  ·  Ext Debt/GNI  ·  DS/Exports  │
├─────────────────────────────────────────────┤
│  AI COMMENTARY  (expanded by default,       │
│  collapsible)                               │
├─────────────────────────────────────────────┤
│  COMPOSITION                                │
│  Domestic / External split                  │
│  Currency mix (donut chart)                 │
│  Fixed / Variable split                     │
├─────────────────────────────────────────────┤
│  MATURITY PROFILE                           │
│  Bar chart: <1yr · 1-3yr · 3-5yr · >5yr    │
│  Maturity wall callout (year)               │
├─────────────────────────────────────────────┤
│  VULNERABILITY FLAGS                        │
│  ⚠ / ✓ per flag                            │
├─────────────────────────────────────────────┤
│  [Run Debt Shock Scenario →]                │
│  Links to ?tab=scenarios&iso3={iso3}        │
└─────────────────────────────────────────────┘
```

**Charts:** Recharts (already used in `FxIntelligenceTab` and `RiskDecompositionTab`). No new dependencies.

**Null state:** If `debt_profile` is `null` in the bundle response, the tab renders a "Data not yet available" placeholder for all sections.

---

## 4. Seed Data

**File:** `infra/seed/debt_profiles.json` — keyed by ISO3, hand-populated from real IMF DSA / World Bank IDS publications.

**Seeder:** `infra/seed/seed_debt_profiles.py` — reads JSON, bulk-upserts into `Country.debt_profile` for matching ISO3 rows. Runs alongside existing seed scripts.

**Initial five countries (demo coverage):**

| ISO3 | Country | Story |
|------|---------|-------|
| GHA | Ghana | Active distress — maturity wall, IMF program |
| ZMB | Zambia | Post-default restructuring recovery |
| KEN | Kenya | Elevated but manageable, Eurobond pressure |
| ETH | Ethiopia | Ongoing G20 Common Framework restructuring |
| EGY | Egypt | High debt/GDP, FX pressure, IMF-supported |

Spread covers distress, restructuring, elevated risk, and borderline — flags and AI commentary will be meaningful across all five.

---

## 5. Testing

**Migration smoke test** — `alembic upgrade head` then `alembic downgrade -1` in CI. Confirms `debt_profile` column round-trips.

**API unit test** — `tests/test_bundle.py`, two new cases:
1. Country row with seeded `debt_profile` → `GET /api/countries/{iso3}` returns `debt_profile.headline.debt_gdp_pct` correctly.
2. Country row with `debt_profile = None` → bundle returns `"debt_profile": null` without error.

No frontend unit tests — the tab is display-only (no user-editable state).

---

## Implementation Order

1. Alembic migration 0015 (`debt_profile` column)
2. Seed file + seeder script (5 countries)
3. Bundle endpoint update (include `debt_profile`)
4. `DebtIntelligenceTab.tsx` (all sections, null state)
5. Tab registration in `CountryProfileTabs.tsx`
6. `generate_debt_commentary()` service function + nightly hook
7. Migration smoke test + two API unit tests
