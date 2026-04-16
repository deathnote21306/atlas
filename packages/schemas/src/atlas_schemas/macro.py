from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class MacroIndicator(StrEnum):
    GDP_USD = "GDP_USD"
    GDP_GROWTH_PCT = "GDP_GROWTH_PCT"
    INFLATION_PCT = "INFLATION_PCT"
    CURRENT_ACCOUNT_PCT_GDP = "CURRENT_ACCOUNT_PCT_GDP"
    FISCAL_BALANCE_PCT_GDP = "FISCAL_BALANCE_PCT_GDP"
    PUBLIC_DEBT_PCT_GDP = "PUBLIC_DEBT_PCT_GDP"
    EXTERNAL_DEBT_PCT_GNI = "EXTERNAL_DEBT_PCT_GNI"
    FX_RESERVES_MO_IMPORTS = "FX_RESERVES_MO_IMPORTS"
    DEBT_SERVICE_PCT_EXPORTS = "DEBT_SERVICE_PCT_EXPORTS"
    UNEMPLOYMENT_PCT = "UNEMPLOYMENT_PCT"
    FDI_INFLOW_USD = "FDI_INFLOW_USD"
    GDP_PER_CAPITA_USD = "GDP_PER_CAPITA_USD"


class MacroValue(BaseModel):
    iso3: str
    indicator: MacroIndicator
    period: str
    value: float | None
    source: str
    source_date: date | None
    ingested_at: datetime
    vintage_id: UUID
