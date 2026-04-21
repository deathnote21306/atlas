"""Bull/Bear scenario computation via risk-scaled dispersion."""

from __future__ import annotations

from typing import Any

INDICATOR_CONFIG = [
    {
        "key": "real_gdp_growth",
        "db_key": "GDP_GROWTH_PCT",
        "label": "Real GDP Growth",
        "unit": "%",
        "direction": "higher_better",
        "base_width": 1.5,
        "clamp": (-10, 15),
    },
    {
        "key": "cpi_inflation",
        "db_key": "INFLATION_PCT",
        "label": "CPI Inflation",
        "unit": "%",
        "direction": "lower_better",
        "base_width": 3.0,
        "clamp": (0, 100),
    },
    {
        "key": "fiscal_balance_pct_gdp",
        "db_key": "FISCAL_BALANCE_PCT_GDP",
        "label": "Fiscal Balance",
        "unit": "% GDP",
        "direction": "higher_better",
        "base_width": 1.0,
        "clamp": (-15, 10),
    },
    {
        "key": "current_account_pct_gdp",
        "db_key": "CURRENT_ACCOUNT_PCT_GDP",
        "label": "Current Account",
        "unit": "% GDP",
        "direction": "higher_better",
        "base_width": 2.0,
        "clamp": (-20, 20),
    },
]


def compute_scenario(
    baseline: float | None,
    base_width: float,
    risk_multiplier: float,
    direction: str,
    clamp: tuple[float, float],
) -> dict[str, Any]:
    if baseline is None:
        return {
            "bull": None,
            "baseline": None,
            "bear": None,
            "bull_clamped": False,
            "bear_clamped": False,
            "baseline_provenance": "missing",
        }

    spread = base_width * risk_multiplier

    if direction == "higher_better":
        bull_raw = baseline + spread
        bear_raw = baseline - spread
    else:
        bull_raw = baseline - spread
        bear_raw = baseline + spread

    bull_clamped = bull_raw < clamp[0] or bull_raw > clamp[1]
    bear_clamped = bear_raw < clamp[0] or bear_raw > clamp[1]

    bull = max(clamp[0], min(clamp[1], bull_raw))
    bear = max(clamp[0], min(clamp[1], bear_raw))

    return {
        "bull": round(bull, 1),
        "baseline": round(baseline, 1),
        "bear": round(bear, 1),
        "bull_clamped": bull_clamped,
        "bear_clamped": bear_clamped,
        "baseline_provenance": "real",
    }
