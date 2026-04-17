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
