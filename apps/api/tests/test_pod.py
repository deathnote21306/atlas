"""Golden tests for Probability of Debt Distress (PoD).

5 macro states + 1 explicit N/A case per spec S10.
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
    ("low_risk", 30.0, 8.0, 2.0, "performing", _expected_pod(30.0, 8.0, 2.0)),
    ("moderate_risk", 60.0, 4.0, -3.0, "performing", _expected_pod(60.0, 4.0, -3.0)),
    ("elevated_risk", 80.0, 2.5, -6.0, "performing", _expected_pod(80.0, 2.5, -6.0)),
    ("high_risk", 95.0, 1.5, -8.0, "performing", _expected_pod(95.0, 1.5, -8.0)),
    ("very_high_risk", 120.0, 0.8, -10.0, "performing", _expected_pod(120.0, 0.8, -10.0)),
]


@pytest.mark.parametrize("label,debt,reserves,fiscal,status,expected", POD_GOLDEN)
def test_pod_golden(label, debt, reserves, fiscal, status, expected):
    result = compute_pod(debt_gdp=debt, reserves=reserves, fiscal_balance=fiscal, status=status)
    assert result == pytest.approx(expected, abs=1e-4), (
        f"{label}: expected {expected}, got {result}"
    )


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
