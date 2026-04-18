# Atlas Scenario Engine (Manual Mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A logged-in analyst can navigate from a country profile to a Scenario Engine page, adjust 5 macro shock sliders, see a live preview of the shocked risk score + fiscal deltas + probability of debt distress, then save the scenario for later viewing. All computation is deterministic and sub-500ms (pure math, no ML). Distressed sovereigns show "N/A" for PoD.

**Architecture:** A new `scenario` service module contains a pure-function shock engine that takes baseline macro indicators + a shock vector, applies deterministic transformations, and recomputes the risk score via the existing `compute_risk_score`. A logistic PoD function provides a prototype-grade distress probability. Four REST endpoints handle preview (no DB write), save, get, and list. The frontend adds two new pages: `ScenarioEngine` with 5 debounced sliders calling the preview endpoint, and `ScenarioView` for readonly display of saved runs. A new `scenario_run` table with JSONB columns stores inputs and outputs. Multi-tenancy is hooked via `tenant_id` per spec section 14.3.

**Tech Stack:** FastAPI endpoints (existing stack); SQLAlchemy + Alembic migration `0006`; Pydantic schemas in `packages/schemas`; React + TanStack Query + react-router-dom (existing); `RiskGauge` from `@atlas/design-system`; vitest for frontend; pytest with testcontainers for backend golden tests.

---

## File Structure

Files created (C) or modified (M):

```
atlas/
├── packages/schemas/
│   ├── src/atlas_schemas/
│   │   ├── __init__.py                                            (M) export new scenario types
│   │   └── scenario.py                                            (C) ShockVector, ScenarioPreview, ScenarioRunOut
│   └── tests/
│       └── test_contracts.py                                      (M) add scenario schema roundtrip tests
│
├── infra/migrations/versions/
│   └── 0006_scenario_run.py                                       (C) scenario_run table
│
├── apps/api/
│   ├── src/atlas_api/
│   │   ├── models.py                                              (M) add ScenarioRun model
│   │   ├── main.py                                                (M) wire scenarios router
│   │   ├── routers/
│   │   │   └── scenarios.py                                       (C) 4 endpoints
│   │   └── services/
│   │       └── scenario/
│   │           ├── __init__.py                                    (C)
│   │           ├── engine.py                                      (C) apply_shocks + compute_scenario_preview
│   │           ├── pod.py                                         (C) compute_pod
│   │           └── service.py                                     (C) preview/save/get/list
│   └── tests/
│       ├── test_scenario_engine.py                                (C) golden tests for engine
│       ├── test_pod.py                                            (C) golden tests for PoD
│       └── test_scenario_endpoints.py                             (C) integration tests
│
└── apps/web/
    └── src/
        ├── App.tsx                                                (M) add /scenarios routes
        ├── routes/
        │   ├── ScenarioEngine.tsx                                 (C) 5 sliders + live preview
        │   └── ScenarioView.tsx                                   (C) saved scenario readonly
        └── routes/CountryProfile.tsx                              (M) add "Run Scenario" button
```

---

## Design decisions locked in this plan

1. **Preview is stateless.** `POST /api/scenarios/preview` does zero DB writes. It fetches the baseline bundle, applies shocks in-memory, and returns the result. Target <500ms.
2. **Shock engine is pure.** `apply_shocks` and `compute_pod` are pure functions with no side effects, making them trivially testable with golden values.
3. **PoD is logistic.** `1 / (1 + exp(-(0.03 * debt_gdp + 0.5 * (1/reserves) - 0.1 * fiscal_balance - 3.5)))`. This is prototype-grade; the spec explicitly calls it out as replaceable.
4. **Distressed countries get `None` PoD.** When `status in {selective_default, default, restructured}`, PoD returns `None` and the frontend shows "Not applicable -- country in [status]".
5. **`commodity_sensitivity = 0.15`** is a fixed coefficient for the commodity shock's effect on fiscal balance and current account.
6. **`tenant_id`** is `UUID NOT NULL DEFAULT 'prototype-tenant'` per spec section 14.3 -- a multi-tenancy hook, not enforced yet.
7. **Debounce is 300ms** on the frontend. After the last slider change, wait 300ms before calling the preview API.
8. **JSONB columns** for `shocks` and `outputs` allow schema evolution without migrations.

---

## Task 1 of 11 -- Scenario schemas

**Goal:** Define `ShockVector`, `ScenarioPreview`, `ScenarioRunOut` Pydantic models. Add contract tests. Update `__init__.py`.

### Steps

- [ ] Create `packages/schemas/src/atlas_schemas/scenario.py`
- [ ] Update `packages/schemas/src/atlas_schemas/__init__.py`
- [ ] Add contract tests in `packages/schemas/tests/test_contracts.py`

### Code

**`packages/schemas/src/atlas_schemas/scenario.py`** (CREATE)

```python
"""Scenario Engine schemas for shock analysis."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ShockVector(BaseModel):
    """Five macro shock sliders -- each value is in percentage points."""

    gdp_shock: float = Field(0.0, ge=-20.0, le=20.0, description="GDP growth shock (pp)")
    inflation_shock: float = Field(0.0, ge=-20.0, le=20.0, description="Inflation shock (pp)")
    fx_depreciation: float = Field(0.0, ge=-50.0, le=100.0, description="FX depreciation (%)")
    rate_shock: float = Field(0.0, ge=-10.0, le=20.0, description="Interest rate shock (pp)")
    commodity_shock: float = Field(0.0, ge=-50.0, le=50.0, description="Commodity price shock (%)")


class ScenarioDeltas(BaseModel):
    """Change in key fiscal aggregates from baseline to shocked state."""

    debt_gdp: float
    fiscal_balance: float
    current_account: float


class ScenarioPreview(BaseModel):
    """Result of applying a shock vector -- returned by the preview endpoint."""

    baseline_risk_score: float
    new_risk_score: float
    distress_probability: float | None = Field(
        None, description="None when country is in distressed status"
    )
    deltas: ScenarioDeltas
    baseline_debt_gdp: float
    baseline_fiscal_balance: float
    baseline_current_account: float
    new_debt_gdp: float
    new_fiscal_balance: float
    new_current_account: float


class ScenarioRunOut(BaseModel):
    """Persisted scenario run -- returned by save/get/list endpoints."""

    id: uuid.UUID
    iso3: str
    shocks: ShockVector
    outputs: ScenarioPreview
    created_by: uuid.UUID
    created_at: datetime
    saved: bool = True
```

**`packages/schemas/src/atlas_schemas/__init__.py`** (MODIFY -- add imports)

```python
from atlas_schemas.auth import LoginRequest, LoginResponse, Me
from atlas_schemas.bundle import CountryBundle, MacroTile, RatingsSection
from atlas_schemas.country import Country, CountryStatus, FxRegime
from atlas_schemas.fx import FxDeltas, FxObservation
from atlas_schemas.health import HealthResponse
from atlas_schemas.ingestion import DataVintage, IngestionReport, SourceStats
from atlas_schemas.macro import MacroIndicator, MacroValue
from atlas_schemas.ratings import Agency, RatingAction
from atlas_schemas.risk import DimensionScore, RiskDimension, RiskScore
from atlas_schemas.scenario import ScenarioDeltas, ScenarioPreview, ScenarioRunOut, ShockVector
from atlas_schemas.staleness import StalenessInfo, StalenessState

__all__ = [
    "Agency", "Country", "CountryBundle", "CountryStatus", "DataVintage",
    "DimensionScore", "FxDeltas", "FxObservation", "FxRegime", "HealthResponse",
    "IngestionReport", "LoginRequest", "LoginResponse", "MacroIndicator",
    "MacroTile", "MacroValue", "Me", "RatingAction", "RatingsSection",
    "RiskDimension", "RiskScore", "ScenarioDeltas", "ScenarioPreview",
    "ScenarioRunOut", "ShockVector", "SourceStats", "StalenessInfo",
    "StalenessState",
]
```

**`packages/schemas/tests/test_contracts.py`** (MODIFY -- append these tests)

```python
from atlas_schemas.scenario import ScenarioDeltas, ScenarioPreview, ScenarioRunOut, ShockVector
import uuid
from datetime import datetime, UTC


def test_shock_vector_defaults():
    sv = ShockVector()
    assert sv.gdp_shock == 0.0
    assert sv.inflation_shock == 0.0
    assert sv.fx_depreciation == 0.0
    assert sv.rate_shock == 0.0
    assert sv.commodity_shock == 0.0


def test_shock_vector_roundtrip():
    sv = ShockVector(gdp_shock=-2.0, inflation_shock=5.0, fx_depreciation=15.0,
                     rate_shock=3.0, commodity_shock=-10.0)
    d = sv.model_dump()
    assert ShockVector(**d) == sv


def test_scenario_preview_roundtrip():
    sp = ScenarioPreview(
        baseline_risk_score=46.7,
        new_risk_score=53.3,
        distress_probability=0.2624,
        deltas=ScenarioDeltas(debt_gdp=3.0612, fiscal_balance=-1.5, current_account=-1.5),
        baseline_debt_gdp=60.0,
        baseline_fiscal_balance=-3.0,
        baseline_current_account=-2.0,
        new_debt_gdp=63.0612,
        new_fiscal_balance=-4.5,
        new_current_account=-3.5,
    )
    d = sp.model_dump()
    assert ScenarioPreview(**d).new_risk_score == 53.3


def test_scenario_run_out_roundtrip():
    run = ScenarioRunOut(
        id=uuid.uuid4(),
        iso3="KEN",
        shocks=ShockVector(gdp_shock=-2.0),
        outputs=ScenarioPreview(
            baseline_risk_score=40.0,
            new_risk_score=45.0,
            distress_probability=0.3,
            deltas=ScenarioDeltas(debt_gdp=1.0, fiscal_balance=-0.5, current_account=-0.5),
            baseline_debt_gdp=73.0,
            baseline_fiscal_balance=-5.5,
            baseline_current_account=-3.0,
            new_debt_gdp=74.0,
            new_fiscal_balance=-6.0,
            new_current_account=-3.5,
        ),
        created_by=uuid.uuid4(),
        created_at=datetime.now(UTC),
    )
    d = run.model_dump(mode="json")
    assert ScenarioRunOut(**d).iso3 == "KEN"


def test_scenario_preview_none_pod():
    """Distressed countries have None PoD."""
    sp = ScenarioPreview(
        baseline_risk_score=71.7,
        new_risk_score=75.0,
        distress_probability=None,
        deltas=ScenarioDeltas(debt_gdp=2.0, fiscal_balance=-1.0, current_account=-1.0),
        baseline_debt_gdp=38.0,
        baseline_fiscal_balance=-3.2,
        baseline_current_account=-4.0,
        new_debt_gdp=40.0,
        new_fiscal_balance=-4.2,
        new_current_account=-5.0,
    )
    assert sp.distress_probability is None
```

### Verification

```bash
cd packages/schemas && python -m pytest tests/test_contracts.py -v --tb=short
```

---

## Task 2 of 11 -- Migration `0006_scenario_run`

**Goal:** Create the `scenario_run` table with JSONB columns, tenant_id, and indexes. Add the SQLAlchemy model.

### Steps

- [ ] Create `infra/migrations/versions/0006_scenario_run.py`
- [ ] Add `ScenarioRun` model to `apps/api/src/atlas_api/models.py`

### Code

**`infra/migrations/versions/0006_scenario_run.py`** (CREATE)

```python
"""add scenario_run table

Revision ID: 0006_scenario_run
Revises: 0005_uq_macro_vintage_add_source
Create Date: 2026-04-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006_scenario_run"
down_revision = "0005_uq_macro_vintage_add_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_run",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column("input_vintage_id", UUID(as_uuid=True), sa.ForeignKey("data_vintage.id"), nullable=True),
        sa.Column("shocks", JSONB, nullable=False),
        sa.Column("outputs", JSONB, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("saved", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("'00000000-0000-0000-0000-000000000000'::uuid"),
        ),
    )
    op.create_index("ix_scenario_run_iso3", "scenario_run", ["iso3"])
    op.create_index("ix_scenario_run_created_by", "scenario_run", ["created_by"])
    op.create_index("ix_scenario_run_tenant_id", "scenario_run", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_scenario_run_tenant_id")
    op.drop_index("ix_scenario_run_created_by")
    op.drop_index("ix_scenario_run_iso3")
    op.drop_table("scenario_run")
```

**`apps/api/src/atlas_api/models.py`** (MODIFY -- append at bottom)

Add after the `RatingHistory` class:

```python
class ScenarioRun(Base):
    __tablename__ = "scenario_run"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    input_vintage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_vintage.id"), nullable=True
    )
    shocks: Mapped[dict] = mapped_column(JSONB, nullable=False)
    outputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    saved: Mapped[bool] = mapped_column(nullable=False, default=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        server_default=func.text("'00000000-0000-0000-0000-000000000000'::uuid"),
    )
```

Note: the existing imports in `models.py` already include `UUID`, `DateTime`, `ForeignKey`, `String`, `func`, `uuid`, and `datetime`. You must add `JSONB` to the imports:

```python
from sqlalchemy.dialects.postgresql import UUID, JSONB
```

And add `Boolean` to the `sqlalchemy` import if not already present:

```python
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
```

### Verification

```bash
cd /Users/bird/Documents/ATLAS/atlas && alembic upgrade head
# Then check table exists:
psql -h localhost -p 5433 -U atlas -d atlas -c "\d scenario_run"
```

---

## Task 3 of 11 -- Shock engine pure function

**Goal:** Implement `apply_shocks` and `compute_scenario_preview` as pure functions. Golden tests with 4-decimal precision.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/scenario/__init__.py`
- [ ] Create `apps/api/src/atlas_api/services/scenario/engine.py`
- [ ] Create `apps/api/tests/test_scenario_engine.py`

### Code

**`apps/api/src/atlas_api/services/scenario/__init__.py`** (CREATE)

```python
```

**`apps/api/src/atlas_api/services/scenario/engine.py`** (CREATE)

```python
"""Deterministic shock engine -- pure functions, no IO.

Takes baseline macro indicators + a ShockVector and produces a ScenarioPreview
with the new risk score, fiscal deltas, and probability of debt distress.
"""

from __future__ import annotations

from atlas_schemas.scenario import ScenarioDeltas, ScenarioPreview, ShockVector

from atlas_api.services.country.risk_score import compute_risk_score
from atlas_api.services.scenario.pod import compute_pod

COMMODITY_SENSITIVITY = 0.15


def apply_shocks(
    baseline_indicators: dict[str, float],
    shocks: ShockVector,
) -> dict[str, float]:
    """Apply a shock vector to baseline macro indicators, returning shocked values.

    This is a pure function: no side effects, no DB access.
    """
    shocked = dict(baseline_indicators)

    # 1. GDP shock: shift growth + denominator effect on debt
    baseline_growth = baseline_indicators.get("GDP_GROWTH_PCT", 0.0)
    new_growth = baseline_growth + shocks.gdp_shock
    shocked["GDP_GROWTH_PCT"] = new_growth

    baseline_debt = baseline_indicators.get("PUBLIC_DEBT_PCT_GDP", 0.0)
    denominator_factor = 1.0 + shocks.gdp_shock / 100.0
    if denominator_factor != 0:
        new_debt = baseline_debt / denominator_factor
    else:
        new_debt = baseline_debt
    shocked["PUBLIC_DEBT_PCT_GDP"] = new_debt

    # 2. Inflation shock
    baseline_inflation = baseline_indicators.get("INFLATION_PCT", 0.0)
    shocked["INFLATION_PCT"] = baseline_inflation + shocks.inflation_shock

    # 3. FX depreciation -- used directly as fx_delta_30d_pct in risk score
    # (does not modify an indicator, passed separately)

    # 4. Rate shock: increases debt via debt service
    # Simplified: new_debt = prev_debt * (1 + rate_shock / 100)
    shocked["PUBLIC_DEBT_PCT_GDP"] = shocked["PUBLIC_DEBT_PCT_GDP"] * (
        1.0 + shocks.rate_shock / 100.0
    )

    # 5. Commodity shock: affects fiscal balance and current account
    baseline_fiscal = baseline_indicators.get("FISCAL_BALANCE_PCT_GDP", 0.0)
    baseline_ca = baseline_indicators.get("CURRENT_ACCOUNT_PCT_GDP", 0.0)
    shocked["FISCAL_BALANCE_PCT_GDP"] = (
        baseline_fiscal + shocks.commodity_shock * COMMODITY_SENSITIVITY
    )
    shocked["CURRENT_ACCOUNT_PCT_GDP"] = (
        baseline_ca + shocks.commodity_shock * COMMODITY_SENSITIVITY
    )

    return shocked


def compute_scenario_preview(
    status: str,
    baseline_indicators: dict[str, float],
    baseline_fx_delta: float | None,
    shocks: ShockVector,
    baseline_risk_composite: float,
) -> ScenarioPreview:
    """Full scenario preview: apply shocks, recompute risk, compute PoD.

    Pure function -- no DB access.
    """
    shocked = apply_shocks(baseline_indicators, shocks)

    # Recompute risk score with shocked indicators + fx_depreciation as the new FX delta
    new_risk = compute_risk_score(
        status=status,
        indicators=shocked,
        fx_delta_30d_pct=shocks.fx_depreciation,
    )

    # Compute PoD
    pod = compute_pod(
        debt_gdp=shocked.get("PUBLIC_DEBT_PCT_GDP", 0.0),
        reserves=shocked.get("FX_RESERVES_MO_IMPORTS", baseline_indicators.get("FX_RESERVES_MO_IMPORTS", 0.0)),
        fiscal_balance=shocked.get("FISCAL_BALANCE_PCT_GDP", 0.0),
        status=status,
    )

    # Compute deltas
    baseline_debt = baseline_indicators.get("PUBLIC_DEBT_PCT_GDP", 0.0)
    baseline_fiscal = baseline_indicators.get("FISCAL_BALANCE_PCT_GDP", 0.0)
    baseline_ca = baseline_indicators.get("CURRENT_ACCOUNT_PCT_GDP", 0.0)
    new_debt = shocked.get("PUBLIC_DEBT_PCT_GDP", 0.0)
    new_fiscal = shocked.get("FISCAL_BALANCE_PCT_GDP", 0.0)
    new_ca = shocked.get("CURRENT_ACCOUNT_PCT_GDP", 0.0)

    return ScenarioPreview(
        baseline_risk_score=baseline_risk_composite,
        new_risk_score=new_risk.composite,
        distress_probability=pod,
        deltas=ScenarioDeltas(
            debt_gdp=round(new_debt - baseline_debt, 4),
            fiscal_balance=round(new_fiscal - baseline_fiscal, 4),
            current_account=round(new_ca - baseline_ca, 4),
        ),
        baseline_debt_gdp=baseline_debt,
        baseline_fiscal_balance=baseline_fiscal,
        baseline_current_account=baseline_ca,
        new_debt_gdp=round(new_debt, 4),
        new_fiscal_balance=round(new_fiscal, 4),
        new_current_account=round(new_ca, 4),
    )
```

**`apps/api/tests/test_scenario_engine.py`** (CREATE)

```python
"""Golden tests for the Scenario Engine shock application."""

import pytest
from atlas_schemas.scenario import ShockVector
from atlas_api.services.scenario.engine import apply_shocks, compute_scenario_preview


# ---------- apply_shocks golden test ----------

BASELINE = {
    "PUBLIC_DEBT_PCT_GDP": 60.0,
    "FISCAL_BALANCE_PCT_GDP": -3.0,
    "CURRENT_ACCOUNT_PCT_GDP": -2.0,
    "GDP_GROWTH_PCT": 4.0,
    "INFLATION_PCT": 8.0,
    "FX_RESERVES_MO_IMPORTS": 4.0,
}

SHOCK = ShockVector(
    gdp_shock=-2.0,
    inflation_shock=5.0,
    fx_depreciation=15.0,
    rate_shock=3.0,
    commodity_shock=-10.0,
)


def test_apply_shocks_golden():
    shocked = apply_shocks(BASELINE, SHOCK)

    # GDP growth: 4.0 + (-2.0) = 2.0
    assert shocked["GDP_GROWTH_PCT"] == pytest.approx(2.0, abs=1e-4)

    # Inflation: 8.0 + 5.0 = 13.0
    assert shocked["INFLATION_PCT"] == pytest.approx(13.0, abs=1e-4)

    # Debt/GDP: 60 / (1 + (-2)/100) * (1 + 3/100)
    # = 60 / 0.98 * 1.03 = 61.2245 * 1.03 = 63.0612
    assert shocked["PUBLIC_DEBT_PCT_GDP"] == pytest.approx(63.0612, abs=1e-3)

    # Fiscal: -3.0 + (-10) * 0.15 = -4.5
    assert shocked["FISCAL_BALANCE_PCT_GDP"] == pytest.approx(-4.5, abs=1e-4)

    # Current account: -2.0 + (-10) * 0.15 = -3.5
    assert shocked["CURRENT_ACCOUNT_PCT_GDP"] == pytest.approx(-3.5, abs=1e-4)

    # Reserves unchanged (no shock modifies them)
    assert shocked["FX_RESERVES_MO_IMPORTS"] == pytest.approx(4.0, abs=1e-4)


def test_apply_shocks_zero_vector_is_identity():
    shocked = apply_shocks(BASELINE, ShockVector())
    for key in BASELINE:
        assert shocked[key] == pytest.approx(BASELINE[key], abs=1e-10), f"{key} changed"


# ---------- compute_scenario_preview golden test ----------

def test_scenario_preview_golden():
    """Full preview with known baseline + shock -> verify all outputs to 4 decimals."""
    preview = compute_scenario_preview(
        status="performing",
        baseline_indicators=BASELINE,
        baseline_fx_delta=-3.0,
        shocks=SHOCK,
        baseline_risk_composite=46.7,
    )

    # New risk score: debt=63.06->5, reserves=4.0->3, fiscal=-4.5->7,
    # growth=2.0->5, inflation=13.0->5, fx=15->7
    # composite = (5+3+7+5+5+7)/6*10 = 53.3
    assert preview.new_risk_score == pytest.approx(53.3, abs=0.1)
    assert preview.baseline_risk_score == pytest.approx(46.7, abs=0.1)

    # Deltas
    assert preview.deltas.debt_gdp == pytest.approx(3.0612, abs=1e-3)
    assert preview.deltas.fiscal_balance == pytest.approx(-1.5, abs=1e-4)
    assert preview.deltas.current_account == pytest.approx(-1.5, abs=1e-4)

    # PoD: 1/(1+exp(-(0.03*63.0612 + 0.5/4.0 - 0.1*(-4.5) - 3.5)))
    # = 1/(1+exp(-(-1.0332))) = 1/(1+exp(1.0332)) ≈ 0.2624
    assert preview.distress_probability == pytest.approx(0.2624, abs=1e-3)


def test_scenario_preview_distressed_country():
    """Distressed country -> PoD is None."""
    preview = compute_scenario_preview(
        status="selective_default",
        baseline_indicators=BASELINE,
        baseline_fx_delta=-3.0,
        shocks=ShockVector(gdp_shock=-1.0),
        baseline_risk_composite=71.7,
    )
    assert preview.distress_probability is None


def test_scenario_preview_zero_shocks():
    """Zero shocks should return deltas near zero (not exactly due to floating point)."""
    preview = compute_scenario_preview(
        status="performing",
        baseline_indicators=BASELINE,
        baseline_fx_delta=-3.0,
        shocks=ShockVector(),
        baseline_risk_composite=46.7,
    )
    assert abs(preview.deltas.debt_gdp) < 1e-10
    assert abs(preview.deltas.fiscal_balance) < 1e-10
    assert abs(preview.deltas.current_account) < 1e-10
```

### Verification

```bash
cd apps/api && python -m pytest tests/test_scenario_engine.py -v --tb=short
```

---

## Task 4 of 11 -- Probability of Debt Distress

**Goal:** Implement `compute_pod` as a pure logistic function. Golden tests for 5 macro states + N/A.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/scenario/pod.py`
- [ ] Create `apps/api/tests/test_pod.py`

### Code

**`apps/api/src/atlas_api/services/scenario/pod.py`** (CREATE)

```python
"""Probability of Debt Distress -- prototype-grade logistic model.

Formula: 1 / (1 + exp(-(0.03 * debt_gdp + 0.5 * (1/reserves) - 0.1 * fiscal_balance - 3.5)))

Returns None for distressed countries (selective_default, default, restructured).
"""

from __future__ import annotations

import math

_DISTRESSED = {"selective_default", "default", "restructured"}


def compute_pod(
    debt_gdp: float,
    reserves: float,
    fiscal_balance: float,
    status: str,
) -> float | None:
    """Compute probability of debt distress via a simple logistic model.

    Pure function -- no IO.

    Args:
        debt_gdp: Public debt as % of GDP.
        reserves: FX reserves in months of imports.
        fiscal_balance: Fiscal balance as % of GDP (negative = deficit).
        status: Country status string (e.g. "performing", "selective_default").

    Returns:
        Float in [0, 1] or None if the country is already in distress.
    """
    if status in _DISTRESSED:
        return None

    # Guard against division by zero on reserves
    inv_reserves = 1.0 / reserves if reserves > 0 else 10.0  # cap at 10 for 0-reserve edge case

    z = 0.03 * debt_gdp + 0.5 * inv_reserves - 0.1 * fiscal_balance - 3.5
    return round(1.0 / (1.0 + math.exp(-z)), 4)
```

**`apps/api/tests/test_pod.py`** (CREATE)

```python
"""Golden tests for Probability of Debt Distress (PoD).

5 macro states + 1 explicit N/A case per spec §10.
"""

import math

import pytest

from atlas_api.services.scenario.pod import compute_pod


def _expected_pod(debt_gdp: float, reserves: float, fiscal_balance: float) -> float:
    """Reference implementation for verification."""
    inv_r = 1.0 / reserves if reserves > 0 else 10.0
    z = 0.03 * debt_gdp + 0.5 * inv_r - 0.1 * fiscal_balance - 3.5
    return round(1.0 / (1.0 + math.exp(-z)), 4)


# 5 macro states spanning low-risk to high-risk
POD_GOLDEN = [
    # (label, debt_gdp, reserves, fiscal, status, expected_pod)
    ("low_risk",       30.0, 8.0,  2.0, "performing",  _expected_pod(30.0, 8.0, 2.0)),
    ("moderate_risk",  60.0, 4.0, -3.0, "performing",  _expected_pod(60.0, 4.0, -3.0)),
    ("elevated_risk",  80.0, 2.5, -6.0, "performing",  _expected_pod(80.0, 2.5, -6.0)),
    ("high_risk",      95.0, 1.5, -8.0, "performing",  _expected_pod(95.0, 1.5, -8.0)),
    ("very_high_risk", 120.0, 0.8, -10.0, "performing", _expected_pod(120.0, 0.8, -10.0)),
]


@pytest.mark.parametrize("label,debt,reserves,fiscal,status,expected", POD_GOLDEN)
def test_pod_golden(label, debt, reserves, fiscal, status, expected):
    result = compute_pod(debt_gdp=debt, reserves=reserves, fiscal_balance=fiscal, status=status)
    assert result == pytest.approx(expected, abs=1e-4), f"{label}: expected {expected}, got {result}"


def test_pod_monotonically_increases_with_debt():
    """Higher debt -> higher PoD, all else equal."""
    pods = [
        compute_pod(debt_gdp=d, reserves=4.0, fiscal_balance=-3.0, status="performing")
        for d in [30.0, 50.0, 70.0, 90.0, 110.0]
    ]
    for i in range(len(pods) - 1):
        assert pods[i] < pods[i + 1], f"PoD did not increase at index {i}"


def test_pod_distressed_returns_none():
    """Explicit N/A case: distressed countries -> None."""
    for status in ("selective_default", "default", "restructured"):
        result = compute_pod(debt_gdp=80.0, reserves=2.0, fiscal_balance=-5.0, status=status)
        assert result is None, f"Expected None for status={status}, got {result}"


def test_pod_zero_reserves():
    """Edge case: zero reserves should not crash, should return high PoD."""
    result = compute_pod(debt_gdp=80.0, reserves=0.0, fiscal_balance=-5.0, status="performing")
    assert result is not None
    assert result > 0.9  # very high distress probability


def test_pod_performing_returns_float():
    """Performing + negotiating countries get a float PoD."""
    for status in ("performing", "negotiating"):
        result = compute_pod(debt_gdp=60.0, reserves=4.0, fiscal_balance=-3.0, status=status)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0


# Committed golden values (4 decimal places)
def test_pod_committed_values():
    """Exact committed values for regression testing."""
    # moderate_risk baseline: debt=60, reserves=4, fiscal=-3
    # z = 0.03*60 + 0.5*(1/4) - 0.1*(-3) - 3.5 = 1.8 + 0.125 + 0.3 - 3.5 = -1.275
    # pod = 1/(1+exp(1.275)) = 1/(1+3.5789) = 0.2184
    assert compute_pod(60.0, 4.0, -3.0, "performing") == pytest.approx(0.2184, abs=1e-4)

    # high_risk: debt=95, reserves=1.5, fiscal=-8
    # z = 0.03*95 + 0.5*(1/1.5) - 0.1*(-8) - 3.5 = 2.85 + 0.3333 + 0.8 - 3.5 = 0.4833
    # pod = 1/(1+exp(-0.4833)) = 1/(1+0.6167) = 0.6185
    assert compute_pod(95.0, 1.5, -8.0, "performing") == pytest.approx(0.6185, abs=1e-3)
```

### Verification

```bash
cd apps/api && python -m pytest tests/test_pod.py -v --tb=short
```

---

## Task 5 of 11 -- Scenario service

**Goal:** Implement service functions that bridge the pure engine with DB reads/writes: `preview_scenario`, `save_scenario`, `get_scenario`, `list_scenarios`.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/scenario/service.py`

### Code

**`apps/api/src/atlas_api/services/scenario/service.py`** (CREATE)

```python
"""Scenario service -- orchestrates DB reads, engine calls, and persistence."""

from __future__ import annotations

import uuid

from atlas_schemas.scenario import ScenarioPreview, ScenarioRunOut, ShockVector
from sqlalchemy.orm import Session

from atlas_api.models import ScenarioRun
from atlas_api.services.country.bundle import get_country_bundle
from atlas_api.services.scenario.engine import compute_scenario_preview


def preview_scenario(
    session: Session,
    iso3: str,
    shocks: ShockVector,
) -> ScenarioPreview:
    """Compute a scenario preview without persisting anything.

    Reads baseline data via the existing country bundle, then runs the shock
    engine in-memory. Target: <500ms.
    """
    iso3 = iso3.upper()
    bundle = get_country_bundle(session, iso3)
    if bundle is None:
        raise ValueError(f"Country {iso3} not found")

    # Extract baseline indicators from macro tiles
    baseline_indicators: dict[str, float] = {}
    for tile in bundle.macro:
        if tile.value is not None:
            baseline_indicators[tile.indicator.value] = tile.value

    # Extract baseline FX delta
    baseline_fx_delta = bundle.fx.delta_30d_pct if bundle.fx is not None else None

    # Extract status
    status = bundle.country.status.value if hasattr(bundle.country.status, "value") else str(bundle.country.status)

    return compute_scenario_preview(
        status=status,
        baseline_indicators=baseline_indicators,
        baseline_fx_delta=baseline_fx_delta,
        shocks=shocks,
        baseline_risk_composite=bundle.risk.composite,
    )


def save_scenario(
    session: Session,
    iso3: str,
    user_id: uuid.UUID,
    shocks: ShockVector,
    preview: ScenarioPreview,
) -> ScenarioRunOut:
    """Persist a scenario run and return the saved record."""
    iso3 = iso3.upper()
    run = ScenarioRun(
        iso3=iso3,
        shocks=shocks.model_dump(),
        outputs=preview.model_dump(),
        created_by=user_id,
        saved=True,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    return ScenarioRunOut(
        id=run.id,
        iso3=run.iso3,
        shocks=ShockVector(**run.shocks),
        outputs=ScenarioPreview(**run.outputs),
        created_by=run.created_by,
        created_at=run.created_at,
        saved=run.saved,
    )


def get_scenario(session: Session, scenario_id: uuid.UUID) -> ScenarioRunOut | None:
    """Retrieve a single saved scenario by ID."""
    run = session.get(ScenarioRun, scenario_id)
    if run is None:
        return None
    return ScenarioRunOut(
        id=run.id,
        iso3=run.iso3,
        shocks=ShockVector(**run.shocks),
        outputs=ScenarioPreview(**run.outputs),
        created_by=run.created_by,
        created_at=run.created_at,
        saved=run.saved,
    )


def list_scenarios(session: Session, iso3: str) -> list[ScenarioRunOut]:
    """List all saved scenarios for a given country, newest first."""
    from sqlalchemy import select

    iso3 = iso3.upper()
    stmt = (
        select(ScenarioRun)
        .where(ScenarioRun.iso3 == iso3, ScenarioRun.saved.is_(True))
        .order_by(ScenarioRun.created_at.desc())
    )
    runs = list(session.execute(stmt).scalars())
    return [
        ScenarioRunOut(
            id=r.id,
            iso3=r.iso3,
            shocks=ShockVector(**r.shocks),
            outputs=ScenarioPreview(**r.outputs),
            created_by=r.created_by,
            created_at=r.created_at,
            saved=r.saved,
        )
        for r in runs
    ]
```

### Verification

Tested indirectly through Task 7 (endpoint integration tests).

---

## Task 6 of 11 -- API endpoints

**Goal:** Wire 4 scenario endpoints into FastAPI: preview, save, get, list.

### Steps

- [ ] Create `apps/api/src/atlas_api/routers/scenarios.py`
- [ ] Modify `apps/api/src/atlas_api/main.py` to include the new router

### Code

**`apps/api/src/atlas_api/routers/scenarios.py`** (CREATE)

```python
"""Scenario Engine API endpoints."""

from __future__ import annotations

import uuid

from atlas_schemas.scenario import ScenarioPreview, ScenarioRunOut, ShockVector
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from atlas_api.deps import CurrentUser, DbSession
from atlas_api.services.scenario.service import (
    get_scenario,
    list_scenarios,
    preview_scenario,
    save_scenario,
)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class PreviewRequest(BaseModel):
    iso3: str
    shocks: ShockVector


class SaveRequest(BaseModel):
    iso3: str
    shocks: ShockVector


@router.post("/preview", response_model=ScenarioPreview)
def post_preview(
    body: PreviewRequest,
    session: DbSession,
    _: CurrentUser,
) -> ScenarioPreview:
    """Compute a scenario preview (no DB writes)."""
    try:
        return preview_scenario(session, body.iso3, body.shocks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=ScenarioRunOut, status_code=status.HTTP_201_CREATED)
def post_save(
    body: SaveRequest,
    session: DbSession,
    user: CurrentUser,
) -> ScenarioRunOut:
    """Preview + persist a scenario run."""
    try:
        preview = preview_scenario(session, body.iso3, body.shocks)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return save_scenario(session, body.iso3, user.id, body.shocks, preview)


@router.get("/{scenario_id}", response_model=ScenarioRunOut)
def get_one(
    scenario_id: uuid.UUID,
    session: DbSession,
    _: CurrentUser,
) -> ScenarioRunOut:
    """Retrieve a saved scenario by ID."""
    result = get_scenario(session, scenario_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"scenario {scenario_id} not found",
        )
    return result


@router.get("", response_model=list[ScenarioRunOut])
def list_all(
    session: DbSession,
    _: CurrentUser,
    iso3: str = Query(..., min_length=3, max_length=3, description="Country ISO3 code"),
) -> list[ScenarioRunOut]:
    """List saved scenarios for a country."""
    return list_scenarios(session, iso3)
```

**`apps/api/src/atlas_api/main.py`** (MODIFY)

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.config import settings
from atlas_api.ingestion.scheduler import build_scheduler
from atlas_api.logging_config import configure_logging
from atlas_api.routers import auth, countries, health, scenarios

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = build_scheduler()
    if settings.ingestion_schedule_enabled:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Atlas API", version="0.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(countries.router)
app.include_router(scenarios.router)
```

### Verification

```bash
cd apps/api && uvicorn atlas_api.main:app --reload &
curl -s http://localhost:8000/docs | head -20  # confirm /api/scenarios endpoints appear
```

---

## Task 7 of 11 -- Endpoint integration tests

**Goal:** Seed a country with macro data, call preview/save/get/list endpoints, verify response shape and values.

### Steps

- [ ] Create `apps/api/tests/test_scenario_endpoints.py`

### Code

**`apps/api/tests/test_scenario_endpoints.py`** (CREATE)

```python
"""Integration tests for scenario endpoints.

Seeds a country + macro data, then exercises preview / save / get / list.
"""

import uuid
from datetime import UTC, datetime

import pytest
from atlas_api.models import Country, DataVintage, MacroIndicatorVintage, User
from atlas_api.security import hash_password


@pytest.fixture()
def seeded(session):
    """Seed a country, user, vintage, and macro data for scenario tests."""
    user = User(
        id=uuid.uuid4(),
        email="analyst@atlas.test",
        password_hash=hash_password("pass1234"),
        role="Analyst",
    )
    session.add(user)

    country = Country(
        iso3="TST",
        name="Testland",
        capital="Testville",
        region="Test Region",
        tags=["test"],
        tier="1",
        status="performing",
        fx_regime="float",
    )
    session.add(country)

    vintage = DataVintage(source="test", notes="test vintage")
    session.add(vintage)
    session.flush()

    indicators = {
        "PUBLIC_DEBT_PCT_GDP": 60.0,
        "FISCAL_BALANCE_PCT_GDP": -3.0,
        "CURRENT_ACCOUNT_PCT_GDP": -2.0,
        "GDP_GROWTH_PCT": 4.0,
        "INFLATION_PCT": 8.0,
        "FX_RESERVES_MO_IMPORTS": 4.0,
    }
    for ind, val in indicators.items():
        session.add(MacroIndicatorVintage(
            iso3="TST",
            indicator=ind,
            value=val,
            source="test",
            period="2025",
            vintage_id=vintage.id,
        ))

    session.commit()
    return {"user": user, "vintage": vintage}


@pytest.fixture()
def auth_client(client, seeded):
    """Client with an active session cookie."""
    resp = client.post("/api/auth/login", json={
        "email": "analyst@atlas.test",
        "password": "pass1234",
    })
    assert resp.status_code == 200, resp.text
    return client


def test_preview_returns_shocked_values(auth_client):
    resp = auth_client.post("/api/scenarios/preview", json={
        "iso3": "TST",
        "shocks": {
            "gdp_shock": -2.0,
            "inflation_shock": 5.0,
            "fx_depreciation": 15.0,
            "rate_shock": 3.0,
            "commodity_shock": -10.0,
        },
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "new_risk_score" in data
    assert "distress_probability" in data
    assert "deltas" in data
    assert data["distress_probability"] is not None  # performing country
    assert data["deltas"]["fiscal_balance"] < 0  # negative shock


def test_preview_unknown_country_404(auth_client):
    resp = auth_client.post("/api/scenarios/preview", json={
        "iso3": "ZZZ",
        "shocks": {"gdp_shock": -1.0},
    })
    assert resp.status_code == 404


def test_save_then_get(auth_client):
    # Save
    resp = auth_client.post("/api/scenarios", json={
        "iso3": "TST",
        "shocks": {"gdp_shock": -2.0, "inflation_shock": 3.0},
    })
    assert resp.status_code == 201, resp.text
    saved = resp.json()
    assert "id" in saved
    scenario_id = saved["id"]

    # Get
    resp2 = auth_client.get(f"/api/scenarios/{scenario_id}")
    assert resp2.status_code == 200
    fetched = resp2.json()
    assert fetched["id"] == scenario_id
    assert fetched["iso3"] == "TST"
    assert fetched["shocks"]["gdp_shock"] == -2.0


def test_list_by_iso3(auth_client):
    # Save two scenarios
    auth_client.post("/api/scenarios", json={
        "iso3": "TST", "shocks": {"gdp_shock": -1.0},
    })
    auth_client.post("/api/scenarios", json={
        "iso3": "TST", "shocks": {"gdp_shock": -3.0},
    })

    resp = auth_client.get("/api/scenarios?iso3=TST")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 2
    # Newest first
    assert items[0]["shocks"]["gdp_shock"] == -3.0


def test_get_nonexistent_404(auth_client):
    resp = auth_client.get(f"/api/scenarios/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_preview_requires_auth(client):
    resp = client.post("/api/scenarios/preview", json={
        "iso3": "TST", "shocks": {"gdp_shock": -1.0},
    })
    assert resp.status_code == 401
```

### Verification

```bash
cd apps/api && python -m pytest tests/test_scenario_endpoints.py -v --tb=short
```

---

## Task 8 of 11 -- ScenarioEngine page

**Goal:** Build the `/scenarios/new?country=XXX` page with 5 range sliders, 300ms debounced preview, live output display.

### Steps

- [ ] Create `apps/web/src/routes/ScenarioEngine.tsx`

### Code

**`apps/web/src/routes/ScenarioEngine.tsx`** (CREATE)

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { RiskGauge } from "@atlas/design-system";
import { api } from "../api/client";
import AppShell from "./AppShell";

interface ScenarioDeltas {
  debt_gdp: number;
  fiscal_balance: number;
  current_account: number;
}

interface ScenarioPreview {
  baseline_risk_score: number;
  new_risk_score: number;
  distress_probability: number | null;
  deltas: ScenarioDeltas;
  baseline_debt_gdp: number;
  baseline_fiscal_balance: number;
  baseline_current_account: number;
  new_debt_gdp: number;
  new_fiscal_balance: number;
  new_current_account: number;
}

interface ShockVector {
  gdp_shock: number;
  inflation_shock: number;
  fx_depreciation: number;
  rate_shock: number;
  commodity_shock: number;
}

const SLIDER_CONFIG: {
  key: keyof ShockVector;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  { key: "gdp_shock", label: "GDP Growth Shock", min: -20, max: 20, step: 0.5, unit: "pp" },
  { key: "inflation_shock", label: "Inflation Shock", min: -20, max: 20, step: 0.5, unit: "pp" },
  { key: "fx_depreciation", label: "FX Depreciation", min: -50, max: 100, step: 1, unit: "%" },
  { key: "rate_shock", label: "Interest Rate Shock", min: -10, max: 20, step: 0.5, unit: "pp" },
  { key: "commodity_shock", label: "Commodity Price Shock", min: -50, max: 50, step: 1, unit: "%" },
];

function fmtDelta(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}`;
}

export default function ScenarioEngine() {
  const [params] = useSearchParams();
  const iso3 = (params.get("country") ?? "").toUpperCase();

  const [shocks, setShocks] = useState<ShockVector>({
    gdp_shock: 0,
    inflation_shock: 0,
    fx_depreciation: 0,
    rate_shock: 0,
    commodity_shock: 0,
  });

  const [preview, setPreview] = useState<ScenarioPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPreview = useCallback(
    async (s: ShockVector) => {
      if (!iso3) return;
      setLoading(true);
      setError(null);
      try {
        const result = await api<ScenarioPreview>("/api/scenarios/preview", {
          method: "POST",
          body: JSON.stringify({ iso3, shocks: s }),
        });
        setPreview(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Preview failed");
      } finally {
        setLoading(false);
      }
    },
    [iso3],
  );

  // Debounced preview: 300ms after last slider change
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => fetchPreview(shocks), 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [shocks, fetchPreview]);

  const handleSlider = (key: keyof ShockVector, value: number) => {
    setShocks((prev) => ({ ...prev, [key]: value }));
    setSavedId(null);
  };

  const handleSave = async () => {
    if (!iso3) return;
    setSaving(true);
    try {
      const result = await api<{ id: string }>("/api/scenarios", {
        method: "POST",
        body: JSON.stringify({ iso3, shocks }),
      });
      setSavedId(result.id);
    } catch {
      setError("Failed to save scenario");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setShocks({
      gdp_shock: 0,
      inflation_shock: 0,
      fx_depreciation: 0,
      rate_shock: 0,
      commodity_shock: 0,
    });
    setSavedId(null);
  };

  if (!iso3) {
    return (
      <AppShell>
        <main className="p-8 text-danger">Missing country parameter.</main>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-5xl p-6">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-semibold text-ink-900">Scenario Engine</h1>
            <span className="font-mono text-sm text-ink-500">{iso3}</span>
          </div>
          <p className="mt-1 text-sm text-ink-500">
            Adjust the macro shock sliders to see how the risk profile changes.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Left: Sliders */}
          <section>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-500">
              Shock Vector
            </h2>
            <div className="space-y-4">
              {SLIDER_CONFIG.map((cfg) => (
                <div key={cfg.key} className="rounded-md border border-ink-100 bg-white p-4">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor={cfg.key}
                      className="text-sm font-medium text-ink-700"
                    >
                      {cfg.label}
                    </label>
                    <span className="font-mono text-sm text-ink-900">
                      {shocks[cfg.key] >= 0 ? "+" : ""}
                      {shocks[cfg.key].toFixed(1)} {cfg.unit}
                    </span>
                  </div>
                  <input
                    id={cfg.key}
                    type="range"
                    min={cfg.min}
                    max={cfg.max}
                    step={cfg.step}
                    value={shocks[cfg.key]}
                    onChange={(e) => handleSlider(cfg.key, parseFloat(e.target.value))}
                    className="mt-2 w-full accent-atlas-600"
                  />
                  <div className="mt-1 flex justify-between text-[10px] text-ink-300">
                    <span>{cfg.min} {cfg.unit}</span>
                    <span>0</span>
                    <span>{cfg.max} {cfg.unit}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 flex gap-3">
              <button
                onClick={handleSave}
                disabled={saving || !preview}
                className="rounded-md bg-atlas-600 px-4 py-2 text-sm font-medium text-white hover:bg-atlas-700 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Scenario"}
              </button>
              <button
                onClick={handleReset}
                className="rounded-md border border-ink-200 px-4 py-2 text-sm font-medium text-ink-700 hover:bg-ink-50"
              >
                Reset
              </button>
            </div>
            {savedId && (
              <p className="mt-2 text-sm text-positive">
                Saved!{" "}
                <Link to={`/scenarios/${savedId}`} className="underline">
                  View saved scenario
                </Link>
              </p>
            )}
          </section>

          {/* Right: Results */}
          <section>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-500">
              Scenario Output
            </h2>

            {loading && <p className="text-sm text-ink-500">Computing...</p>}
            {error && <p className="text-sm text-danger">{error}</p>}

            {preview && !loading && (
              <div className="space-y-4">
                {/* Risk Score comparison */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-md border border-ink-100 bg-white p-4 text-center">
                    <div className="text-xs text-ink-500">Baseline Risk</div>
                    <div className="mt-1 font-mono text-2xl text-ink-900">
                      {preview.baseline_risk_score.toFixed(1)}
                    </div>
                  </div>
                  <div className="rounded-md border border-ink-100 bg-white p-4 text-center">
                    <div className="text-xs text-ink-500">Shocked Risk</div>
                    <div
                      className={`mt-1 font-mono text-2xl ${
                        preview.new_risk_score > preview.baseline_risk_score
                          ? "text-danger"
                          : preview.new_risk_score < preview.baseline_risk_score
                            ? "text-positive"
                            : "text-ink-900"
                      }`}
                    >
                      {preview.new_risk_score.toFixed(1)}
                    </div>
                  </div>
                </div>

                {/* PoD */}
                <div className="rounded-md border border-ink-100 bg-white p-4">
                  <div className="text-xs text-ink-500">Probability of Debt Distress</div>
                  <div className="mt-1 font-mono text-lg text-ink-900">
                    {preview.distress_probability != null
                      ? `${(preview.distress_probability * 100).toFixed(1)}%`
                      : "Not applicable -- country in distressed status"}
                  </div>
                </div>

                {/* Deltas table */}
                <div className="rounded-md border border-ink-100 bg-white p-4">
                  <div className="text-xs text-ink-500 mb-2">Fiscal Deltas</div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-ink-100 text-left text-xs text-ink-500">
                        <th className="pb-1">Metric</th>
                        <th className="pb-1 text-right">Baseline</th>
                        <th className="pb-1 text-right">Shocked</th>
                        <th className="pb-1 text-right">Delta</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      <tr>
                        <td className="py-1 text-ink-700">Debt / GDP</td>
                        <td className="py-1 text-right">{preview.baseline_debt_gdp.toFixed(1)}%</td>
                        <td className="py-1 text-right">{preview.new_debt_gdp.toFixed(1)}%</td>
                        <td className={`py-1 text-right ${preview.deltas.debt_gdp > 0 ? "text-danger" : "text-positive"}`}>
                          {fmtDelta(preview.deltas.debt_gdp)} pp
                        </td>
                      </tr>
                      <tr>
                        <td className="py-1 text-ink-700">Fiscal Balance</td>
                        <td className="py-1 text-right">{preview.baseline_fiscal_balance.toFixed(1)}%</td>
                        <td className="py-1 text-right">{preview.new_fiscal_balance.toFixed(1)}%</td>
                        <td className={`py-1 text-right ${preview.deltas.fiscal_balance < 0 ? "text-danger" : "text-positive"}`}>
                          {fmtDelta(preview.deltas.fiscal_balance)} pp
                        </td>
                      </tr>
                      <tr>
                        <td className="py-1 text-ink-700">Current Account</td>
                        <td className="py-1 text-right">{preview.baseline_current_account.toFixed(1)}%</td>
                        <td className="py-1 text-right">{preview.new_current_account.toFixed(1)}%</td>
                        <td className={`py-1 text-right ${preview.deltas.current_account < 0 ? "text-danger" : "text-positive"}`}>
                          {fmtDelta(preview.deltas.current_account)} pp
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    </AppShell>
  );
}
```

### Verification

```bash
cd apps/web && npx tsc --noEmit
# Then manual: navigate to /scenarios/new?country=KEN and adjust sliders
```

---

## Task 9 of 11 -- ScenarioView page

**Goal:** Build the `/scenarios/:id` page that displays a saved scenario's inputs and outputs in readonly mode.

### Steps

- [ ] Create `apps/web/src/routes/ScenarioView.tsx`

### Code

**`apps/web/src/routes/ScenarioView.tsx`** (CREATE)

```tsx
import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { ApiError, api } from "../api/client";
import AppShell from "./AppShell";

interface ScenarioDeltas {
  debt_gdp: number;
  fiscal_balance: number;
  current_account: number;
}

interface ScenarioPreview {
  baseline_risk_score: number;
  new_risk_score: number;
  distress_probability: number | null;
  deltas: ScenarioDeltas;
  baseline_debt_gdp: number;
  baseline_fiscal_balance: number;
  baseline_current_account: number;
  new_debt_gdp: number;
  new_fiscal_balance: number;
  new_current_account: number;
}

interface ShockVector {
  gdp_shock: number;
  inflation_shock: number;
  fx_depreciation: number;
  rate_shock: number;
  commodity_shock: number;
}

interface ScenarioRunOut {
  id: string;
  iso3: string;
  shocks: ShockVector;
  outputs: ScenarioPreview;
  created_by: string;
  created_at: string;
  saved: boolean;
}

const SHOCK_LABELS: Record<keyof ShockVector, { label: string; unit: string }> = {
  gdp_shock: { label: "GDP Growth Shock", unit: "pp" },
  inflation_shock: { label: "Inflation Shock", unit: "pp" },
  fx_depreciation: { label: "FX Depreciation", unit: "%" },
  rate_shock: { label: "Interest Rate Shock", unit: "pp" },
  commodity_shock: { label: "Commodity Price Shock", unit: "%" },
};

function fmtDelta(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}`;
}

export default function ScenarioView() {
  const { id = "" } = useParams();
  const { data, isLoading, error } = useQuery<ScenarioRunOut>({
    queryKey: ["scenario", id],
    queryFn: () => api<ScenarioRunOut>(`/api/scenarios/${id}`),
    staleTime: 60 * 1000,
    retry: false,
  });

  if (isLoading) {
    return <AppShell><main className="p-8 text-ink-500">Loading...</main></AppShell>;
  }
  if (error) {
    const msg = error instanceof ApiError && error.status === 404
      ? "Scenario not found"
      : "Failed to load scenario";
    return <AppShell><main className="p-8 text-danger">{msg}</main></AppShell>;
  }
  if (!data) return null;

  const { iso3, shocks, outputs, created_at } = data;

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl p-6">
        <header className="mb-6">
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-semibold text-ink-900">Saved Scenario</h1>
            <span className="font-mono text-sm text-ink-500">{iso3}</span>
          </div>
          <p className="mt-1 text-xs text-ink-400">
            Created {new Date(created_at).toLocaleString()}
          </p>
          <div className="mt-2 flex gap-3">
            <Link
              to={`/countries/${iso3}`}
              className="text-sm text-atlas-600 hover:underline"
            >
              Back to country profile
            </Link>
            <Link
              to={`/scenarios/new?country=${iso3}`}
              className="text-sm text-atlas-600 hover:underline"
            >
              Run new scenario
            </Link>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Inputs */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-500">
              Shock Inputs
            </h2>
            <div className="rounded-md border border-ink-100 bg-white p-4">
              <table className="w-full text-sm">
                <tbody>
                  {(Object.keys(SHOCK_LABELS) as (keyof ShockVector)[]).map((key) => (
                    <tr key={key} className="border-b border-ink-50 last:border-0">
                      <td className="py-2 text-ink-700">{SHOCK_LABELS[key].label}</td>
                      <td className="py-2 text-right font-mono text-ink-900">
                        {shocks[key] >= 0 ? "+" : ""}{shocks[key].toFixed(1)} {SHOCK_LABELS[key].unit}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Outputs */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-500">
              Results
            </h2>
            <div className="space-y-3">
              {/* Risk comparison */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border border-ink-100 bg-white p-3 text-center">
                  <div className="text-xs text-ink-500">Baseline Risk</div>
                  <div className="mt-1 font-mono text-xl text-ink-900">
                    {outputs.baseline_risk_score.toFixed(1)}
                  </div>
                </div>
                <div className="rounded-md border border-ink-100 bg-white p-3 text-center">
                  <div className="text-xs text-ink-500">Shocked Risk</div>
                  <div
                    className={`mt-1 font-mono text-xl ${
                      outputs.new_risk_score > outputs.baseline_risk_score
                        ? "text-danger"
                        : outputs.new_risk_score < outputs.baseline_risk_score
                          ? "text-positive"
                          : "text-ink-900"
                    }`}
                  >
                    {outputs.new_risk_score.toFixed(1)}
                  </div>
                </div>
              </div>

              {/* PoD */}
              <div className="rounded-md border border-ink-100 bg-white p-3">
                <div className="text-xs text-ink-500">Probability of Debt Distress</div>
                <div className="mt-1 font-mono text-ink-900">
                  {outputs.distress_probability != null
                    ? `${(outputs.distress_probability * 100).toFixed(1)}%`
                    : "Not applicable -- country in distressed status"}
                </div>
              </div>

              {/* Deltas */}
              <div className="rounded-md border border-ink-100 bg-white p-3">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-ink-100 text-left text-xs text-ink-500">
                      <th className="pb-1">Metric</th>
                      <th className="pb-1 text-right">Baseline</th>
                      <th className="pb-1 text-right">Shocked</th>
                      <th className="pb-1 text-right">Delta</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono text-sm">
                    <tr>
                      <td className="py-1 text-ink-700">Debt / GDP</td>
                      <td className="py-1 text-right">{outputs.baseline_debt_gdp.toFixed(1)}%</td>
                      <td className="py-1 text-right">{outputs.new_debt_gdp.toFixed(1)}%</td>
                      <td className="py-1 text-right">{fmtDelta(outputs.deltas.debt_gdp)} pp</td>
                    </tr>
                    <tr>
                      <td className="py-1 text-ink-700">Fiscal Balance</td>
                      <td className="py-1 text-right">{outputs.baseline_fiscal_balance.toFixed(1)}%</td>
                      <td className="py-1 text-right">{outputs.new_fiscal_balance.toFixed(1)}%</td>
                      <td className="py-1 text-right">{fmtDelta(outputs.deltas.fiscal_balance)} pp</td>
                    </tr>
                    <tr>
                      <td className="py-1 text-ink-700">Current Account</td>
                      <td className="py-1 text-right">{outputs.baseline_current_account.toFixed(1)}%</td>
                      <td className="py-1 text-right">{outputs.new_current_account.toFixed(1)}%</td>
                      <td className="py-1 text-right">{fmtDelta(outputs.deltas.current_account)} pp</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>
      </main>
    </AppShell>
  );
}
```

### Verification

```bash
cd apps/web && npx tsc --noEmit
```

---

## Task 10 of 11 -- Nav + routing

**Goal:** Add scenario routes to `App.tsx` and a "Run Scenario" button on the country profile page.

### Steps

- [ ] Modify `apps/web/src/App.tsx` to add `/scenarios/new` and `/scenarios/:id` routes
- [ ] Modify `apps/web/src/routes/CountryProfile.tsx` to add "Run Scenario" link

### Code

**`apps/web/src/App.tsx`** (MODIFY -- full file)

```tsx
import { Route, Routes } from "react-router-dom";
import Login from "./routes/Login";
import Home from "./routes/Home";
import CountriesList from "./routes/CountriesList";
import CountryProfile from "./routes/CountryProfile";
import ScenarioEngine from "./routes/ScenarioEngine";
import ScenarioView from "./routes/ScenarioView";
import RequireAuth from "./routes/RequireAuth";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
      <Route path="/countries" element={<RequireAuth><CountriesList /></RequireAuth>} />
      <Route path="/countries/:iso3" element={<RequireAuth><CountryProfile /></RequireAuth>} />
      <Route path="/scenarios/new" element={<RequireAuth><ScenarioEngine /></RequireAuth>} />
      <Route path="/scenarios/:id" element={<RequireAuth><ScenarioView /></RequireAuth>} />
    </Routes>
  );
}
```

**`apps/web/src/routes/CountryProfile.tsx`** (MODIFY -- add "Run Scenario" link in header)

Find the header section:

```tsx
        <header className="mb-6">
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-semibold text-ink-900">{country.name}</h1>
            <span className="font-mono text-sm text-ink-500">{country.iso3}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-ink-500">
```

Replace with:

```tsx
        <header className="mb-6">
          <div className="flex items-baseline justify-between">
            <div className="flex items-baseline gap-3">
              <h1 className="text-2xl font-semibold text-ink-900">{country.name}</h1>
              <span className="font-mono text-sm text-ink-500">{country.iso3}</span>
            </div>
            <Link
              to={`/scenarios/new?country=${country.iso3}`}
              className="rounded-md bg-atlas-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-atlas-700"
            >
              Run Scenario
            </Link>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-ink-500">
```

Also add the `Link` import at the top of CountryProfile.tsx:

```tsx
import { useParams, Link } from "react-router-dom";
```

(Change `import { useParams } from "react-router-dom";` to include `Link`.)

### Verification

```bash
cd apps/web && npx tsc --noEmit
```

---

## Task 11 of 11 -- Manual smoke + optional tag

**Goal:** Manual end-to-end walkthrough: country profile -> scenario engine -> adjust sliders -> live feedback -> save -> view saved.

### Steps

- [ ] Start backend: `cd apps/api && uvicorn atlas_api.main:app --reload`
- [ ] Run migration: `cd /Users/bird/Documents/ATLAS/atlas && alembic upgrade head`
- [ ] Start frontend: `cd apps/web && npm run dev`
- [ ] Navigate to `/countries/KEN` (or any seeded country)
- [ ] Click "Run Scenario" button in the header
- [ ] Verify page loads at `/scenarios/new?country=KEN`
- [ ] Adjust GDP Growth Shock slider to -3.0 pp
- [ ] Verify preview updates within ~300ms showing increased risk score
- [ ] Adjust FX Depreciation slider to +20%
- [ ] Verify risk score increases further, PoD shows a percentage
- [ ] Click "Save Scenario"
- [ ] Verify "Saved!" message appears with a link
- [ ] Click the link to navigate to `/scenarios/{id}`
- [ ] Verify ScenarioView page shows the correct inputs and outputs
- [ ] Click "Back to country profile" link and verify navigation works
- [ ] Navigate to a distressed country (e.g., ETH if status=selective_default)
- [ ] Run a scenario and verify PoD shows "Not applicable -- country in distressed status"
- [ ] Run all backend tests: `cd apps/api && python -m pytest -v --tb=short`
- [ ] Run schema tests: `cd packages/schemas && python -m pytest -v --tb=short`
- [ ] Run frontend type check: `cd apps/web && npx tsc --noEmit`
- [ ] Optionally tag: `git tag plan-4a-scenario-engine`

### Checklist

```
[ ] Country profile shows "Run Scenario" button
[ ] ScenarioEngine page loads with 5 sliders at 0
[ ] Debounced preview fires ~300ms after slider change
[ ] Risk score updates live (baseline vs shocked)
[ ] PoD shows percentage for performing countries
[ ] PoD shows N/A message for distressed countries
[ ] Fiscal deltas table shows baseline/shocked/delta
[ ] Save persists to DB and returns ID
[ ] ScenarioView page renders saved inputs + outputs
[ ] GET /api/scenarios?iso3=XXX returns saved scenarios
[ ] All pytest tests pass
[ ] TypeScript compiles clean
```

---

## Self-review

### Spec coverage

| Spec section | Requirement | Covered in task |
|---|---|---|
| §6.5 | 5 sliders -> debounced POST preview | Task 8 |
| §6.5 | Deterministic engine -> Risk Score + deltas + PoD | Tasks 3, 4 |
| §6.5 | Response <500ms | Task 5 (no DB writes on preview, pure computation) |
| §6.5 | Save button -> POST /api/scenarios | Tasks 6, 8 |
| §6.5 | View saved -> GET /api/scenarios/:id | Tasks 6, 9 |
| §6.5 | List saved -> GET /api/scenarios?iso3=XXX | Task 6 |
| §8 | Distressed -> PoD = N/A | Task 4 |
| §4 | /scenarios/new?country=XXX | Tasks 8, 10 |
| §4 | /scenarios/:id | Tasks 9, 10 |
| §10 | Golden tests 4 decimal | Tasks 3, 4 |
| §10 | PoD for 5 macro states + N/A | Task 4 |
| §14.3 | tenant_id on scenario_run | Task 2 |
| §5 | Multi-tenancy hook | Task 2 |

### Placeholder scan

- No `TODO`, `FIXME`, or `pass` statements in any production code.
- No placeholder values -- all shock coefficients and PoD formula terms are committed.
- `commodity_sensitivity = 0.15` is a named constant.

### Type consistency

- All Pydantic models use `float | None` (not `Optional`).
- All `StrEnum` usage follows project convention.
- `server_default=func.now()` + Python `default=lambda: datetime.now(UTC)` used for timestamps.
- `values_callable` not needed here (no `SqlEnum` columns in `ScenarioRun` -- shocks/outputs are JSONB).
- `Annotated[..., Depends()]` pattern used via existing `DbSession` and `CurrentUser`.

### Import graph

```
scenarios.py (router)
  -> service.py
    -> engine.py -> compute_risk_score (existing), pod.py
    -> bundle.py (existing) -> queries.py (existing)
  -> models.py (ScenarioRun)
  -> deps.py (DbSession, CurrentUser)
```

No circular imports. The scenario module only depends on the existing country service layer for baseline data.

---

## Execution handoff

To execute this plan task-by-task:

```
/superpowers:execute-plan docs/superpowers/plans/2026-04-17-atlas-scenario-engine.md
```

Or for parallel execution with sub-agents:

```
/superpowers:subagent-driven-development docs/superpowers/plans/2026-04-17-atlas-scenario-engine.md
```

Tasks 1-4 can run in parallel (schemas, migration, engine, PoD are independent). Tasks 5-6 depend on 1-4. Task 7 depends on 6. Tasks 8-9 depend on 1. Task 10 depends on 8-9. Task 11 depends on all.
