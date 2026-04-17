"""Deterministic 6-dimension sovereign risk score.

Takes raw macro indicator values + country status + FX delta; returns a
composite score on a 0-100 scale plus per-dimension breakdowns. Hand-tuned
thresholds locked via golden tests.
"""

from atlas_schemas.risk import DimensionScore, RiskDimension, RiskScore

Bracket = tuple[float, int]

_DEBT_BRACKETS: list[Bracket] = [(30, 1), (50, 3), (70, 5), (90, 7), (float("inf"), 9)]
_FISCAL_BRACKETS: list[Bracket] = [(-5, 9), (-2, 7), (0, 5), (2, 3), (float("inf"), 1)]
_GROWTH_BRACKETS: list[Bracket] = [(-1, 9), (1, 7), (3, 5), (5, 3), (float("inf"), 1)]
_INFLATION_BRACKETS: list[Bracket] = [(5, 1), (10, 3), (20, 5), (40, 7), (float("inf"), 9)]
_LIQUIDITY_BRACKETS_LOWER_IS_WORSE: list[Bracket] = [
    (2, 9), (3, 7), (4, 5), (6, 3), (float("inf"), 1),
]
_FX_BRACKETS: list[Bracket] = [(2, 1), (5, 3), (10, 5), (20, 7), (float("inf"), 9)]

_DISTRESSED = {"selective_default", "default", "restructured"}


def bucket_score(value: float, brackets: list[Bracket]) -> int:
    """Map a continuous value to a discrete score via bracket lookup."""
    for upper, score in brackets:
        if value < upper:
            return score
    return brackets[-1][1]


def compute_risk_score(
    status: str,
    indicators: dict[str, float],
    fx_delta_30d_pct: float | None,
) -> RiskScore:
    """Pure function: macro indicators -> composite 0-100 risk score."""
    dimensions: list[DimensionScore] = []

    # 1. Debt Burden
    debt = indicators.get("PUBLIC_DEBT_PCT_GDP")
    if status in _DISTRESSED:
        dimensions.append(DimensionScore(
            dimension=RiskDimension.DEBT_BURDEN, score=10,
            rationale=f"country status {status!r} \u2192 auto max",
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

    # 2. External Liquidity
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

    # 3. Fiscal Flexibility
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

    # 4. Growth Momentum
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

    # 6. FX Stability
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
