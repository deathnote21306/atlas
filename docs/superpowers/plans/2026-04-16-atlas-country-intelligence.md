# Atlas Country Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A logged-in analyst can browse to `/countries`, pick one of the 10 sovereigns, and see a populated country profile with macro grid, FX section, ratings, composite score, risk decomposition, and freshness badges — all rendering real data from Plan 2's ingested vintages. Synopsis + news slots render empty-state placeholders until Plan 4.

**Architecture:** Adds a single bundle endpoint `GET /api/countries/{iso3}/bundle` that composes Plan 2's read paths + a new deterministic Risk Score (6-dimension) + staleness assessment into one response. Four new design-system primitives (`StalenessChip`, `RatingBadge`, `RiskGauge`, `InstitutionalTable`) built on the Plan 1 Tailwind preset. Two new React pages (`/countries` list + `/countries/:iso3` profile) consume the bundle via TanStack Query with 5-min stale time. A shared top nav unifies Home / Countries / Logout. A new `POST /api/auth/logout` clears the session cookie. Synopsis + news are rendered as placeholder sections gated on data that arrives in Plan 4.

**Tech Stack:** FastAPI bundle endpoint (existing stack); React + TanStack Query + react-router-dom (existing); Tailwind utilities from `@atlas/design-system/tailwind-preset`; vitest + testing-library for all new components.

---

## File Structure

Files created (C) or modified (M):

```
atlas/
├── apps/api/
│   ├── src/atlas_api/
│   │   ├── main.py                                            (M) wire auth logout — already includes auth router, so no change
│   │   ├── routers/
│   │   │   ├── auth.py                                        (M) add POST /api/auth/logout
│   │   │   └── countries.py                                   (M) add GET /{iso3}/bundle
│   │   └── services/
│   │       └── country/
│   │           ├── bundle.py                                  (C) get_country_bundle composition
│   │           ├── risk_score.py                              (C) pure 6-dim deterministic risk
│   │           └── staleness.py                               (C) freshness classifier (missing/fresh/yellow/red)
│   └── tests/
│       ├── test_risk_score.py                                 (C) golden scenarios across 10 countries
│       ├── test_staleness.py                                  (C) threshold tests
│       ├── test_bundle.py                                     (C) integration: seed macro/fx/ratings, hit endpoint
│       └── test_auth_logout.py                                (C) logout clears cookie
│
├── packages/schemas/
│   ├── src/atlas_schemas/
│   │   ├── __init__.py                                        (M) export new bundle types
│   │   ├── risk.py                                            (C) RiskDimension enum + RiskScore model
│   │   ├── staleness.py                                       (C) StalenessState enum + StalenessInfo model
│   │   └── bundle.py                                          (C) CountryBundle + MacroTile + FxSection + RatingsSection schemas
│   └── tests/
│       └── test_contracts.py                                  (M) add schema roundtrip tests
│
├── packages/design-system/
│   ├── src/
│   │   ├── index.ts                                           (M) export new primitives
│   │   └── primitives/
│   │       ├── StalenessChip.tsx                              (C)
│   │       ├── RatingBadge.tsx                                (C)
│   │       ├── RiskGauge.tsx                                  (C)
│   │       └── InstitutionalTable.tsx                         (C)
│   └── tests/
│       ├── StalenessChip.test.tsx                             (C)
│       ├── RatingBadge.test.tsx                               (C)
│       ├── RiskGauge.test.tsx                                 (C)
│       └── InstitutionalTable.test.tsx                        (C)
│
└── apps/web/
    ├── src/
    │   ├── App.tsx                                            (M) add /countries and /countries/:iso3 routes
    │   ├── auth/AuthContext.tsx                               (M) add logout() that POSTs /api/auth/logout
    │   ├── components/
    │   │   └── TopNav.tsx                                     (C) nav bar shown on authed pages
    │   └── routes/
    │       ├── Home.tsx                                       (M) wrap in <AppShell>
    │       ├── CountriesList.tsx                              (C) list + filter + search page
    │       ├── CountryProfile.tsx                             (C) detail page
    │       └── AppShell.tsx                                   (C) layout wrapper with TopNav
    └── tests/
        ├── TopNav.test.tsx                                    (C)
        ├── CountriesList.test.tsx                             (C)
        └── CountryProfile.test.tsx                            (C)
```

---

## Design decisions locked in this plan

1. **Bundle endpoint is separate from the simple country endpoint.**
   - `GET /api/countries/{iso3}` keeps returning the lightweight reference row (Plan 2 contract — unchanged).
   - `GET /api/countries/{iso3}/bundle` returns the composite for the profile page.
   - Rationale: list page uses the light endpoint; profile page uses bundle. Separation avoids always-paying the composition cost.

2. **Risk Score is deterministic, 6 dimensions, 0–100 total.** Thresholds are hand-picked for the 10 prototype countries and locked in golden tests. Not intended to match any published sovereign methodology — the prototype's job is to demonstrate the informational loop, not to out-rate S&P.

3. **Staleness is computed from `macro_indicator_vintage.ingested_at`** per country:
   - `missing` — no rows at all for that indicator
   - `fresh` — ingested within the last 6 months
   - `yellow` — 6–12 months old
   - `red` — >12 months old

4. **Logout is minimal.** `POST /api/auth/logout` clears the `atlas_session` cookie with an expired `Set-Cookie` header. No CSRF token on logout — same-site lax cookie is sufficient for a single-demo-user prototype.

5. **Synopsis + news placeholders.** The spec says the profile has an exec synopsis and a news items section. Plan 4 builds the AI + news pipeline. For Plan 3, both sections render a subtle empty state ("AI synopsis pending review", "No scored news yet") so the page doesn't look broken.

6. **No Playwright setup in this plan.** Plan 1 deferred it; Plan 4 or 5 will install it when PDF rendering needs it. Until then, a manual browser smoke checklist in Task 13 is the acceptance test.

7. **Country ordering on the list page is iso3 ASC** (Plan 2's `list_countries` default). Client-side search filters by iso3 + name substring, case-insensitive. Filter chips: region (West Africa / East Africa / Southern Africa / North Africa) + status (all / performing / negotiating / restructured / distressed).

---

## Risk Score — the 6 dimensions

Each dimension returns a 0–10 score (0 = lowest risk, 10 = highest). The composite is `round(mean(dims) * 10, 1)` → a 0–100 scale.

| Dimension | Input indicator | Score 1 | Score 3 | Score 5 | Score 7 | Score 9 | Special |
|---|---|---|---|---|---|---|---|
| Debt Burden | `PUBLIC_DEBT_PCT_GDP` | <30 | 30–50 | 50–70 | 70–90 | ≥90 | Distressed status → auto 10 |
| External Liquidity | `FX_RESERVES_MO_IMPORTS` | >6 | 4–6 | 3–4 | 2–3 | <2 | Missing → 5 |
| Fiscal Flexibility | `FISCAL_BALANCE_PCT_GDP` | >2 | 0–2 | −2–0 | −5 to −2 | <−5 | Missing → 5 |
| Growth Momentum | `GDP_GROWTH_PCT` | >5 | 3–5 | 1–3 | −1–1 | <−1 | Missing → 5 |
| Inflation Pressure | `INFLATION_PCT` | <5 | 5–10 | 10–20 | 20–40 | ≥40 | Missing → 5 |
| FX Stability | `abs(fx_delta_30d_pct)` | <2 | 2–5 | 5–10 | 10–20 | ≥20 | Missing → regime heuristic (see code) |

"Distressed" means `country.status in {selective_default, default, restructured}`.

Scores between bracket boundaries use the nearest odd integer (1/3/5/7/9). Even scores (2/4/6/8) are reserved for future manual overrides and do not occur in the deterministic path.

---

### Task 1: Bundle schemas + TS codegen

**Files:**
- Create: `packages/schemas/src/atlas_schemas/staleness.py`
- Create: `packages/schemas/src/atlas_schemas/risk.py`
- Create: `packages/schemas/src/atlas_schemas/bundle.py`
- Modify: `packages/schemas/src/atlas_schemas/__init__.py`
- Modify: `packages/schemas/tests/test_contracts.py`

- [ ] **Step 1: Write `staleness.py`**

```python
# packages/schemas/src/atlas_schemas/staleness.py
from enum import StrEnum

from pydantic import BaseModel


class StalenessState(StrEnum):
    MISSING = "missing"
    FRESH = "fresh"
    YELLOW = "yellow"
    RED = "red"


class StalenessInfo(BaseModel):
    state: StalenessState
    age_days: int | None
```

- [ ] **Step 2: Write `risk.py`**

```python
# packages/schemas/src/atlas_schemas/risk.py
from enum import StrEnum

from pydantic import BaseModel


class RiskDimension(StrEnum):
    DEBT_BURDEN = "debt_burden"
    EXTERNAL_LIQUIDITY = "external_liquidity"
    FISCAL_FLEXIBILITY = "fiscal_flexibility"
    GROWTH_MOMENTUM = "growth_momentum"
    INFLATION_PRESSURE = "inflation_pressure"
    FX_STABILITY = "fx_stability"


class DimensionScore(BaseModel):
    dimension: RiskDimension
    score: int                         # 0-10
    rationale: str
    input_value: float | None
    is_estimate: bool = False


class RiskScore(BaseModel):
    composite: float                   # 0.0-100.0
    dimensions: list[DimensionScore]
```

- [ ] **Step 3: Write `bundle.py`**

```python
# packages/schemas/src/atlas_schemas/bundle.py
from pydantic import BaseModel

from atlas_schemas.country import Country
from atlas_schemas.fx import FxDeltas
from atlas_schemas.macro import MacroIndicator
from atlas_schemas.ratings import RatingAction
from atlas_schemas.risk import RiskScore
from atlas_schemas.staleness import StalenessInfo


class MacroTile(BaseModel):
    indicator: MacroIndicator
    label: str
    value: float | None
    period: str | None
    source: str | None
    staleness: StalenessInfo


class RatingsSection(BaseModel):
    latest_per_agency: dict[str, RatingAction]     # {"S&P": RatingAction, ...}
    composite_score: float | None                   # 0-21 weighted ladder
    history: list[RatingAction]                     # most recent first


class CountryBundle(BaseModel):
    country: Country
    macro: list[MacroTile]
    fx: FxDeltas | None
    ratings: RatingsSection
    risk: RiskScore
    synopsis: str | None = None                     # Plan 4 will populate
    news_placeholder: bool = True                   # Plan 4 flips to False
```

- [ ] **Step 4: Update `__init__.py`**

```python
# packages/schemas/src/atlas_schemas/__init__.py
from atlas_schemas.auth import LoginRequest, LoginResponse, Me
from atlas_schemas.bundle import CountryBundle, MacroTile, RatingsSection
from atlas_schemas.country import Country, CountryStatus, FxRegime
from atlas_schemas.fx import FxDeltas, FxObservation
from atlas_schemas.health import HealthResponse
from atlas_schemas.ingestion import DataVintage, IngestionReport, SourceStats
from atlas_schemas.macro import MacroIndicator, MacroValue
from atlas_schemas.ratings import Agency, RatingAction
from atlas_schemas.risk import DimensionScore, RiskDimension, RiskScore
from atlas_schemas.staleness import StalenessInfo, StalenessState

__all__ = [
    "Agency",
    "Country",
    "CountryBundle",
    "CountryStatus",
    "DataVintage",
    "DimensionScore",
    "FxDeltas",
    "FxObservation",
    "FxRegime",
    "HealthResponse",
    "IngestionReport",
    "LoginRequest",
    "LoginResponse",
    "MacroIndicator",
    "MacroTile",
    "MacroValue",
    "Me",
    "RatingAction",
    "RatingsSection",
    "RiskDimension",
    "RiskScore",
    "SourceStats",
    "StalenessInfo",
    "StalenessState",
]
```

- [ ] **Step 5: Add contract tests**

Append to `packages/schemas/tests/test_contracts.py`:

```python
def test_staleness_info_schema():
    from atlas_schemas.staleness import StalenessInfo, StalenessState
    s = StalenessInfo.model_validate({"state": "yellow", "age_days": 200})
    assert s.state is StalenessState.YELLOW
    assert s.age_days == 200

    s_missing = StalenessInfo.model_validate({"state": "missing", "age_days": None})
    assert s_missing.state is StalenessState.MISSING
    assert s_missing.age_days is None


def test_dimension_score_schema():
    from atlas_schemas.risk import DimensionScore, RiskDimension
    d = DimensionScore.model_validate({
        "dimension": "debt_burden", "score": 7, "rationale": "debt 85% of GDP",
        "input_value": 85.0, "is_estimate": False,
    })
    assert d.dimension is RiskDimension.DEBT_BURDEN
    assert d.score == 7


def test_country_bundle_shape():
    from atlas_schemas.bundle import CountryBundle
    payload = {
        "country": {
            "iso3": "GHA", "name": "Ghana", "capital": "Accra", "region": "West Africa",
            "tags": ["SSA"], "tier": "C", "status": "restructured", "fx_regime": "float",
            "fx_regime_notes": None, "fx_parallel_premium": None,
        },
        "macro": [],
        "fx": None,
        "ratings": {"latest_per_agency": {}, "composite_score": None, "history": []},
        "risk": {"composite": 50.0, "dimensions": []},
        "synopsis": None,
        "news_placeholder": True,
    }
    b = CountryBundle.model_validate(payload)
    assert b.country.iso3 == "GHA"
    assert b.risk.composite == 50.0
```

- [ ] **Step 6: Run + regen TS**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv run pytest packages/schemas/tests/ -v
PATH="$PWD/node_modules/.bin:$PATH" uv run python packages/schemas/scripts/generate_ts.py
grep -q "CountryBundle" apps/web/src/types/generated.ts && echo OK
grep -q "RiskDimension" apps/web/src/types/generated.ts && echo OK
```

Expected: 11 passing (8 prior + 3 new); `OK` `OK`.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add packages/schemas
git commit -m "feat(schemas): add country bundle + risk + staleness contracts"
```

Expected: ruff + mypy clean.

---

### Task 2: Risk Score pure function + golden tests

**Files:**
- Create: `apps/api/src/atlas_api/services/country/risk_score.py`
- Create: `apps/api/tests/test_risk_score.py`

- [ ] **Step 1: Write failing golden tests**

```python
# apps/api/tests/test_risk_score.py
"""Golden tests for the 6-dimension Risk Score. Values locked at 2026-04-16."""

import pytest

from atlas_api.services.country.risk_score import (
    bucket_score,
    compute_risk_score,
)


# --- Threshold bucket unit tests ---------------------------------------------

@pytest.mark.parametrize(
    "value,brackets,expected",
    [
        # Debt burden: lower = better, bracket list is ascending-bad.
        (20.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 1),
        (40.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 3),
        (60.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 5),
        (80.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 7),
        (95.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 9),
        # Boundary: exactly 30 falls into the second bracket.
        (30.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 3),
    ],
)
def test_bucket_score(value: float, brackets: list[tuple[float, int]], expected: int):
    assert bucket_score(value, brackets) == expected


# --- Golden scenarios: one canonical set of inputs per country ---------------
#
# Inputs reflect late-2024 / early-2025 macro snapshot; locked for reproducibility.
# Each country lists: (iso3, status, {indicator: value}, fx_delta_30d, expected_composite)

GOLDEN_SCENARIOS: list[tuple[str, str, dict[str, float], float | None, float]] = [
    # Ghana — restructured, high debt, inflation still elevated.
    ("GHA", "restructured",
     {"PUBLIC_DEBT_PCT_GDP": 83.0, "FX_RESERVES_MO_IMPORTS": 3.1,
      "FISCAL_BALANCE_PCT_GDP": -4.5, "GDP_GROWTH_PCT": 3.1,
      "INFLATION_PCT": 22.0},
     -8.0,
     # Debt=10 (distressed auto), Liq=5, Fiscal=7, Growth=5, Inflation=7, FX=5
     round((10+5+7+5+7+5)/6 * 10, 1)),  # 65.0

    # Kenya — performing, moderate fiscal strain.
    ("KEN", "performing",
     {"PUBLIC_DEBT_PCT_GDP": 73.0, "FX_RESERVES_MO_IMPORTS": 4.2,
      "FISCAL_BALANCE_PCT_GDP": -5.5, "GDP_GROWTH_PCT": 5.4,
      "INFLATION_PCT": 6.5},
     -1.5,
     # Debt=7, Liq=3, Fiscal=9, Growth=3, Inflation=3, FX=1
     round((7+3+9+3+3+1)/6 * 10, 1)),  # 43.3

    # Côte d'Ivoire — performing, stable WAEMU peg, strong growth.
    ("CIV", "performing",
     {"PUBLIC_DEBT_PCT_GDP": 55.0, "FX_RESERVES_MO_IMPORTS": 5.0,
      "FISCAL_BALANCE_PCT_GDP": -4.0, "GDP_GROWTH_PCT": 6.5,
      "INFLATION_PCT": 2.5},
     0.0,
     # Debt=5, Liq=3, Fiscal=7, Growth=1, Inflation=1, FX=1
     round((5+3+7+1+1+1)/6 * 10, 1)),  # 30.0

    # Ethiopia — selective default, high everything.
    ("ETH", "selective_default",
     {"PUBLIC_DEBT_PCT_GDP": 38.0, "FX_RESERVES_MO_IMPORTS": 1.5,
      "FISCAL_BALANCE_PCT_GDP": -3.2, "GDP_GROWTH_PCT": 6.1,
      "INFLATION_PCT": 25.0},
     -25.0,
     # Debt=10 (distressed), Liq=9, Fiscal=7, Growth=1, Inflation=7, FX=9
     round((10+9+7+1+7+9)/6 * 10, 1)),  # 71.7

    # South Africa — performing, large economy.
    ("ZAF", "performing",
     {"PUBLIC_DEBT_PCT_GDP": 74.0, "FX_RESERVES_MO_IMPORTS": 4.5,
      "FISCAL_BALANCE_PCT_GDP": -4.8, "GDP_GROWTH_PCT": 1.1,
      "INFLATION_PCT": 5.3},
     -3.0,
     # Debt=7, Liq=3, Fiscal=7, Growth=5, Inflation=3, FX=3
     round((7+3+7+5+3+3)/6 * 10, 1)),  # 46.7
]


@pytest.mark.parametrize("iso3,status,indicators,fx_delta,expected", GOLDEN_SCENARIOS)
def test_risk_score_golden(
    iso3: str, status: str, indicators: dict[str, float],
    fx_delta: float | None, expected: float,
):
    result = compute_risk_score(
        status=status, indicators=indicators, fx_delta_30d_pct=fx_delta
    )
    assert result.composite == pytest.approx(expected), (
        f"{iso3}: expected {expected}, got {result.composite}, dims={[(d.dimension.value, d.score) for d in result.dimensions]}"
    )


def test_risk_score_handles_all_missing():
    """Nothing but status → every dimension falls back to its default (5/10)."""
    result = compute_risk_score(status="performing", indicators={}, fx_delta_30d_pct=None)
    assert result.composite == pytest.approx(round(5 * 10, 1))  # 50.0
    assert len(result.dimensions) == 6
    assert all(d.is_estimate for d in result.dimensions)


def test_risk_score_distressed_auto_debt_max():
    """Distressed countries get Debt Burden = 10 regardless of the debt number."""
    result = compute_risk_score(
        status="restructured",
        indicators={"PUBLIC_DEBT_PCT_GDP": 10.0},  # absurdly low
        fx_delta_30d_pct=0.0,
    )
    debt = next(d for d in result.dimensions if d.dimension.value == "debt_burden")
    assert debt.score == 10


def test_risk_score_dimensions_are_ordered_canonically():
    """Stable ordering: debt, liquidity, fiscal, growth, inflation, fx."""
    result = compute_risk_score(status="performing", indicators={}, fx_delta_30d_pct=None)
    order = [d.dimension.value for d in result.dimensions]
    assert order == [
        "debt_burden", "external_liquidity", "fiscal_flexibility",
        "growth_momentum", "inflation_pressure", "fx_stability",
    ]
```

- [ ] **Step 2: Implement `risk_score.py`**

```python
# apps/api/src/atlas_api/services/country/risk_score.py
"""Deterministic 6-dimension sovereign risk score.

Takes raw macro indicator values + country status + FX delta; returns a
composite score on a 0–100 scale plus per-dimension breakdowns. Hand-tuned
thresholds locked via golden tests in test_risk_score.py. Not a replacement
for agency ratings — internal risk sense-check only.
"""

from atlas_schemas.risk import DimensionScore, RiskDimension, RiskScore

Bracket = tuple[float, int]

# Lower input → lower score. Each bracket's upper bound is exclusive of the next.
_DEBT_BRACKETS: list[Bracket] = [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)]
_FISCAL_BRACKETS: list[Bracket] = [(-5, 9), (-2, 7), (0, 5), (2, 3), (float("inf"), 1)]
_GROWTH_BRACKETS: list[Bracket] = [(-1, 9), (1, 7), (3, 5), (5, 3), (float("inf"), 1)]
_INFLATION_BRACKETS: list[Bracket] = [(5, 1), (10, 3), (20, 5), (40, 7), (float("inf"), 9)]
_LIQUIDITY_BRACKETS_LOWER_IS_WORSE: list[Bracket] = [(2, 9), (3, 7), (4, 5), (6, 3), (float("inf"), 1)]
_FX_BRACKETS: list[Bracket] = [(2, 1), (5, 3), (10, 5), (20, 7), (float("inf"), 9)]

_DISTRESSED = {"selective_default", "default", "restructured"}


def bucket_score(value: float, brackets: list[Bracket]) -> int:
    """Return the score for the first bracket whose upper-bound is > value."""
    for upper, score in brackets:
        if value < upper:
            return score
    return brackets[-1][1]


def compute_risk_score(
    status: str,
    indicators: dict[str, float],
    fx_delta_30d_pct: float | None,
) -> RiskScore:
    dimensions: list[DimensionScore] = []

    # 1. Debt Burden
    debt = indicators.get("PUBLIC_DEBT_PCT_GDP")
    if status in _DISTRESSED:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.DEBT_BURDEN, score=10,
            rationale=f"country status {status!r} → auto max",
            input_value=debt, is_estimate=False,
        ))
    elif debt is None:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.DEBT_BURDEN, score=5,
            rationale="no public debt data", input_value=None, is_estimate=True,
        ))
    else:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.DEBT_BURDEN,
            score=bucket_score(debt, _DEBT_BRACKETS),
            rationale=f"public debt {debt:.1f}% of GDP",
            input_value=debt, is_estimate=False,
        ))

    # 2. External Liquidity (reserves in months of imports; lower = worse)
    reserves = indicators.get("FX_RESERVES_MO_IMPORTS")
    if reserves is None:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.EXTERNAL_LIQUIDITY, score=5,
            rationale="no reserves data", input_value=None, is_estimate=True,
        ))
    else:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.EXTERNAL_LIQUIDITY,
            score=bucket_score(reserves, _LIQUIDITY_BRACKETS_LOWER_IS_WORSE),
            rationale=f"reserves {reserves:.1f} months of imports",
            input_value=reserves, is_estimate=False,
        ))

    # 3. Fiscal Flexibility (balance % GDP; more negative = worse)
    fiscal = indicators.get("FISCAL_BALANCE_PCT_GDP")
    if fiscal is None:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.FISCAL_FLEXIBILITY, score=5,
            rationale="no fiscal balance data", input_value=None, is_estimate=True,
        ))
    else:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.FISCAL_FLEXIBILITY,
            score=bucket_score(fiscal, _FISCAL_BRACKETS),
            rationale=f"fiscal balance {fiscal:+.1f}% of GDP",
            input_value=fiscal, is_estimate=False,
        ))

    # 4. Growth Momentum (% YoY; higher = better)
    growth = indicators.get("GDP_GROWTH_PCT")
    if growth is None:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.GROWTH_MOMENTUM, score=5,
            rationale="no GDP growth data", input_value=None, is_estimate=True,
        ))
    else:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.GROWTH_MOMENTUM,
            score=bucket_score(growth, _GROWTH_BRACKETS),
            rationale=f"GDP growth {growth:+.1f}%",
            input_value=growth, is_estimate=False,
        ))

    # 5. Inflation Pressure
    inflation = indicators.get("INFLATION_PCT")
    if inflation is None:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.INFLATION_PRESSURE, score=5,
            rationale="no inflation data", input_value=None, is_estimate=True,
        ))
    else:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.INFLATION_PRESSURE,
            score=bucket_score(inflation, _INFLATION_BRACKETS),
            rationale=f"CPI inflation {inflation:.1f}% YoY",
            input_value=inflation, is_estimate=False,
        ))

    # 6. FX Stability (absolute 30-day % delta)
    if fx_delta_30d_pct is None:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.FX_STABILITY, score=5,
            rationale="no recent FX data", input_value=None, is_estimate=True,
        ))
    else:
        abs_delta = abs(fx_delta_30d_pct)
        dimensions.append(DimensionScore(
            dimension=RiskDimension.FX_STABILITY,
            score=bucket_score(abs_delta, _FX_BRACKETS),
            rationale=f"30d FX move {fx_delta_30d_pct:+.1f}%",
            input_value=fx_delta_30d_pct, is_estimate=False,
        ))

    composite = round(sum(d.score for d in dimensions) / len(dimensions) * 10, 1)
    return RiskScore(composite=composite, dimensions=dimensions)
```

- [ ] **Step 3: Run**

```bash
uv run pytest apps/api/tests/test_risk_score.py -v
```

Expected: all 15 tests pass (6 bucket_score cases + 5 golden countries + 3 edge cases + 1 ordering).

- [ ] **Step 4: Lint + commit**

```bash
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/services/country/risk_score.py apps/api/tests/test_risk_score.py
git commit -m "feat(api): deterministic 6-dimension risk score"
```

---

### Task 3: Staleness helper

**Files:**
- Create: `apps/api/src/atlas_api/services/country/staleness.py`
- Create: `apps/api/tests/test_staleness.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/api/tests/test_staleness.py
from datetime import UTC, datetime, timedelta

from atlas_api.services.country.staleness import classify_staleness
from atlas_schemas.staleness import StalenessState


NOW = datetime(2026, 4, 16, tzinfo=UTC)


def test_missing_when_ingested_at_is_none():
    info = classify_staleness(None, now=NOW)
    assert info.state is StalenessState.MISSING
    assert info.age_days is None


def test_fresh_when_under_6_months():
    info = classify_staleness(NOW - timedelta(days=30), now=NOW)
    assert info.state is StalenessState.FRESH
    assert info.age_days == 30


def test_yellow_between_6_and_12_months():
    info = classify_staleness(NOW - timedelta(days=200), now=NOW)
    assert info.state is StalenessState.YELLOW
    assert info.age_days == 200


def test_red_after_12_months():
    info = classify_staleness(NOW - timedelta(days=400), now=NOW)
    assert info.state is StalenessState.RED
    assert info.age_days == 400


def test_boundary_exact_6_months_is_yellow():
    """Spec: yellow starts at 6 months (>180 days)."""
    info = classify_staleness(NOW - timedelta(days=181), now=NOW)
    assert info.state is StalenessState.YELLOW


def test_boundary_exact_12_months_is_red():
    info = classify_staleness(NOW - timedelta(days=366), now=NOW)
    assert info.state is StalenessState.RED
```

- [ ] **Step 2: Implement**

```python
# apps/api/src/atlas_api/services/country/staleness.py
"""Staleness classifier per spec §8. Age thresholds: fresh <=180d, yellow 181-365d, red >365d."""

from datetime import UTC, datetime

from atlas_schemas.staleness import StalenessInfo, StalenessState

FRESH_MAX_DAYS = 180
YELLOW_MAX_DAYS = 365


def classify_staleness(ingested_at: datetime | None, now: datetime | None = None) -> StalenessInfo:
    if ingested_at is None:
        return StalenessInfo(state=StalenessState.MISSING, age_days=None)
    ref = now or datetime.now(UTC)
    age = (ref - ingested_at).days
    if age <= FRESH_MAX_DAYS:
        state = StalenessState.FRESH
    elif age <= YELLOW_MAX_DAYS:
        state = StalenessState.YELLOW
    else:
        state = StalenessState.RED
    return StalenessInfo(state=state, age_days=age)
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest apps/api/tests/test_staleness.py -v
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/services/country/staleness.py apps/api/tests/test_staleness.py
git commit -m "feat(api): staleness classifier"
```

Expected: 6 passing.

---

### Task 4: Bundle service composition

**Files:**
- Create: `apps/api/src/atlas_api/services/country/bundle.py`
- Create: `apps/api/tests/test_bundle_service.py`

- [ ] **Step 1: Write failing tests (unit-level, minimal DB touch)**

```python
# apps/api/tests/test_bundle_service.py
"""Tests for the bundle-assembly function. DB-integration test lives in test_bundle.py."""

import uuid
from datetime import UTC, date, datetime

from atlas_api.models import (
    Country, DataVintage, FxRate, MacroIndicatorVintage, RatingHistory,
)
from atlas_api.services.country.bundle import get_country_bundle


def _seed_gha(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v


def test_bundle_missing_everything_returns_country_only(session):
    _seed_gha(session)
    b = get_country_bundle(session, "GHA")
    assert b is not None
    assert b.country.iso3 == "GHA"
    # Macro grid always has 12 tiles; all missing here.
    assert len(b.macro) == 12
    assert all(t.value is None for t in b.macro)
    assert b.fx is None
    assert b.ratings.latest_per_agency == {}
    assert b.ratings.composite_score is None
    assert b.risk.composite == 50.0   # all dims neutral (5) → 50
    assert b.synopsis is None
    assert b.news_placeholder is True


def test_bundle_unknown_country_returns_none(session):
    assert get_country_bundle(session, "ZZZ") is None


def test_bundle_populates_macro_and_fx(session):
    v = _seed_gha(session)
    session.add_all([
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="PUBLIC_DEBT_PCT_GDP",
            period="2024", value=83.0, source="worldbank",
            source_date=date(2024, 12, 31), vintage_id=v.id,
        ),
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="INFLATION_PCT",
            period="2024", value=22.0, source="worldbank",
            source_date=date(2024, 12, 31), vintage_id=v.id,
        ),
        FxRate(
            id=uuid.uuid4(), iso3="GHA", ccy="GHS", usd_per_ccy=1 / 15.0,
            observation_date=date(2026, 4, 16), source="exchangerate.host",
        ),
    ])
    session.commit()

    b = get_country_bundle(session, "GHA")
    assert b is not None
    debt = next(t for t in b.macro if t.indicator.value == "PUBLIC_DEBT_PCT_GDP")
    assert debt.value == 83.0
    assert debt.period == "2024"
    assert debt.source == "worldbank"
    inflation = next(t for t in b.macro if t.indicator.value == "INFLATION_PCT")
    assert inflation.value == 22.0
    assert b.fx is not None
    assert b.fx.latest.ccy == "GHS"


def test_bundle_populates_ratings(session):
    _seed_gha(session)
    session.add_all([
        RatingHistory(
            id=uuid.uuid4(), iso3="GHA", agency="S&P", rating="CCC+",
            outlook="stable", action="upgrade", action_date=date(2024, 5, 1),
        ),
        RatingHistory(
            id=uuid.uuid4(), iso3="GHA", agency="Moodys", rating="Caa3",
            outlook="stable", action="affirm", action_date=date(2024, 6, 1),
        ),
    ])
    session.commit()

    b = get_country_bundle(session, "GHA")
    assert b is not None
    assert set(b.ratings.latest_per_agency.keys()) == {"S&P", "Moodys"}
    assert b.ratings.latest_per_agency["S&P"].rating == "CCC+"
    assert b.ratings.composite_score is not None
    assert len(b.ratings.history) == 2
```

- [ ] **Step 2: Implement**

```python
# apps/api/src/atlas_api/services/country/bundle.py
"""Compose the country detail bundle from stored reads + calculated metrics."""

from sqlalchemy.orm import Session

from atlas_api.models import Country
from atlas_api.services.country.composite_rating import composite_score
from atlas_api.services.country.queries import (
    compute_fx_deltas,
    get_country,
    get_latest,
    get_latest_fx,
    get_rating_history,
)
from atlas_api.services.country.risk_score import compute_risk_score
from atlas_api.services.country.staleness import classify_staleness
from atlas_schemas.bundle import CountryBundle, MacroTile, RatingsSection
from atlas_schemas.country import Country as CountrySchema
from atlas_schemas.fx import FxDeltas, FxObservation
from atlas_schemas.macro import MacroIndicator
from atlas_schemas.ratings import RatingAction

_TILE_LABELS: dict[MacroIndicator, str] = {
    MacroIndicator.GDP_USD: "GDP (USD, current)",
    MacroIndicator.GDP_GROWTH_PCT: "GDP growth (% YoY)",
    MacroIndicator.INFLATION_PCT: "Inflation (CPI % YoY)",
    MacroIndicator.CURRENT_ACCOUNT_PCT_GDP: "Current account (% GDP)",
    MacroIndicator.FISCAL_BALANCE_PCT_GDP: "Fiscal balance (% GDP)",
    MacroIndicator.PUBLIC_DEBT_PCT_GDP: "Public debt (% GDP)",
    MacroIndicator.EXTERNAL_DEBT_PCT_GNI: "External debt (% GNI)",
    MacroIndicator.FX_RESERVES_MO_IMPORTS: "Reserves (months of imports)",
    MacroIndicator.DEBT_SERVICE_PCT_EXPORTS: "Debt service (% exports)",
    MacroIndicator.UNEMPLOYMENT_PCT: "Unemployment (%)",
    MacroIndicator.FDI_INFLOW_USD: "FDI inflow (USD)",
    MacroIndicator.GDP_PER_CAPITA_USD: "GDP per capita (USD)",
}


def _macro_tiles(session: Session, iso3: str) -> list[MacroTile]:
    tiles: list[MacroTile] = []
    for indicator, label in _TILE_LABELS.items():
        row = get_latest(session, iso3, indicator.value)
        tiles.append(MacroTile(
            indicator=indicator,
            label=label,
            value=float(row.value) if row is not None and row.value is not None else None,
            period=row.period if row is not None else None,
            source=row.source if row is not None else None,
            staleness=classify_staleness(row.ingested_at if row is not None else None),
        ))
    return tiles


def _fx_section(session: Session, iso3: str) -> FxDeltas | None:
    latest = get_latest_fx(session, iso3)
    if latest is None:
        return None
    deltas = compute_fx_deltas(session, iso3)
    return FxDeltas(
        latest=FxObservation(
            iso3=latest.iso3,
            ccy=latest.ccy,
            usd_per_ccy=float(latest.usd_per_ccy),
            observation_date=latest.observation_date,
            source=latest.source,
            ingested_at=latest.ingested_at,
        ),
        delta_1d_pct=deltas["delta_1d_pct"],
        delta_7d_pct=deltas["delta_7d_pct"],
        delta_30d_pct=deltas["delta_30d_pct"],
        delta_ytd_pct=deltas["delta_ytd_pct"],
    )


def _ratings_section(session: Session, iso3: str) -> RatingsSection:
    history = get_rating_history(session, iso3)
    latest_per_agency: dict[str, RatingAction] = {}
    for row in history:
        if row.agency not in latest_per_agency:
            latest_per_agency[row.agency] = RatingAction(
                iso3=row.iso3, agency=row.agency, rating=row.rating,
                outlook=row.outlook, action=row.action,
                action_date=row.action_date, source_url=row.source_url,
            )
    rating_dict = {a: r.rating for a, r in latest_per_agency.items()}
    return RatingsSection(
        latest_per_agency=latest_per_agency,
        composite_score=composite_score(rating_dict) if rating_dict else None,
        history=[
            RatingAction(
                iso3=r.iso3, agency=r.agency, rating=r.rating, outlook=r.outlook,
                action=r.action, action_date=r.action_date, source_url=r.source_url,
            ) for r in history
        ],
    )


def get_country_bundle(session: Session, iso3: str) -> CountryBundle | None:
    iso3 = iso3.upper()
    country = get_country(session, iso3)
    if country is None:
        return None

    macro = _macro_tiles(session, iso3)
    fx = _fx_section(session, iso3)
    ratings = _ratings_section(session, iso3)

    # Risk score inputs: current values for the 5 macro indicators + FX delta.
    risk_indicators = {t.indicator.value: t.value for t in macro if t.value is not None}
    risk = compute_risk_score(
        status=country.status.value if hasattr(country.status, "value") else str(country.status),
        indicators=risk_indicators,
        fx_delta_30d_pct=fx.delta_30d_pct if fx is not None else None,
    )

    return CountryBundle(
        country=CountrySchema.model_validate(country, from_attributes=True),
        macro=macro,
        fx=fx,
        ratings=ratings,
        risk=risk,
        synopsis=None,
        news_placeholder=True,
    )
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest apps/api/tests/test_bundle_service.py -v
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/services/country/bundle.py apps/api/tests/test_bundle_service.py
git commit -m "feat(api): assemble country bundle from reads"
```

Expected: 4 passing.

---

### Task 5: Bundle endpoint

**Files:**
- Modify: `apps/api/src/atlas_api/routers/countries.py`
- Create: `apps/api/tests/test_bundle_endpoint.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/api/tests/test_bundle_endpoint.py
import uuid
from datetime import UTC, date, datetime

from atlas_api.models import (
    Country, DataVintage, MacroIndicatorVintage, RatingHistory, User,
)
from atlas_api.security import hash_password


def _seed_user(session):
    session.add(User(
        id=uuid.uuid4(), email="a@b.test",
        password_hash=hash_password("pw-123456"), role="Analyst",
    ))
    session.commit()


def _seed_gha_with_data(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.add(MacroIndicatorVintage(
        id=uuid.uuid4(), iso3="GHA", indicator="PUBLIC_DEBT_PCT_GDP",
        period="2024", value=83.0, source="worldbank",
        source_date=date(2024, 12, 31), vintage_id=v.id,
    ))
    session.add(RatingHistory(
        id=uuid.uuid4(), iso3="GHA", agency="S&P", rating="CCC+",
        outlook="stable", action="upgrade", action_date=date(2024, 5, 1),
    ))
    session.commit()


def _login(client):
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert r.status_code == 200


def test_bundle_requires_auth(client):
    r = client.get("/api/countries/GHA/bundle")
    assert r.status_code == 401


def test_bundle_returns_full_shape(client, session):
    _seed_user(session)
    _seed_gha_with_data(session)
    _login(client)
    r = client.get("/api/countries/GHA/bundle")
    assert r.status_code == 200
    body = r.json()
    # Country reference
    assert body["country"]["iso3"] == "GHA"
    assert body["country"]["status"] == "restructured"
    # Macro
    assert len(body["macro"]) == 12
    debt = next(t for t in body["macro"] if t["indicator"] == "PUBLIC_DEBT_PCT_GDP")
    assert debt["value"] == 83.0
    assert debt["staleness"]["state"] == "fresh"
    # Ratings
    assert "S&P" in body["ratings"]["latest_per_agency"]
    assert body["ratings"]["composite_score"] is not None
    # Risk
    assert body["risk"]["composite"] >= 0
    assert len(body["risk"]["dimensions"]) == 6
    # Placeholders
    assert body["synopsis"] is None
    assert body["news_placeholder"] is True


def test_bundle_404(client, session):
    _seed_user(session)
    _login(client)
    r = client.get("/api/countries/ZZZ/bundle")
    assert r.status_code == 404


def test_bundle_iso3_case_normalized(client, session):
    _seed_user(session)
    _seed_gha_with_data(session)
    _login(client)
    r = client.get("/api/countries/gha/bundle")
    assert r.status_code == 200
    assert r.json()["country"]["iso3"] == "GHA"
```

- [ ] **Step 2: Extend router**

Edit `apps/api/src/atlas_api/routers/countries.py` — add the bundle endpoint after `get_one`:

```python
# at top of file, add to imports:
from atlas_api.services.country.bundle import get_country_bundle
from atlas_schemas.bundle import CountryBundle

# … existing list_all and get_one stay unchanged …


@router.get("/{iso3}/bundle", response_model=CountryBundle)
def get_bundle(iso3: str, session: DbSession, _: CurrentUser) -> CountryBundle:
    iso3 = iso3.upper()
    bundle = get_country_bundle(session, iso3)
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"country {iso3} not found",
        )
    return bundle
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest apps/api/tests/test_bundle_endpoint.py -v
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/routers/countries.py apps/api/tests/test_bundle_endpoint.py
git commit -m "feat(api): GET /api/countries/{iso3}/bundle endpoint"
```

Expected: 4 passing.

---

### Task 6: Logout endpoint + AuthContext.logout

**Files:**
- Modify: `apps/api/src/atlas_api/routers/auth.py`
- Modify: `apps/api/src/atlas_api/routers/countries.py` — no changes (listed here by mistake, delete from working set)
- Create: `apps/api/tests/test_auth_logout.py`
- Modify: `apps/web/src/auth/AuthContext.tsx`

- [ ] **Step 1: Write failing test**

```python
# apps/api/tests/test_auth_logout.py
import uuid

from atlas_api.models import User
from atlas_api.security import hash_password


def _seed(session):
    session.add(User(
        id=uuid.uuid4(), email="a@b.test",
        password_hash=hash_password("pw-123456"), role="Analyst",
    ))
    session.commit()


def test_logout_clears_cookie(client, session):
    _seed(session)
    login = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert login.status_code == 200
    assert "atlas_session" in login.cookies

    # /api/me should succeed while authed
    assert client.get("/api/me").status_code == 200

    # Logout
    r = client.post("/api/auth/logout")
    assert r.status_code == 204

    # Subsequent /api/me must 401 — cookie is cleared on the client.
    assert client.get("/api/me").status_code == 401


def test_logout_without_session_still_204(client):
    """Idempotent: logging out without a session is a no-op."""
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
```

- [ ] **Step 2: Add endpoint to `auth.py`**

After the existing `@router.get("/me", ...)` handler, add:

```python
from fastapi import Response as FastAPIResponse


@router.post("/auth/logout", status_code=204)
def logout(response: FastAPIResponse) -> FastAPIResponse:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite="lax",
    )
    response.status_code = 204
    return response
```

(If there's already a `Response` import from `fastapi` used by `login`, reuse it instead of aliasing — but watch for conflicts with any local `Response` type.)

- [ ] **Step 3: Extend `AuthContext.tsx`**

Replace the `AuthProvider` implementation in `apps/web/src/auth/AuthContext.tsx` to add a `logout` method:

```tsx
// apps/web/src/auth/AuthContext.tsx
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, api } from "../api/client";

interface Me { email: string; role: string }

interface AuthState {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Me>("/api/me")
      .then(setUser)
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 401)) console.error(e);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await api<Me>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    const me = await api<Me>("/api/me");
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } catch {
      /* best-effort; even if the request fails we clear local state */
    }
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used within AuthProvider");
  return v;
}
```

Note: logout endpoint returns 204 with no JSON body, so we use `fetch` directly (not the `api<T>` wrapper which assumes JSON).

- [ ] **Step 4: Run + commit**

```bash
uv run pytest apps/api/tests/test_auth_logout.py -v
pnpm --filter @atlas/web typecheck
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/routers/auth.py apps/api/tests/test_auth_logout.py apps/web/src/auth/AuthContext.tsx
git commit -m "feat(auth): logout endpoint + client"
```

Expected: 2 pytest passing; typecheck clean.

---

### Task 7: StalenessChip + RatingBadge primitives

**Files:**
- Create: `packages/design-system/src/primitives/StalenessChip.tsx`
- Create: `packages/design-system/src/primitives/RatingBadge.tsx`
- Create: `packages/design-system/tests/StalenessChip.test.tsx`
- Create: `packages/design-system/tests/RatingBadge.test.tsx`
- Modify: `packages/design-system/src/index.ts`

- [ ] **Step 1: StalenessChip tests**

```tsx
// packages/design-system/tests/StalenessChip.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { StalenessChip } from "../src/primitives/StalenessChip";

describe("StalenessChip", () => {
  it("renders fresh state with no age label", () => {
    render(<StalenessChip state="fresh" ageDays={30} />);
    expect(screen.getByText(/fresh/i)).toBeInTheDocument();
  });

  it("renders yellow state with age in months", () => {
    render(<StalenessChip state="yellow" ageDays={200} />);
    const text = screen.getByText(/~6 months/i);
    expect(text).toBeInTheDocument();
  });

  it("renders red state with age in years for old data", () => {
    render(<StalenessChip state="red" ageDays={400} />);
    expect(screen.getByText(/~1 years?/i)).toBeInTheDocument();
  });

  it("renders missing state with em dash", () => {
    render(<StalenessChip state="missing" ageDays={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: StalenessChip component**

```tsx
// packages/design-system/src/primitives/StalenessChip.tsx
export type StalenessState = "missing" | "fresh" | "yellow" | "red";

export interface StalenessChipProps {
  state: StalenessState;
  ageDays: number | null;
}

function formatAge(days: number | null): string {
  if (days === null) return "—";
  if (days <= 90) return `${days}d old`;
  if (days <= 365) return `~${Math.round(days / 30)} months`;
  return `~${Math.round(days / 365)} years`;
}

const PALETTE: Record<StalenessState, string> = {
  missing: "bg-ink-100 text-ink-500",
  fresh: "bg-positive/10 text-positive",
  yellow: "bg-warning/10 text-warning",
  red: "bg-danger/10 text-danger",
};

export function StalenessChip({ state, ageDays }: StalenessChipProps) {
  const label = state === "missing" ? "—" : state;
  const age = state === "missing" ? "—" : formatAge(ageDays);
  return (
    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${PALETTE[state]}`}>
      {label !== "—" && <span className="uppercase tracking-wide">{label}</span>}
      <span className="font-mono">{age}</span>
    </span>
  );
}
```

- [ ] **Step 3: RatingBadge tests**

```tsx
// packages/design-system/tests/RatingBadge.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { RatingBadge } from "../src/primitives/RatingBadge";

describe("RatingBadge", () => {
  it("renders agency and rating", () => {
    render(<RatingBadge agency="S&P" rating="B+" />);
    expect(screen.getByText("S&P")).toBeInTheDocument();
    expect(screen.getByText("B+")).toBeInTheDocument();
  });

  it("renders outlook when provided", () => {
    render(<RatingBadge agency="Moodys" rating="Ba2" outlook="positive" />);
    expect(screen.getByText(/positive/i)).toBeInTheDocument();
  });

  it("applies distressed styling for SD/D/RD/C ratings", () => {
    const { container } = render(<RatingBadge agency="S&P" rating="SD" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toMatch(/bg-danger/);
  });
});
```

- [ ] **Step 4: RatingBadge component**

```tsx
// packages/design-system/src/primitives/RatingBadge.tsx
export interface RatingBadgeProps {
  agency: "S&P" | "Moodys" | "Fitch";
  rating: string;
  outlook?: string | null;
}

const DISTRESSED = new Set(["SD", "D", "DD", "DDD", "RD", "C", "Ca"]);

function gradeClass(rating: string): string {
  if (DISTRESSED.has(rating)) return "bg-danger/15 text-danger border-danger/30";
  const first = rating.charAt(0).toUpperCase();
  if (first === "A") return "bg-positive/15 text-positive border-positive/30";
  if (first === "B" && !rating.startsWith("BB")) return "bg-ink-100 text-ink-700 border-ink-300";
  if (first === "B") return "bg-warning/15 text-warning border-warning/30";
  if (first === "C") return "bg-danger/15 text-danger border-danger/30";
  return "bg-ink-100 text-ink-700 border-ink-300";
}

export function RatingBadge({ agency, rating, outlook }: RatingBadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs ${gradeClass(rating)}`}>
      <span className="text-ink-500">{agency}</span>
      <span className="font-mono font-semibold">{rating}</span>
      {outlook ? <span className="text-ink-500 text-[10px]">· {outlook}</span> : null}
    </span>
  );
}
```

- [ ] **Step 5: Update `index.ts`**

Replace `packages/design-system/src/index.ts`:

```ts
// packages/design-system/src/index.ts
export { KpiCard } from "./primitives/KpiCard";
export type { KpiCardProps } from "./primitives/KpiCard";
export { StalenessChip } from "./primitives/StalenessChip";
export type { StalenessChipProps, StalenessState } from "./primitives/StalenessChip";
export { RatingBadge } from "./primitives/RatingBadge";
export type { RatingBadgeProps } from "./primitives/RatingBadge";
```

- [ ] **Step 6: Run + commit**

```bash
pnpm --filter @atlas/design-system test
pnpm --filter @atlas/design-system typecheck
uv run ruff check .
git add packages/design-system
git commit -m "feat(design-system): StalenessChip + RatingBadge primitives"
```

Expected: 9 design-system tests pass (2 existing KpiCard + 4 staleness + 3 rating).

---

### Task 8: RiskGauge + InstitutionalTable primitives

**Files:**
- Create: `packages/design-system/src/primitives/RiskGauge.tsx`
- Create: `packages/design-system/src/primitives/InstitutionalTable.tsx`
- Create: `packages/design-system/tests/RiskGauge.test.tsx`
- Create: `packages/design-system/tests/InstitutionalTable.test.tsx`
- Modify: `packages/design-system/src/index.ts`

- [ ] **Step 1: RiskGauge tests**

```tsx
// packages/design-system/tests/RiskGauge.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { RiskGauge } from "../src/primitives/RiskGauge";

describe("RiskGauge", () => {
  it("renders label and numeric score", () => {
    render(<RiskGauge label="Debt Burden" score={7} rationale="public debt 85%" />);
    expect(screen.getByText("Debt Burden")).toBeInTheDocument();
    expect(screen.getByText("7/10")).toBeInTheDocument();
  });

  it("shows rationale", () => {
    render(<RiskGauge label="FX Stability" score={3} rationale="30d move -4%" />);
    expect(screen.getByText(/30d move -4%/)).toBeInTheDocument();
  });

  it("applies danger styling for high scores", () => {
    const { container } = render(<RiskGauge label="X" score={9} rationale="r" />);
    expect(container.innerHTML).toMatch(/bg-danger/);
  });

  it("applies positive styling for low scores", () => {
    const { container } = render(<RiskGauge label="X" score={1} rationale="r" />);
    expect(container.innerHTML).toMatch(/bg-positive/);
  });

  it("marks estimates with a visible flag", () => {
    render(<RiskGauge label="X" score={5} rationale="no data" isEstimate />);
    expect(screen.getByText(/estimate/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: RiskGauge component**

```tsx
// packages/design-system/src/primitives/RiskGauge.tsx
export interface RiskGaugeProps {
  label: string;
  score: number;                // 0-10
  rationale: string;
  isEstimate?: boolean;
}

function barClass(score: number): string {
  if (score <= 2) return "bg-positive";
  if (score <= 4) return "bg-positive/60";
  if (score <= 6) return "bg-warning/80";
  if (score <= 8) return "bg-warning";
  return "bg-danger";
}

export function RiskGauge({ label, score, rationale, isEstimate = false }: RiskGaugeProps) {
  const pct = Math.max(0, Math.min(100, (score / 10) * 100));
  return (
    <div className="rounded-md border border-ink-100 bg-white p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-ink-700">{label}</span>
        <span className="font-mono text-sm text-ink-900">{score}/10</span>
      </div>
      <div className="mt-2 h-1.5 w-full rounded-full bg-ink-100">
        <div className={`h-1.5 rounded-full ${barClass(score)}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1.5 text-[10px] text-ink-500">
        {rationale}
        {isEstimate && <span className="ml-1 italic">(estimate)</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: InstitutionalTable tests**

```tsx
// packages/design-system/tests/InstitutionalTable.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { InstitutionalTable } from "../src/primitives/InstitutionalTable";

describe("InstitutionalTable", () => {
  it("renders column headers", () => {
    render(
      <InstitutionalTable
        columns={[
          { key: "agency", header: "Agency" },
          { key: "rating", header: "Rating" },
        ]}
        rows={[]}
      />,
    );
    expect(screen.getByText("Agency")).toBeInTheDocument();
    expect(screen.getByText("Rating")).toBeInTheDocument();
  });

  it("renders cells via render function", () => {
    render(
      <InstitutionalTable
        columns={[
          { key: "a", header: "A", render: (r: { a: string }) => r.a.toUpperCase() },
        ]}
        rows={[{ a: "hello" }, { a: "world" }]}
      />,
    );
    expect(screen.getByText("HELLO")).toBeInTheDocument();
    expect(screen.getByText("WORLD")).toBeInTheDocument();
  });

  it("shows empty state when rows are empty and emptyLabel provided", () => {
    render(
      <InstitutionalTable
        columns={[{ key: "a", header: "A" }]}
        rows={[]}
        emptyLabel="No data"
      />,
    );
    expect(screen.getByText("No data")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: InstitutionalTable component**

```tsx
// packages/design-system/src/primitives/InstitutionalTable.tsx
import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  header: string;
  render?: (row: Row) => ReactNode;
  align?: "left" | "right";
}

export interface InstitutionalTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  emptyLabel?: string;
}

export function InstitutionalTable<Row extends object>({
  columns,
  rows,
  emptyLabel,
}: InstitutionalTableProps<Row>) {
  if (rows.length === 0 && emptyLabel) {
    return (
      <div className="rounded-md border border-ink-100 bg-white p-4 text-xs text-ink-500">
        {emptyLabel}
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-md border border-ink-100 bg-white">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-ink-100 bg-ink-100/40 text-ink-500">
            {columns.map((c) => (
              <th
                key={c.key}
                className={`px-3 py-2 font-medium uppercase tracking-wide ${c.align === "right" ? "text-right" : "text-left"}`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-ink-100 last:border-b-0">
              {columns.map((c) => {
                const value = c.render ? c.render(r) : (r as Record<string, ReactNode>)[c.key];
                return (
                  <td
                    key={c.key}
                    className={`px-3 py-2 font-mono text-ink-900 ${c.align === "right" ? "text-right" : "text-left"}`}
                  >
                    {value}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 5: Update `index.ts`**

Add two more exports to `packages/design-system/src/index.ts`:

```ts
export { RiskGauge } from "./primitives/RiskGauge";
export type { RiskGaugeProps } from "./primitives/RiskGauge";
export { InstitutionalTable } from "./primitives/InstitutionalTable";
export type { Column, InstitutionalTableProps } from "./primitives/InstitutionalTable";
```

- [ ] **Step 6: Run + commit**

```bash
pnpm --filter @atlas/design-system test
pnpm --filter @atlas/design-system typecheck
git add packages/design-system
git commit -m "feat(design-system): RiskGauge + InstitutionalTable primitives"
```

Expected: 13 tests pass (2 KpiCard + 4 Staleness + 3 RatingBadge + 5 RiskGauge + 3 InstitutionalTable — actually tally matches total above; verify).

Actual test counts from this plan: 2 + 4 + 3 + 5 + 3 = **17** design-system tests after Tasks 7+8. Adjust the "expected" line above to 17 if the output differs.

---

### Task 9: Top nav + AppShell layout

**Files:**
- Create: `apps/web/src/components/TopNav.tsx`
- Create: `apps/web/src/routes/AppShell.tsx`
- Create: `apps/web/tests/TopNav.test.tsx`
- Modify: `apps/web/src/routes/Home.tsx` (wrap in AppShell)
- Modify: `apps/web/src/App.tsx` (no change needed yet — routes updated in Task 10)

- [ ] **Step 1: Write failing test**

```tsx
// apps/web/tests/TopNav.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import TopNav from "../src/components/TopNav";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode) {
  return (
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>
  );
}

describe("TopNav", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 })),
    );
  });

  it("renders Atlas logo + Home and Countries links", async () => {
    render(wrap(<TopNav />));
    expect(screen.getByText(/atlas/i)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /home/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /countries/i })).toBeInTheDocument();
  });

  it("shows the signed-in email and Logout button when authed", async () => {
    render(wrap(<TopNav />));
    expect(await screen.findByText(/a@b\.test/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /logout/i })).toBeInTheDocument();
  });

  it("calls logout when the button is clicked", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(wrap(<TopNav />));
    const btn = await screen.findByRole("button", { name: /logout/i });
    await userEvent.click(btn);
    // Logout POST should have been issued
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
```

- [ ] **Step 2: Write `TopNav.tsx`**

```tsx
// apps/web/src/components/TopNav.tsx
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function TopNav() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  async function handleLogout() {
    await logout();
    nav("/login", { replace: true });
  }

  return (
    <header className="border-b border-ink-100 bg-white">
      <div className="mx-auto flex h-12 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <span className="font-semibold tracking-tight text-ink-900">Atlas</span>
          <nav className="flex items-center gap-4 text-sm text-ink-700">
            <Link to="/" className="hover:text-ink-900">Home</Link>
            <Link to="/countries" className="hover:text-ink-900">Countries</Link>
          </nav>
        </div>
        {user ? (
          <div className="flex items-center gap-3 text-xs text-ink-500">
            <span>{user.email}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded border border-ink-100 px-2 py-0.5 hover:border-ink-300 hover:text-ink-900"
            >
              Logout
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Write `AppShell.tsx`**

```tsx
// apps/web/src/routes/AppShell.tsx
import type { ReactNode } from "react";
import TopNav from "../components/TopNav";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-ink-100">
      <TopNav />
      <div>{children}</div>
    </div>
  );
}
```

- [ ] **Step 4: Wrap Home in AppShell**

Replace `apps/web/src/routes/Home.tsx`:

```tsx
// apps/web/src/routes/Home.tsx
import { useQuery } from "@tanstack/react-query";
import { KpiCard } from "@atlas/design-system";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import AppShell from "./AppShell";

interface Health { status: string; version: string }

export default function Home() {
  const { user } = useAuth();
  const { data } = useQuery<Health>({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-8">
        <h1 className="text-xl font-semibold">Atlas — signed in as {user?.email}</h1>
        <div className="mt-6 grid grid-cols-2 gap-3">
          <KpiCard label="API status" value={data?.status ?? "—"} />
          <KpiCard label="API version" value={data?.version ?? "—"} />
        </div>
      </main>
    </AppShell>
  );
}
```

- [ ] **Step 5: Run + commit**

```bash
pnpm --filter @atlas/web test
pnpm --filter @atlas/web typecheck
pnpm --filter @atlas/web build
git add apps/web
git commit -m "feat(web): TopNav + AppShell layout"
```

Expected: existing 3 web tests still pass + 3 new TopNav tests = 6 passing.

---

### Task 10: CountriesList page

**Files:**
- Create: `apps/web/src/routes/CountriesList.tsx`
- Create: `apps/web/tests/CountriesList.test.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Failing test**

```tsx
// apps/web/tests/CountriesList.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CountriesList from "../src/routes/CountriesList";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE = [
  { iso3: "GHA", name: "Ghana", capital: "Accra", region: "West Africa", tags: ["SSA"], tier: "C", status: "restructured", fx_regime: "float", fx_regime_notes: null, fx_parallel_premium: null },
  { iso3: "KEN", name: "Kenya", capital: "Nairobi", region: "East Africa", tags: ["SSA"], tier: "B", status: "performing", fx_regime: "managed_float", fx_regime_notes: null, fx_parallel_premium: null },
  { iso3: "ZAF", name: "South Africa", capital: "Pretoria", region: "Southern Africa", tags: ["SSA"], tier: "A", status: "performing", fx_regime: "float", fx_regime_notes: null, fx_parallel_premium: null },
];

function stubFetch(countries: typeof SAMPLE) {
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }))  // /api/me
      .mockResolvedValue(new Response(JSON.stringify(countries), { status: 200 })),
  );
}

describe("CountriesList", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders each seeded country", async () => {
    stubFetch(SAMPLE);
    render(wrap(<CountriesList />));
    expect(await screen.findByText("Ghana")).toBeInTheDocument();
    expect(screen.getByText("Kenya")).toBeInTheDocument();
    expect(screen.getByText("South Africa")).toBeInTheDocument();
  });

  it("filters by search term", async () => {
    stubFetch(SAMPLE);
    render(wrap(<CountriesList />));
    await screen.findByText("Ghana");
    await userEvent.type(screen.getByPlaceholderText(/search/i), "ken");
    expect(screen.getByText("Kenya")).toBeInTheDocument();
    expect(screen.queryByText("Ghana")).not.toBeInTheDocument();
  });

  it("filters by region chip", async () => {
    stubFetch(SAMPLE);
    render(wrap(<CountriesList />));
    await screen.findByText("Ghana");
    await userEvent.click(screen.getByRole("button", { name: /east africa/i }));
    expect(screen.getByText("Kenya")).toBeInTheDocument();
    expect(screen.queryByText("Ghana")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write component**

```tsx
// apps/web/src/routes/CountriesList.tsx
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "./AppShell";

interface Country {
  iso3: string;
  name: string;
  region: string;
  status: string;
  fx_regime: string;
  tier: string;
}

const REGIONS = ["West Africa", "East Africa", "Southern Africa", "North Africa"] as const;

export default function CountriesList() {
  const { data, isLoading, error } = useQuery<Country[]>({
    queryKey: ["countries"],
    queryFn: () => api<Country[]>("/api/countries"),
    staleTime: 5 * 60 * 1000,
  });
  const [q, setQ] = useState("");
  const [region, setRegion] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.filter((c) => {
      if (region && c.region !== region) return false;
      if (!q) return true;
      const needle = q.trim().toLowerCase();
      return c.iso3.toLowerCase().includes(needle) || c.name.toLowerCase().includes(needle);
    });
  }, [data, q, region]);

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-8">
        <h1 className="text-xl font-semibold text-ink-900">Countries</h1>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <input
            type="search"
            placeholder="Search by name or ISO3…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-56 rounded border border-ink-100 px-3 py-1 text-sm"
          />
          <div className="flex items-center gap-1">
            {REGIONS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRegion(region === r ? null : r)}
                className={`rounded border px-2 py-0.5 text-xs ${region === r ? "border-accent bg-accent/10 text-accent" : "border-ink-100 text-ink-700 hover:border-ink-300"}`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="mt-8 text-ink-500">Loading…</div>
        ) : error ? (
          <div className="mt-8 text-danger">Failed to load countries.</div>
        ) : (
          <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((c) => (
              <li key={c.iso3}>
                <Link
                  to={`/countries/${c.iso3}`}
                  className="block rounded-md border border-ink-100 bg-white p-4 transition hover:border-accent"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-sm font-semibold text-ink-900">{c.name}</div>
                      <div className="text-xs text-ink-500">{c.region} · {c.iso3}</div>
                    </div>
                    <span className="font-mono text-xs text-ink-500">Tier {c.tier}</span>
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-[10px] uppercase tracking-wide text-ink-500">
                    <span className="rounded bg-ink-100 px-1.5 py-0.5">{c.status}</span>
                    <span className="rounded bg-ink-100 px-1.5 py-0.5">{c.fx_regime}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </AppShell>
  );
}
```

- [ ] **Step 3: Add route to `App.tsx`**

Replace `apps/web/src/App.tsx`:

```tsx
// apps/web/src/App.tsx
import { Route, Routes } from "react-router-dom";
import Login from "./routes/Login";
import Home from "./routes/Home";
import CountriesList from "./routes/CountriesList";
import RequireAuth from "./routes/RequireAuth";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
      <Route path="/countries" element={<RequireAuth><CountriesList /></RequireAuth>} />
    </Routes>
  );
}
```

- [ ] **Step 4: Run + commit**

```bash
pnpm --filter @atlas/web test
pnpm --filter @atlas/web typecheck
pnpm --filter @atlas/web build
git add apps/web
git commit -m "feat(web): /countries list page"
```

Expected: 3 existing + 3 TopNav + 3 CountriesList = 9 web tests pass.

---

### Task 11: CountryProfile page — shell + header + macro grid + FX

**Files:**
- Create: `apps/web/src/routes/CountryProfile.tsx`
- Create: `apps/web/tests/CountryProfile.test.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Failing tests**

```tsx
// apps/web/tests/CountryProfile.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CountryProfile from "../src/routes/CountryProfile";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode, initial = "/countries/GHA") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>
        <AuthProvider>
          <Routes>
            <Route path="/countries/:iso3" element={ui} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const GHA_BUNDLE = {
  country: {
    iso3: "GHA", name: "Ghana", capital: "Accra", region: "West Africa",
    tags: ["SSA"], tier: "C", status: "restructured", fx_regime: "float",
    fx_regime_notes: "Cedi floats", fx_parallel_premium: null,
  },
  macro: [
    { indicator: "PUBLIC_DEBT_PCT_GDP", label: "Public debt (% GDP)", value: 83.0, period: "2024", source: "worldbank", staleness: { state: "fresh", age_days: 30 } },
    { indicator: "INFLATION_PCT", label: "Inflation (CPI % YoY)", value: 22.0, period: "2024", source: "worldbank", staleness: { state: "fresh", age_days: 30 } },
    { indicator: "GDP_GROWTH_PCT", label: "GDP growth (% YoY)", value: 3.1, period: "2024", source: "imf_weo", staleness: { state: "fresh", age_days: 45 } },
    // …enough tiles that the grid has content; 12 total in prod, we only stub 3 here
  ],
  fx: {
    latest: {
      iso3: "GHA", ccy: "GHS", usd_per_ccy: 0.0667,
      observation_date: "2026-04-16", source: "exchangerate.host",
      ingested_at: "2026-04-16T03:00:00Z",
    },
    delta_1d_pct: -0.3, delta_7d_pct: -1.2, delta_30d_pct: -4.8, delta_ytd_pct: -9.0,
  },
  ratings: {
    latest_per_agency: {
      "S&P": { iso3: "GHA", agency: "S&P", rating: "CCC+", outlook: "stable", action: "upgrade", action_date: "2024-05-01", source_url: null },
    },
    composite_score: 17.5,
    history: [],
  },
  risk: {
    composite: 65.0,
    dimensions: [
      { dimension: "debt_burden", score: 10, rationale: "distressed", input_value: 83.0, is_estimate: false },
      { dimension: "external_liquidity", score: 5, rationale: "3.1mo", input_value: 3.1, is_estimate: false },
      { dimension: "fiscal_flexibility", score: 7, rationale: "-4.5%", input_value: -4.5, is_estimate: false },
      { dimension: "growth_momentum", score: 5, rationale: "3.1%", input_value: 3.1, is_estimate: false },
      { dimension: "inflation_pressure", score: 7, rationale: "22%", input_value: 22.0, is_estimate: false },
      { dimension: "fx_stability", score: 5, rationale: "-4.8%", input_value: -4.8, is_estimate: false },
    ],
  },
  synopsis: null,
  news_placeholder: true,
};

function stubBundle(body: unknown = GHA_BUNDLE) {
  vi.stubGlobal(
    "fetch",
    vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }))
      .mockResolvedValue(new Response(JSON.stringify(body), { status: 200 })),
  );
}

describe("CountryProfile", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders the header with country name and status", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("Ghana")).toBeInTheDocument();
    expect(screen.getByText(/restructured/i)).toBeInTheDocument();
  });

  it("renders macro tiles with values", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("Public debt (% GDP)")).toBeInTheDocument();
    expect(screen.getByText("83.00")).toBeInTheDocument();
  });

  it("renders FX section with latest rate and deltas", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText(/GHS/i)).toBeInTheDocument();
    expect(screen.getByText(/-4.8/)).toBeInTheDocument();
  });

  it("renders ratings with composite", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("CCC+")).toBeInTheDocument();
    expect(screen.getByText(/17\.5/)).toBeInTheDocument();
  });

  it("renders the 6 risk dimensions", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    await screen.findByText("Ghana");
    for (const dim of ["debt_burden", "external_liquidity", "fiscal_flexibility", "growth_momentum", "inflation_pressure", "fx_stability"]) {
      expect(screen.getByText(new RegExp(dim.replace("_", " "), "i"))).toBeInTheDocument();
    }
  });

  it("shows synopsis placeholder when synopsis is null", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText(/AI synopsis pending/i)).toBeInTheDocument();
  });

  it("shows news placeholder when news_placeholder is true", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText(/no scored news yet/i)).toBeInTheDocument();
  });

  it("renders 404 state when bundle returns 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn()
        .mockResolvedValueOnce(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }))
        .mockResolvedValue(new Response(JSON.stringify({ detail: "country ZZZ not found" }), { status: 404 })),
    );
    render(wrap(<CountryProfile />, "/countries/ZZZ"));
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write component**

```tsx
// apps/web/src/routes/CountryProfile.tsx
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import {
  InstitutionalTable,
  RatingBadge,
  RiskGauge,
  StalenessChip,
  type StalenessState,
} from "@atlas/design-system";
import { ApiError, api } from "../api/client";
import AppShell from "./AppShell";

interface MacroTile {
  indicator: string;
  label: string;
  value: number | null;
  period: string | null;
  source: string | null;
  staleness: { state: StalenessState; age_days: number | null };
}

interface FxObservation {
  iso3: string;
  ccy: string;
  usd_per_ccy: number;
  observation_date: string;
  source: string;
  ingested_at: string;
}

interface FxDeltas {
  latest: FxObservation;
  delta_1d_pct: number | null;
  delta_7d_pct: number | null;
  delta_30d_pct: number | null;
  delta_ytd_pct: number | null;
}

interface RatingAction {
  iso3: string;
  agency: "S&P" | "Moodys" | "Fitch";
  rating: string;
  outlook: string | null;
  action: string;
  action_date: string;
  source_url: string | null;
}

interface DimensionScore {
  dimension: string;
  score: number;
  rationale: string;
  input_value: number | null;
  is_estimate: boolean;
}

interface CountryBundle {
  country: {
    iso3: string; name: string; capital: string; region: string;
    tags: string[]; tier: string; status: string; fx_regime: string;
    fx_regime_notes: string | null; fx_parallel_premium: number | null;
  };
  macro: MacroTile[];
  fx: FxDeltas | null;
  ratings: {
    latest_per_agency: Record<string, RatingAction>;
    composite_score: number | null;
    history: RatingAction[];
  };
  risk: { composite: number; dimensions: DimensionScore[] };
  synopsis: string | null;
  news_placeholder: boolean;
}

function fmtPct(n: number | null): string {
  return n == null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function fmtValue(n: number | null): string {
  return n == null ? "—" : n.toFixed(2);
}

function dimensionLabel(d: string): string {
  return d.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function CountryProfile() {
  const { iso3 = "" } = useParams();
  const { data, isLoading, error } = useQuery<CountryBundle>({
    queryKey: ["country-bundle", iso3.toUpperCase()],
    queryFn: () => api<CountryBundle>(`/api/countries/${iso3.toUpperCase()}/bundle`),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  if (isLoading) {
    return <AppShell><main className="p-8 text-ink-500">Loading…</main></AppShell>;
  }
  if (error) {
    const msg = error instanceof ApiError && error.status === 404
      ? `Country ${iso3.toUpperCase()} not found`
      : "Failed to load country profile";
    return <AppShell><main className="p-8 text-danger">{msg}</main></AppShell>;
  }
  if (!data) return null;

  const { country, macro, fx, ratings, risk, synopsis, news_placeholder } = data;

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-6">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-semibold text-ink-900">{country.name}</h1>
            <span className="font-mono text-sm text-ink-500">{country.iso3}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-ink-500">
            <span className="rounded bg-ink-100 px-2 py-0.5 uppercase tracking-wide">{country.status}</span>
            <span className="rounded bg-ink-100 px-2 py-0.5 uppercase tracking-wide">{country.fx_regime}</span>
            <span>Tier {country.tier} · {country.region}</span>
          </div>
        </header>

        {/* Synopsis placeholder */}
        <section className="mb-6 rounded-md border border-dashed border-ink-100 bg-white p-4 text-sm text-ink-500">
          {synopsis ?? "AI synopsis pending review."}
        </section>

        {/* Ratings */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">Ratings</h2>
          <div className="flex flex-wrap items-center gap-2">
            {Object.values(ratings.latest_per_agency).map((r) => (
              <RatingBadge key={r.agency} agency={r.agency} rating={r.rating} outlook={r.outlook} />
            ))}
            {ratings.composite_score != null ? (
              <span className="ml-2 rounded border border-ink-100 px-2 py-0.5 text-xs text-ink-700">
                Composite <span className="font-mono">{ratings.composite_score.toFixed(1)}</span>/21
              </span>
            ) : null}
          </div>
        </section>

        {/* Macro grid */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">Macro</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
            {macro.map((t) => (
              <div key={t.indicator} className="rounded-md border border-ink-100 bg-white p-3">
                <div className="flex items-start justify-between">
                  <div className="text-xs text-ink-500">{t.label}</div>
                  <StalenessChip state={t.staleness.state} ageDays={t.staleness.age_days} />
                </div>
                <div className="mt-1 font-mono text-lg text-ink-900">{fmtValue(t.value)}</div>
                <div className="text-[10px] text-ink-300">
                  {t.period ?? "—"}{t.source ? ` · ${t.source}` : ""}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* FX section */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">FX</h2>
          {fx ? (
            <div className="rounded-md border border-ink-100 bg-white p-4">
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="text-xs text-ink-500">{fx.latest.ccy} / USD</span>
                  <div className="font-mono text-2xl text-ink-900">{fx.latest.usd_per_ccy.toFixed(6)}</div>
                </div>
                <div className="text-[10px] text-ink-300">as of {fx.latest.observation_date}</div>
              </div>
              <div className="mt-3 grid grid-cols-4 gap-2 text-center">
                {[
                  { label: "1d", v: fx.delta_1d_pct },
                  { label: "7d", v: fx.delta_7d_pct },
                  { label: "30d", v: fx.delta_30d_pct },
                  { label: "YTD", v: fx.delta_ytd_pct },
                ].map((cell) => (
                  <div key={cell.label} className="rounded bg-ink-100/40 py-2">
                    <div className="text-[10px] uppercase tracking-wide text-ink-500">{cell.label}</div>
                    <div className={`font-mono text-sm ${cell.v == null ? "text-ink-500" : cell.v < 0 ? "text-danger" : "text-positive"}`}>
                      {fmtPct(cell.v)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <InstitutionalTable columns={[{ key: "label", header: "" }]} rows={[]} emptyLabel="No FX data yet" />
          )}
        </section>

        {/* Risk decomposition */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">
            Risk decomposition <span className="ml-2 font-mono text-ink-900">{risk.composite.toFixed(1)}/100</span>
          </h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {risk.dimensions.map((d) => (
              <RiskGauge
                key={d.dimension}
                label={dimensionLabel(d.dimension)}
                score={d.score}
                rationale={d.rationale}
                isEstimate={d.is_estimate}
              />
            ))}
          </div>
        </section>

        {/* News placeholder */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">News & impact</h2>
          {news_placeholder
            ? <InstitutionalTable columns={[{ key: "label", header: "" }]} rows={[]} emptyLabel="No scored news yet." />
            : <div>News list goes here in Plan 4.</div>}
        </section>
      </main>
    </AppShell>
  );
}
```

- [ ] **Step 3: Add route to `App.tsx`**

```tsx
// apps/web/src/App.tsx
import { Route, Routes } from "react-router-dom";
import Login from "./routes/Login";
import Home from "./routes/Home";
import CountriesList from "./routes/CountriesList";
import CountryProfile from "./routes/CountryProfile";
import RequireAuth from "./routes/RequireAuth";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
      <Route path="/countries" element={<RequireAuth><CountriesList /></RequireAuth>} />
      <Route path="/countries/:iso3" element={<RequireAuth><CountryProfile /></RequireAuth>} />
    </Routes>
  );
}
```

- [ ] **Step 4: Run + commit**

```bash
pnpm --filter @atlas/web test
pnpm --filter @atlas/web typecheck
pnpm --filter @atlas/web build
git add apps/web
git commit -m "feat(web): country profile page with macro/FX/ratings/risk"
```

Expected: 9 + 8 CountryProfile = 17 web tests pass.

---

### Task 12: Populate DB with live data + manual browser smoke

This task is NOT a code change — it's the end-to-end verification that Plan 3 delivers a populated country page. Everything up through Task 11 ships with all placeholders because the DB has only the 10 seeded country reference rows from Plan 2.

- [ ] **Step 1: Start the stack**

```bash
cd /Users/bird/Documents/ATLAS/atlas
docker compose up -d
uv run alembic -c infra/migrations/alembic.ini upgrade head
uv run python apps/api/scripts/seed_countries.py
uv run python apps/api/scripts/seed_demo_user.py
```

Expected: migrations head `0005_uq_macro_vintage_add_source`, 10 countries, demo user.

- [ ] **Step 2: Populate vintage data (first run hits real APIs)**

```bash
uv run python -m atlas_api.ingestion.cli run --source ratings
uv run python -m atlas_api.ingestion.cli run --source fx
uv run python -m atlas_api.ingestion.cli run --source worldbank
uv run python -m atlas_api.ingestion.cli run --source imf
```

Expected:
- ratings: `rows_written: 26` (one per agency-country in `ratings.json`)
- fx: `rows_written: 10` (today's date for all 10 countries; some may `rows_skipped` if ExchangeRate.host is missing a currency)
- worldbank: `rows_written >= 500` (~12 indicators × 10 countries × several years)
- imf: `rows_written >= 300` (~8 indicators × 10 countries × several years)

**If ExchangeRate.host returns 401/403:** per Plan 2 Task 18 step 3 fallback, either register for a key and set `EXCHANGERATE_HOST_KEY=...` in `.env`, or swap to Frankfurter (edit `apps/api/src/atlas_api/ingestion/fx.py`: change `BASE_URL` to `"https://api.frankfurter.app/latest"`, change `params` construction to `{"from": "USD", "to": ",".join(currencies)}`, accept that Frankfurter lacks GHS/NGN/KES/ETB/RWF coverage). Commit the chosen solution as `fix(ingestion): switch fx source` and re-run.

- [ ] **Step 3: Spot-check the API**

```bash
uv run uvicorn atlas_api.main:app --reload --app-dir apps/api/src &
sleep 2
curl -s -c /tmp/atlas.cookies -X POST http://localhost:8000/api/auth/login \
  -H "content-type: application/json" \
  -d '{"email":"analyst@atlas.test","password":"change-me"}' > /dev/null
curl -s -b /tmp/atlas.cookies http://localhost:8000/api/countries/GHA/bundle | python -m json.tool | head -80
kill %1
```

Expected output: JSON with country=Ghana, non-empty macro tiles (most indicators have values), fx populated, ratings with S&P/Moodys/Fitch entries, risk composite 50–75ish.

- [ ] **Step 4: Manual browser smoke**

Start both terminals:

```bash
# Terminal A
uv run uvicorn atlas_api.main:app --reload --app-dir apps/api/src
# Terminal B
pnpm dev:web
```

Visit `http://localhost:5173`:

1. Redirected to `/login`. Log in with `analyst@atlas.test` / `change-me`. ✓ Redirects to `/`.
2. Top nav shows `Atlas` · `Home` · `Countries` · email · Logout. ✓
3. Click `Countries`. 10 country cards render. Click a region chip to filter; type in search to narrow. ✓
4. Click a country (e.g. Ghana). Profile page renders:
   - Header with name + ISO3 + status + regime + tier.
   - "AI synopsis pending review" placeholder. ✓
   - Ratings line with at least one rating badge + composite score.
   - Macro grid with ~12 tiles; values visible where data exists, "—" + missing/red chip where absent.
   - FX section with current rate and 1d/7d/30d/YTD deltas.
   - Risk decomposition gauges (6 dimensions, composite at the top).
   - "No scored news yet" placeholder. ✓
5. Click Logout. Cookie cleared; redirected to `/login`. Trying to revisit `/countries` → redirected back to `/login`. ✓
6. Try an invalid iso3 directly: `http://localhost:5173/countries/ZZZ` → "Country ZZZ not found". ✓

Mark each item as ✓ before declaring success.

- [ ] **Step 5: Final lint/type/test pass**

```bash
uv run pytest
pnpm -r test
pnpm -r typecheck
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
```

All green.

- [ ] **Step 6: Optional tag**

**Gated — ask the user before pushing.**

```bash
git tag -a v0.3.0-country-intel -m "Atlas country intelligence: profile page ships with macro+fx+ratings+risk"
# git push origin v0.3.0-country-intel   # user-approved only
```

---

## Self-Review

**1. Spec coverage (Plan 3 scope: Country Intelligence only):**

- §1.2 Country Intelligence full page → Tasks 11. ✓
- §4 `/countries` list with filter chips + search → Task 10. ✓
- §4 `/countries/:iso3` CountryProfile: header, synopsis, ratings, macro grid, FX section, risk decomposition, news → Task 11. Synopsis + news are placeholders (deferred to Plan 4); spec §7 says synopsis ships in the AI plan anyway. ✓
- §4 Design-system primitives KpiCard (exists), RatingBadge, RiskGauge, InstitutionalTable, StalenessChip → Tasks 7-8. NewsItemCard is deferred to Plan 4 (no news data to render). ✓
- §5 Composite rating (S&P×0.4 + Moody×0.35 + Fitch×0.25 rescaled) → Plan 2 Task 9 (already built); surfaced in Task 4 bundle. ✓
- §5 Risk Score (6-dimension deterministic) → Task 2. ✓
- §6.4 `GET /api/countries/:iso3` bundle — macro + FX + ratings + composite + risk + news (placeholder) + synopsis (placeholder) → Tasks 4 + 5. Note: we use `/bundle` subpath to keep the simple list endpoint lightweight. ✓
- §6.4 React Query 5-min stale time → Tasks 10 + 11 (via `staleTime: 5 * 60 * 1000`). ✓
- §8 Staleness: missing `—`, yellow >6mo, red >12mo → Tasks 3 + 7 (`StalenessChip`). ✓
- §8 Distressed sovereign handling: Risk Score flags Liquidity; status shown on header → Task 2 (distressed status auto-maxes Debt Burden) + Task 11 (status chip). ✓
- §9 Logout / session hygiene — added as minimum auth hygiene since nav needs a logout button. Spec doesn't require it but it's a natural fit. ✓
- §10 One Playwright smoke test — **deferred**. Plan 1 deferred Playwright setup; installing it is overkill for Plan 3's reach. Manual browser smoke in Task 12 covers the same ground until Plan 5 (Reports) forces Playwright for PDF generation.

**Deferred to later plans (as designed):**
- Exec synopsis generation (AI) — Plan 4
- News ingestion + impact scoring — Plan 4
- Events timeline — Plan 4 or later
- Scenario engine — Plan 5
- Country Brief PDF — Plan 5
- Playwright E2E — Plan 5 when PDF generation needs it

**2. Placeholder scan:** The plan as written has no TBDs, no "similar to", no "handle edge cases" without code. Two intentional "(placeholder)" artifacts — synopsis and news — are deliberately empty-state UIs until Plan 4 populates them, and the schemas explicitly encode the empty state (`synopsis: str | None`, `news_placeholder: bool`). Not plan gaps.

**3. Type consistency:**
- `StalenessState` enum values (`"missing" | "fresh" | "yellow" | "red"`) used consistently across Python schemas (Task 1), Python helper (Task 3), TS component props (Task 7). ✓
- `RiskDimension` enum 6 members used in Python risk function (Task 2), TS `DimensionScore` props (Task 11). ✓
- `CountryBundle` shape: Python Pydantic (Task 1) matches TS interface in `CountryProfile.tsx` (Task 11). ✓
- `MacroIndicator` enum values match tile order in `_TILE_LABELS` (Task 4) ↔ test assertions ↔ indicator codes (Plan 2 Task 8). ✓
- `RatingBadge.agency` prop is `"S&P" | "Moodys" | "Fitch"` — matches Python `Agency` enum values (Plan 2 Task 6). ✓
- Bundle endpoint URL `/api/countries/{iso3}/bundle` matches Task 5 router + Task 11 frontend `useQuery` call. ✓
- `composite_score` returns `float | None` (Plan 2 Task 9) — surfaced as `RatingsSection.composite_score: float | None` (Task 1) — rendered with null check in Task 11. ✓

Plan is internally consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-16-atlas-country-intelligence.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task, spec + code quality review between tasks.

**2. Inline Execution** — Direct execution with checkpoints.

Which approach?
