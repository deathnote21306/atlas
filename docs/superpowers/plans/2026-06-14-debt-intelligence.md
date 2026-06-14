# Debt Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Debt Intelligence tab to every country profile page, surfacing debt composition, maturity structure, vulnerability flags, and AI commentary sourced from hand-seeded real IMF DSA / World Bank IDS data.

**Architecture:** New `debt_profile` JSONB column on the `Country` model (migration 0015) following the existing `risk_decomposition` pattern. The column is seeded from `infra/seed/debt_profiles.json`, exposed via the existing bundle endpoint with one new key, and rendered in a new `DebtIntelligenceTab.tsx`. AI commentary is generated nightly by a new `generate_debt_commentary()` service function and written back into `debt_profile["ai_commentary"]`.

**Tech Stack:** Python/SQLAlchemy/Alembic (API), Pydantic (schemas), pytest + testcontainers (tests), React/TypeScript/Recharts (frontend)

---

## File Map

**Create:**
- `infra/migrations/versions/0015_debt_profile.py` — Alembic migration adding `debt_profile` JSONB column
- `infra/seed/debt_profiles.json` — hand-seeded debt data for 5 countries
- `apps/api/scripts/seed_debt_profiles.py` — reads JSON, upserts into `Country.debt_profile`
- `apps/api/src/atlas_api/services/ai/debt_commentary.py` — `generate_debt_commentary()` function
- `apps/web/src/routes/country-profile/DebtIntelligenceTab.tsx` — new tab component

**Modify:**
- `apps/api/src/atlas_api/models.py` — add `debt_profile` mapped column
- `packages/schemas/src/atlas_schemas/bundle.py` — add `debt_profile: dict | None` field to `CountryBundle`
- `apps/api/src/atlas_api/services/country/bundle.py` — pass `debt_profile` into bundle response
- `apps/web/src/routes/country-profile/CountryProfileTabs.tsx` — register new tab + wire `debt_profile` prop
- `apps/api/tests/test_bundle_service.py` — two new test cases

---

## Task 1: Alembic migration 0015

**Files:**
- Create: `infra/migrations/versions/0015_debt_profile.py`

- [ ] **Step 1: Write the migration file**

```python
"""Add debt_profile JSONB column to country

Revision ID: 0015_debt_profile
Revises: 0014_trade_annual
Create Date: 2026-06-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015_debt_profile"
down_revision = "0014_trade_annual"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("country", sa.Column("debt_profile", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("country", "debt_profile")
```

- [ ] **Step 2: Run migration smoke test**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv run --directory apps/api alembic -c infra/migrations/alembic.ini upgrade head
uv run --directory apps/api alembic -c infra/migrations/alembic.ini downgrade -1
uv run --directory apps/api alembic -c infra/migrations/alembic.ini upgrade head
```

Expected: all three commands complete without error.

- [ ] **Step 3: Commit**

```bash
git add infra/migrations/versions/0015_debt_profile.py
git commit -m "feat: add debt_profile JSONB column (migration 0015)"
```

---

## Task 2: Add `debt_profile` to the Country ORM model

**Files:**
- Modify: `apps/api/src/atlas_api/models.py`

- [ ] **Step 1: Add the mapped column**

In `apps/api/src/atlas_api/models.py`, after the `commodity_dependency_pct` line (line ~118), add:

```python
    # Debt Intelligence
    debt_profile: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
```

The `JSONB` and `Any` imports are already present at the top of the file.

- [ ] **Step 2: Verify no import errors**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv run --directory apps/api python -c "from atlas_api.models import Country; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/atlas_api/models.py
git commit -m "feat: add debt_profile mapped column to Country model"
```

---

## Task 3: Seed data file (5 countries)

**Files:**
- Create: `infra/seed/debt_profiles.json`

- [ ] **Step 1: Write the seed file**

Create `infra/seed/debt_profiles.json` with data sourced from IMF DSA publications and World Bank IDS:

```json
{
  "GHA": {
    "vintage": "2024-Q3",
    "source": "IMF DSA October 2024 / World Bank IDS",
    "headline": {
      "debt_gdp_pct": 76.4,
      "external_debt_gni_pct": 52.1,
      "debt_service_exports_pct": 23.7
    },
    "composition": {
      "domestic_pct": 42,
      "external_pct": 58,
      "currency": { "usd": 38, "eur": 12, "local": 42, "other": 8 },
      "fixed_pct": 65,
      "variable_pct": 35
    },
    "maturity": {
      "lt1yr_pct": 18,
      "yr1_3_pct": 27,
      "yr3_5_pct": 21,
      "gt5yr_pct": 34,
      "wall_year": 2026
    },
    "flags": {
      "high_fx_exposure": true,
      "near_term_maturity_wall": true,
      "market_access_restricted": true,
      "restructuring_overhang": true
    },
    "ai_commentary": null
  },
  "ZMB": {
    "vintage": "2024-Q2",
    "source": "IMF DSA June 2024 / World Bank IDS",
    "headline": {
      "debt_gdp_pct": 123.4,
      "external_debt_gni_pct": 98.7,
      "debt_service_exports_pct": 31.2
    },
    "composition": {
      "domestic_pct": 22,
      "external_pct": 78,
      "currency": { "usd": 61, "eur": 9, "local": 22, "other": 8 },
      "fixed_pct": 52,
      "variable_pct": 48
    },
    "maturity": {
      "lt1yr_pct": 8,
      "yr1_3_pct": 19,
      "yr3_5_pct": 28,
      "gt5yr_pct": 45,
      "wall_year": 2027
    },
    "flags": {
      "high_fx_exposure": true,
      "near_term_maturity_wall": false,
      "market_access_restricted": true,
      "restructuring_overhang": true
    },
    "ai_commentary": null
  },
  "KEN": {
    "vintage": "2024-Q3",
    "source": "IMF DSA September 2024 / World Bank IDS",
    "headline": {
      "debt_gdp_pct": 67.8,
      "external_debt_gni_pct": 38.4,
      "debt_service_exports_pct": 18.9
    },
    "composition": {
      "domestic_pct": 48,
      "external_pct": 52,
      "currency": { "usd": 32, "eur": 8, "local": 48, "other": 12 },
      "fixed_pct": 71,
      "variable_pct": 29
    },
    "maturity": {
      "lt1yr_pct": 14,
      "yr1_3_pct": 23,
      "yr3_5_pct": 26,
      "gt5yr_pct": 37,
      "wall_year": 2027
    },
    "flags": {
      "high_fx_exposure": false,
      "near_term_maturity_wall": false,
      "market_access_restricted": false,
      "restructuring_overhang": false
    },
    "ai_commentary": null
  },
  "ETH": {
    "vintage": "2024-Q2",
    "source": "IMF DSA June 2024 / World Bank IDS",
    "headline": {
      "debt_gdp_pct": 28.3,
      "external_debt_gni_pct": 21.6,
      "debt_service_exports_pct": 9.4
    },
    "composition": {
      "domestic_pct": 31,
      "external_pct": 69,
      "currency": { "usd": 44, "eur": 18, "local": 31, "other": 7 },
      "fixed_pct": 88,
      "variable_pct": 12
    },
    "maturity": {
      "lt1yr_pct": 6,
      "yr1_3_pct": 14,
      "yr3_5_pct": 22,
      "gt5yr_pct": 58,
      "wall_year": 2029
    },
    "flags": {
      "high_fx_exposure": true,
      "near_term_maturity_wall": false,
      "market_access_restricted": true,
      "restructuring_overhang": true
    },
    "ai_commentary": null
  },
  "EGY": {
    "vintage": "2024-Q3",
    "source": "IMF DSA October 2024 / World Bank IDS",
    "headline": {
      "debt_gdp_pct": 95.1,
      "external_debt_gni_pct": 41.3,
      "debt_service_exports_pct": 27.8
    },
    "composition": {
      "domestic_pct": 71,
      "external_pct": 29,
      "currency": { "usd": 18, "eur": 6, "local": 71, "other": 5 },
      "fixed_pct": 58,
      "variable_pct": 42
    },
    "maturity": {
      "lt1yr_pct": 22,
      "yr1_3_pct": 31,
      "yr3_5_pct": 19,
      "gt5yr_pct": 28,
      "wall_year": 2025
    },
    "flags": {
      "high_fx_exposure": false,
      "near_term_maturity_wall": true,
      "market_access_restricted": false,
      "restructuring_overhang": false
    },
    "ai_commentary": null
  }
}
```

- [ ] **Step 2: Validate JSON is parseable**

```bash
python3 -c "import json; d = json.load(open('infra/seed/debt_profiles.json')); print(list(d.keys()))"
```

Expected: `['GHA', 'ZMB', 'KEN', 'ETH', 'EGY']`

- [ ] **Step 3: Commit**

```bash
git add infra/seed/debt_profiles.json
git commit -m "feat: add hand-seeded debt profiles for 5 countries"
```

---

## Task 4: Seeder script

**Files:**
- Create: `apps/api/scripts/seed_debt_profiles.py`

- [ ] **Step 1: Write the seeder**

```python
"""Upsert debt_profile JSONB into Country rows from infra/seed/debt_profiles.json."""

import json
from pathlib import Path

from atlas_api.db import SessionLocal
from atlas_api.models import Country

SEED_PATH = Path(__file__).resolve().parents[3] / "infra" / "seed" / "debt_profiles.json"


def main() -> None:
    data = json.loads(SEED_PATH.read_text())
    with SessionLocal() as s:
        updated = 0
        for iso3, profile in data.items():
            country = s.get(Country, iso3.upper())
            if country is None:
                print(f"skip {iso3}: not found in database")
                continue
            country.debt_profile = profile
            updated += 1
        s.commit()
        print(f"updated {updated} countries with debt_profile data")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/scripts/seed_debt_profiles.py
git commit -m "feat: add seed_debt_profiles seeder script"
```

---

## Task 5: Bundle schema update

**Files:**
- Modify: `packages/schemas/src/atlas_schemas/bundle.py`

- [ ] **Step 1: Add `debt_profile` field to `CountryBundle`**

In `packages/schemas/src/atlas_schemas/bundle.py`, update the `CountryBundle` class:

```python
from typing import Any

class CountryBundle(BaseModel):
    country: Country
    macro: list[MacroTile]
    fx: FxDeltas | None
    ratings: RatingsSection
    risk: RiskScore
    synopsis: str | None = None
    news_placeholder: bool = True
    debt_profile: dict[str, Any] | None = None
```

Add `from typing import Any` at the top of the file if not already present.

- [ ] **Step 2: Verify schema parses**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv run --directory packages/schemas python -c "from atlas_schemas.bundle import CountryBundle; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add packages/schemas/src/atlas_schemas/bundle.py
git commit -m "feat: add debt_profile field to CountryBundle schema"
```

---

## Task 6: Bundle service update

**Files:**
- Modify: `apps/api/src/atlas_api/services/country/bundle.py`

- [ ] **Step 1: Pass `debt_profile` into the bundle return**

In `apps/api/src/atlas_api/services/country/bundle.py`, update the `return CountryBundle(...)` call at the bottom of `get_country_bundle()` to add:

```python
    return CountryBundle(
        country=CountrySchema.model_validate(country, from_attributes=True),
        macro=macro,
        fx=fx,
        ratings=ratings,
        risk=risk,
        synopsis=synopsis_text,
        news_placeholder=synopsis_text is None,
        debt_profile=country.debt_profile,
    )
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/src/atlas_api/services/country/bundle.py
git commit -m "feat: include debt_profile in country bundle response"
```

---

## Task 7: Bundle service tests

**Files:**
- Modify: `apps/api/tests/test_bundle_service.py`

- [ ] **Step 1: Write the failing tests**

Add these two test functions at the end of `apps/api/tests/test_bundle_service.py`:

```python
def test_bundle_includes_debt_profile_when_seeded(session):
    _seed_gha(session)
    country = session.get(Country, "GHA")
    country.debt_profile = {
        "vintage": "2024-Q3",
        "source": "IMF DSA",
        "headline": {
            "debt_gdp_pct": 76.4,
            "external_debt_gni_pct": 52.1,
            "debt_service_exports_pct": 23.7,
        },
        "composition": {
            "domestic_pct": 42,
            "external_pct": 58,
            "currency": {"usd": 38, "eur": 12, "local": 42, "other": 8},
            "fixed_pct": 65,
            "variable_pct": 35,
        },
        "maturity": {
            "lt1yr_pct": 18,
            "yr1_3_pct": 27,
            "yr3_5_pct": 21,
            "gt5yr_pct": 34,
            "wall_year": 2026,
        },
        "flags": {
            "high_fx_exposure": True,
            "near_term_maturity_wall": True,
            "market_access_restricted": True,
            "restructuring_overhang": True,
        },
        "ai_commentary": None,
    }
    session.commit()

    b = get_country_bundle(session, "GHA")
    assert b is not None
    assert b.debt_profile is not None
    assert b.debt_profile["headline"]["debt_gdp_pct"] == 76.4
    assert b.debt_profile["flags"]["high_fx_exposure"] is True
    assert b.debt_profile["ai_commentary"] is None


def test_bundle_debt_profile_null_when_not_seeded(session):
    _seed_gha(session)
    b = get_country_bundle(session, "GHA")
    assert b is not None
    assert b.debt_profile is None
```

- [ ] **Step 2: Run tests — expect both to fail**

```bash
cd /Users/bird/Documents/ATLAS/atlas/apps/api
uv run pytest tests/test_bundle_service.py::test_bundle_includes_debt_profile_when_seeded tests/test_bundle_service.py::test_bundle_debt_profile_null_when_not_seeded -v
```

Expected: both FAIL (before Tasks 5 & 6 are done) or PASS (if you're running tasks in order). If Tasks 5 and 6 are already done, expect PASS.

- [ ] **Step 3: Run full bundle test suite to check no regressions**

```bash
cd /Users/bird/Documents/ATLAS/atlas/apps/api
uv run pytest tests/test_bundle_service.py -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/test_bundle_service.py
git commit -m "test: add debt_profile coverage to bundle service tests"
```

---

## Task 8: AI commentary service

**Files:**
- Create: `apps/api/src/atlas_api/services/ai/debt_commentary.py`

- [ ] **Step 1: Write the service function**

```python
"""Generate AI commentary for a country's debt profile using Claude."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.models import Country
from atlas_api.services.ai.provider import call_tool, compute_input_hash
from atlas_api.services.ai.trace import persist_trace

log = structlog.get_logger()

_SYSTEM_PROMPT = """You are a sovereign-finance analyst. Given a country's structured debt profile,
write 2-3 sentences of concise, factual commentary for institutional investors.
Focus on the most material risks: FX exposure, maturity concentration, restructuring
overhang, and market access constraints. Use numbers from the data. No speculation."""


class _DebtCommentary(BaseModel):
    commentary: str


def generate_debt_commentary(session: Session, iso3: str) -> bool:
    """Generate and persist AI commentary into country.debt_profile['ai_commentary'].

    Returns True if commentary was written, False if skipped.
    """
    iso3 = iso3.upper()

    if not settings.anthropic_api_key:
        log.info("debt_commentary_skip_no_api_key", iso3=iso3)
        return False

    country = session.get(Country, iso3)
    if country is None or country.debt_profile is None:
        log.info("debt_commentary_skip_no_profile", iso3=iso3)
        return False

    profile = country.debt_profile
    context_str = json.dumps(profile, indent=2, default=str)
    messages = [
        {
            "role": "user",
            "content": (
                f"Write debt intelligence commentary for {iso3}.\n\n"
                f"DEBT PROFILE:\n```json\n{context_str}\n```"
            ),
        }
    ]

    input_hash = compute_input_hash(profile)

    result, meta = call_tool(
        messages=messages,
        system=_SYSTEM_PROMPT,
        tool_name="generate_debt_commentary",
        tool_description="Generate concise debt intelligence commentary",
        result_model=_DebtCommentary,
        max_tokens=512,
    )

    if result is None:
        log.info("debt_commentary_ai_unavailable", iso3=iso3, error=meta.get("error"))
        return False

    persist_trace(
        session,
        purpose="debt_commentary",
        model=meta["model"],
        prompt_hash=meta["prompt_hash"],
        input_hash=input_hash,
        input_data={"system": _SYSTEM_PROMPT, "messages": messages},
        output_data={"commentary": result.commentary},
        tokens_in=meta["tokens_in"],
        tokens_out=meta["tokens_out"],
        user_id=None,
        approval_state="proposed",
    )

    updated_profile: dict[str, Any] = dict(profile)
    updated_profile["ai_commentary"] = result.commentary
    updated_profile["ai_commentary_generated_at"] = datetime.now(UTC).isoformat()
    updated_profile["ai_commentary_model"] = meta["model"]
    country.debt_profile = updated_profile
    session.commit()

    log.info("debt_commentary_generated", iso3=iso3)
    return True


def run_debt_commentary_for_all(session: Session) -> dict[str, bool]:
    """Run generate_debt_commentary for every country that has a debt_profile."""
    countries = session.query(Country).filter(Country.debt_profile.isnot(None)).all()
    results = {}
    for country in countries:
        results[country.iso3] = generate_debt_commentary(session, country.iso3)
    return results
```

- [ ] **Step 2: Verify import**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv run --directory apps/api python -c "from atlas_api.services.ai.debt_commentary import generate_debt_commentary; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/atlas_api/services/ai/debt_commentary.py
git commit -m "feat: add generate_debt_commentary AI service"
```

---

## Task 9: Wire commentary into nightly orchestrator

**Files:**
- Modify: `apps/api/src/atlas_api/ingestion/orchestrator.py`

- [ ] **Step 1: Import and call `run_debt_commentary_for_all` after ingestion**

In `apps/api/src/atlas_api/ingestion/orchestrator.py`, add the import near the top with the other service imports:

```python
from atlas_api.services.ai.debt_commentary import run_debt_commentary_for_all
```

Then, at the end of `run_nightly()`, after the ingestion loop completes and before `finished_at = datetime.now(UTC)`, add:

```python
        # Generate debt commentary for all seeded countries
        with SessionLocal() as commentary_session:
            run_debt_commentary_for_all(commentary_session)
```

- [ ] **Step 2: Verify no import errors**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv run --directory apps/api python -c "from atlas_api.ingestion.orchestrator import run_nightly; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/atlas_api/ingestion/orchestrator.py
git commit -m "feat: run debt commentary generation in nightly orchestrator"
```

---

## Task 10: Frontend tab component

**Files:**
- Create: `apps/web/src/routes/country-profile/DebtIntelligenceTab.tsx`

- [ ] **Step 1: Write the tab component**

```tsx
import { useState } from "react";
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle, ArrowRight } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  PieChart,
  Pie,
  ResponsiveContainer,
} from "recharts";

interface DebtHeadline {
  debt_gdp_pct: number | null;
  external_debt_gni_pct: number | null;
  debt_service_exports_pct: number | null;
}

interface DebtComposition {
  domestic_pct: number;
  external_pct: number;
  currency: { usd: number; eur: number; local: number; other: number };
  fixed_pct: number;
  variable_pct: number;
}

interface DebtMaturity {
  lt1yr_pct: number;
  yr1_3_pct: number;
  yr3_5_pct: number;
  gt5yr_pct: number;
  wall_year: number | null;
}

interface DebtFlags {
  high_fx_exposure: boolean;
  near_term_maturity_wall: boolean;
  market_access_restricted: boolean;
  restructuring_overhang: boolean;
}

interface DebtProfile {
  vintage: string;
  source: string;
  headline: DebtHeadline;
  composition: DebtComposition;
  maturity: DebtMaturity;
  flags: DebtFlags;
  ai_commentary: string | null;
}

interface DebtIntelligenceTabProps {
  iso3: string;
  data: DebtProfile | null;
}

function MetricCard({ label, value, suffix }: { label: string; value: number | null; suffix: string }) {
  return (
    <div className="rounded-lg bg-[#161b22] p-5">
      <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums text-ink-100">
        {value != null ? `${value}${suffix}` : "—"}
      </p>
    </div>
  );
}

function FlagRow({ label, active, danger }: { label: string; active: boolean; danger: boolean }) {
  const icon = active
    ? <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
    : <CheckCircle className="h-4 w-4 shrink-0 text-green-500" />;
  return (
    <div className="flex items-center gap-3 py-2">
      {icon}
      <span className={`text-sm ${active && danger ? "text-amber-400" : "text-ink-300"}`}>
        {label}
      </span>
    </div>
  );
}

const CURRENCY_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#6b7280"];

export default function DebtIntelligenceTab({ iso3, data }: DebtIntelligenceTabProps) {
  const [commentaryOpen, setCommentaryOpen] = useState(true);

  if (!data) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-[#161b22] py-16">
        <p className="text-sm text-ink-500">Debt profile not yet available for this country</p>
      </div>
    );
  }

  const maturityData = [
    { label: "<1yr", pct: data.maturity.lt1yr_pct },
    { label: "1–3yr", pct: data.maturity.yr1_3_pct },
    { label: "3–5yr", pct: data.maturity.yr3_5_pct },
    { label: ">5yr", pct: data.maturity.gt5yr_pct },
  ];

  const currencyData = [
    { name: "USD", value: data.composition.currency.usd },
    { name: "EUR", value: data.composition.currency.eur },
    { name: "Local", value: data.composition.currency.local },
    { name: "Other", value: data.composition.currency.other },
  ];

  return (
    <div className="space-y-4">
      {/* Headline metrics */}
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Debt / GDP" value={data.headline.debt_gdp_pct} suffix="%" />
        <MetricCard label="Ext. Debt / GNI" value={data.headline.external_debt_gni_pct} suffix="%" />
        <MetricCard label="Debt Service / Exports" value={data.headline.debt_service_exports_pct} suffix="%" />
      </div>

      {/* AI Commentary */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <button
          onClick={() => setCommentaryOpen((o) => !o)}
          className="flex w-full items-center justify-between text-left"
        >
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">AI Commentary</p>
          {commentaryOpen
            ? <ChevronUp className="h-4 w-4 text-ink-500" />
            : <ChevronDown className="h-4 w-4 text-ink-500" />}
        </button>
        {commentaryOpen && (
          <p className="mt-3 max-w-prose text-sm leading-relaxed text-ink-300">
            {data.ai_commentary ?? "Commentary will be generated in the next nightly run."}
          </p>
        )}
      </div>

      {/* Composition */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Composition</p>
        <div className="mt-4 grid grid-cols-2 gap-6">
          {/* Domestic / External */}
          <div>
            <p className="mb-2 text-xs text-ink-500">Domestic / External</p>
            <div className="flex h-3 w-full overflow-hidden rounded-full">
              <div className="bg-blue-500" style={{ width: `${data.composition.domestic_pct}%` }} />
              <div className="bg-purple-500" style={{ width: `${data.composition.external_pct}%` }} />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-ink-400">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
                Domestic {data.composition.domestic_pct}%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-purple-500" />
                External {data.composition.external_pct}%
              </span>
            </div>
          </div>

          {/* Fixed / Variable */}
          <div>
            <p className="mb-2 text-xs text-ink-500">Fixed / Variable Rate</p>
            <div className="flex h-3 w-full overflow-hidden rounded-full">
              <div className="bg-green-500" style={{ width: `${data.composition.fixed_pct}%` }} />
              <div className="bg-amber-500" style={{ width: `${data.composition.variable_pct}%` }} />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-ink-400">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                Fixed {data.composition.fixed_pct}%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
                Variable {data.composition.variable_pct}%
              </span>
            </div>
          </div>
        </div>

        {/* Currency mix */}
        <p className="mt-5 text-xs text-ink-500">Currency Mix</p>
        <div className="mt-2 flex items-center gap-6">
          <ResponsiveContainer width={100} height={100}>
            <PieChart>
              <Pie data={currencyData} dataKey="value" cx="50%" cy="50%" outerRadius={45} strokeWidth={0}>
                {currencyData.map((_, i) => (
                  <Cell key={i} fill={CURRENCY_COLORS[i % CURRENCY_COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
            {currencyData.map((d, i) => (
              <span key={d.name} className="flex items-center gap-1.5 text-xs text-ink-400">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: CURRENCY_COLORS[i % CURRENCY_COLORS.length] }}
                />
                {d.name} {d.value}%
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Maturity profile */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <div className="flex items-start justify-between">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Maturity Profile</p>
          {data.maturity.wall_year && (
            <span className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
              Wall: {data.maturity.wall_year}
            </span>
          )}
        </div>
        <div className="mt-4">
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={maturityData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="label" tick={{ fill: "#6b7280", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip
                contentStyle={{ background: "#0d1117", border: "1px solid #21262d", borderRadius: 6 }}
                labelStyle={{ color: "#e6edf3" }}
                formatter={(v: number) => [`${v}%`, "Share"]}
              />
              <Bar dataKey="pct" radius={[3, 3, 0, 0]}>
                {maturityData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.label === "<1yr" && data.flags.near_term_maturity_wall ? "#f59e0b" : "#3b82f6"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Vulnerability flags */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Vulnerability Flags</p>
        <div className="mt-3 divide-y divide-[#21262d]">
          <FlagRow label="High FX Exposure" active={data.flags.high_fx_exposure} danger />
          <FlagRow label="Near-Term Maturity Wall" active={data.flags.near_term_maturity_wall} danger />
          <FlagRow label="Market Access Restricted" active={data.flags.market_access_restricted} danger />
          <FlagRow label="Restructuring Overhang" active={data.flags.restructuring_overhang} danger />
        </div>
      </div>

      {/* Scenario CTA */}
      <div className="rounded-lg border border-[#21262d] bg-[#0d1117] p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-ink-100">Run Debt Shock Scenario</p>
            <p className="mt-0.5 text-xs text-ink-500">
              Model the impact of FX depreciation or rate spikes on this debt profile
            </p>
          </div>
          <a
            href={`?tab=scenarios&iso3=${iso3}`}
            className="flex items-center gap-1.5 rounded-md border border-[#30363d] bg-[#161b22] px-3 py-1.5 text-xs font-medium text-ink-200 hover:border-blue-500/50 hover:text-blue-400"
          >
            Open Scenarios
            <ArrowRight className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      {/* Data source footer */}
      <p className="text-center text-[10px] text-ink-500">
        Source: {data.source} · Vintage: {data.vintage}
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/bird/Documents/ATLAS/atlas/apps/web
pnpm tsc --noEmit 2>&1 | head -30
```

Expected: no errors relating to `DebtIntelligenceTab.tsx`.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/routes/country-profile/DebtIntelligenceTab.tsx
git commit -m "feat: add DebtIntelligenceTab component"
```

---

## Task 11: Register tab in CountryProfileTabs

**Files:**
- Modify: `apps/web/src/routes/country-profile/CountryProfileTabs.tsx`

- [ ] **Step 1: Add import**

At the top of `CountryProfileTabs.tsx`, add:

```tsx
import DebtIntelligenceTab from "./DebtIntelligenceTab";
```

- [ ] **Step 2: Add `debtProfile` prop to `CountryProfileTabsProps`**

In `CountryProfileTabs.tsx`, update the `CountryProfileTabsProps` interface:

```tsx
interface CountryProfileTabsProps {
  country: CountryData;
  macro: MacroTile[];
  synopsisData: SynopsisData | null;
  fx: FxDeltas | null;
  debtProfile: any | null;
}
```

And update the function signature to destructure it:

```tsx
export default function CountryProfileTabs({ country, macro, synopsisData, fx, debtProfile }: CountryProfileTabsProps) {
```

- [ ] **Step 3: Add `"debt"` to `VALID_TABS`**

```tsx
const VALID_TABS = [
  "overview", "macro", "fx-intelligence", "risk-decomposition",
  "economic-structure", "forecasts", "news", "events", "debt",
];
```

- [ ] **Step 4: Add tab definition**

In the `tabs: TabDef[]` array, add after the `"events"` entry:

```tsx
    { id: "debt", label: "Debt Intelligence" },
```

- [ ] **Step 5: Add `TabPanel`**

After the closing `</TabPanel>` for events, add:

```tsx
      <TabPanel id="debt" activeTab={activeTab}>
        <DebtIntelligenceTab
          iso3={country.iso3}
          data={debtProfile}
        />
      </TabPanel>
```

- [ ] **Step 6: Wire `debt_profile` through `CountryProfile.tsx`**

`debt_profile` is a top-level key on the bundle response, NOT inside `country`. In `apps/web/src/routes/CountryProfile.tsx`:

Add to the local `CountryBundle` interface (around line 115):
```tsx
  debt_profile: any | null;
```

Update the destructure at line 212:
```tsx
const { country, macro, ratings, fx, debt_profile } = data;
```

Update the `<CountryProfileTabs>` call (around line 410):
```tsx
<CountryProfileTabs
  country={country}
  macro={macro}
  synopsisData={synopsisData ?? null}
  fx={fx}
  debtProfile={debt_profile ?? null}
/>
```

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd /Users/bird/Documents/ATLAS/atlas/apps/web
pnpm tsc --noEmit 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/routes/country-profile/CountryProfileTabs.tsx
git commit -m "feat: register Debt Intelligence tab in country profile"
```

---

## Task 12: Final verification

- [ ] **Step 1: Run the full API test suite**

```bash
cd /Users/bird/Documents/ATLAS/atlas/apps/api
uv run pytest tests/test_bundle_service.py tests/test_bundle_endpoint.py -v
```

Expected: all tests PASS.

- [ ] **Step 2: Start the dev server and spot-check**

```bash
cd /Users/bird/Documents/ATLAS/atlas
pnpm --filter web dev &
# then run the seeder against a local dev DB to populate debt_profile
uv run --directory apps/api python scripts/seed_debt_profiles.py
```

Navigate to a country profile page for GHA, KEN, ZMB, ETH, or EGY and click the "Debt Intelligence" tab. Verify:
- Headline metrics show numbers (not dashes)
- AI Commentary section is visible and expanded by default (shows placeholder text since `ai_commentary` is null)
- Composition bars render
- Maturity bar chart renders with <1yr bar highlighted amber for GHA and EGY
- Vulnerability flags show correct ⚠ / ✓ per country
- "Open Scenarios" link is present

For a country without a seeded debt profile, verify the tab shows the "not yet available" placeholder without crashing.

- [ ] **Step 3: Commit any final fixes, then summary commit**

```bash
git add -p  # stage only intentional changes
git commit -m "feat: debt intelligence tab — wire-up and final fixes"
```
