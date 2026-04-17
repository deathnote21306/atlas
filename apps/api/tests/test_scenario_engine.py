"""Golden tests for the Scenario Engine shock application."""

import pytest
from atlas_api.services.scenario.engine import (
    apply_shocks,
    compute_scenario_preview,
)
from atlas_schemas.scenario import ShockVector

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
