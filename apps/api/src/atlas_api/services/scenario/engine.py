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
    new_debt = baseline_debt / denominator_factor if denominator_factor != 0 else baseline_debt
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
        reserves=shocked.get(
            "FX_RESERVES_MO_IMPORTS",
            baseline_indicators.get("FX_RESERVES_MO_IMPORTS", 0.0),
        ),
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
