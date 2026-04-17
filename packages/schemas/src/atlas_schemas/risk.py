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
    score: int
    rationale: str
    input_value: float | None
    is_estimate: bool = False


class RiskScore(BaseModel):
    composite: float
    dimensions: list[DimensionScore]
