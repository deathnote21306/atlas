"""Golden tests for the 6-dimension Risk Score."""

import pytest
from atlas_api.services.country.risk_score import bucket_score, compute_risk_score


@pytest.mark.parametrize(
    "value,brackets,expected",
    [
        (20.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 1),
        (40.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 3),
        (60.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 5),
        (80.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 7),
        (95.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 9),
        (30.0, [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)], 3),
    ],
)
def test_bucket_score(value, brackets, expected):
    assert bucket_score(value, brackets) == expected


GOLDEN_SCENARIOS = [
    # (iso3, status, indicators, fx_delta_30d, expected_composite)
    ("GHA", "restructured",
     {"PUBLIC_DEBT_PCT_GDP": 83.0, "FX_RESERVES_MO_IMPORTS": 3.1,
      "FISCAL_BALANCE_PCT_GDP": -4.5, "GDP_GROWTH_PCT": 3.1,
      "INFLATION_PCT": 22.0},
     -8.0,
     round((10 + 5 + 7 + 3 + 7 + 5) / 6 * 10, 1)),  # 61.7

    ("KEN", "performing",
     {"PUBLIC_DEBT_PCT_GDP": 73.0, "FX_RESERVES_MO_IMPORTS": 4.2,
      "FISCAL_BALANCE_PCT_GDP": -5.5, "GDP_GROWTH_PCT": 5.4,
      "INFLATION_PCT": 6.5},
     -1.5,
     round((7 + 3 + 9 + 1 + 3 + 1) / 6 * 10, 1)),  # 40.0

    ("CIV", "performing",
     {"PUBLIC_DEBT_PCT_GDP": 55.0, "FX_RESERVES_MO_IMPORTS": 5.0,
      "FISCAL_BALANCE_PCT_GDP": -4.0, "GDP_GROWTH_PCT": 6.5,
      "INFLATION_PCT": 2.5},
     0.0,
     round((5 + 3 + 7 + 1 + 1 + 1) / 6 * 10, 1)),  # 30.0

    ("ETH", "selective_default",
     {"PUBLIC_DEBT_PCT_GDP": 38.0, "FX_RESERVES_MO_IMPORTS": 1.5,
      "FISCAL_BALANCE_PCT_GDP": -3.2, "GDP_GROWTH_PCT": 6.1,
      "INFLATION_PCT": 25.0},
     -25.0,
     round((10 + 9 + 7 + 1 + 7 + 9) / 6 * 10, 1)),  # 71.7

    ("ZAF", "performing",
     {"PUBLIC_DEBT_PCT_GDP": 74.0, "FX_RESERVES_MO_IMPORTS": 4.5,
      "FISCAL_BALANCE_PCT_GDP": -4.8, "GDP_GROWTH_PCT": 1.1,
      "INFLATION_PCT": 5.3},
     -3.0,
     round((7 + 3 + 7 + 5 + 3 + 3) / 6 * 10, 1)),  # 46.7
]


@pytest.mark.parametrize("iso3,status,indicators,fx_delta,expected", GOLDEN_SCENARIOS)
def test_risk_score_golden(iso3, status, indicators, fx_delta, expected):
    result = compute_risk_score(status=status, indicators=indicators, fx_delta_30d_pct=fx_delta)
    assert result.composite == pytest.approx(expected), (
        f"{iso3}: expected {expected}, got {result.composite}"
    )


def test_risk_score_handles_all_missing():
    result = compute_risk_score(status="performing", indicators={}, fx_delta_30d_pct=None)
    assert result.composite == pytest.approx(50.0)
    assert len(result.dimensions) == 6
    assert all(d.is_estimate for d in result.dimensions)


def test_risk_score_distressed_auto_debt_max():
    result = compute_risk_score(
        status="restructured",
        indicators={"PUBLIC_DEBT_PCT_GDP": 10.0},
        fx_delta_30d_pct=0.0,
    )
    debt = next(d for d in result.dimensions if d.dimension.value == "debt_burden")
    assert debt.score == 10


def test_risk_score_dimensions_are_ordered_canonically():
    result = compute_risk_score(status="performing", indicators={}, fx_delta_30d_pct=None)
    order = [d.dimension.value for d in result.dimensions]
    assert order == [
        "debt_burden", "external_liquidity", "fiscal_flexibility",
        "growth_momentum", "inflation_pressure", "fx_stability",
    ]
