"""Scenario Engine schemas for shock analysis."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ShockVector(BaseModel):
    gdp_shock: float = Field(0.0, ge=-20.0, le=20.0)
    inflation_shock: float = Field(0.0, ge=-20.0, le=20.0)
    fx_depreciation: float = Field(0.0, ge=-50.0, le=100.0)
    rate_shock: float = Field(0.0, ge=-10.0, le=20.0)
    commodity_shock: float = Field(0.0, ge=-50.0, le=50.0)


class ScenarioDeltas(BaseModel):
    debt_gdp: float
    fiscal_balance: float
    current_account: float


class ScenarioPreview(BaseModel):
    baseline_risk_score: float
    new_risk_score: float
    distress_probability: float | None = None
    deltas: ScenarioDeltas
    baseline_debt_gdp: float
    baseline_fiscal_balance: float
    baseline_current_account: float
    new_debt_gdp: float
    new_fiscal_balance: float
    new_current_account: float


class CountryImpact(BaseModel):
    iso3: str
    name: str
    status: str
    baseline_risk: float
    new_risk: float
    risk_change: float
    deltas: ScenarioDeltas
    distress_probability: float | None = None


class ScenarioRunOut(BaseModel):
    id: uuid.UUID
    iso3: str
    title: str = ""
    description: str | None = None
    shocks: ShockVector
    outputs: ScenarioPreview
    created_by: uuid.UUID
    created_at: datetime
    saved: bool = True
