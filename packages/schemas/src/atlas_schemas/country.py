from enum import StrEnum

from pydantic import BaseModel, Field


class CountryStatus(StrEnum):
    PERFORMING = "performing"
    NEGOTIATING = "negotiating"
    SELECTIVE_DEFAULT = "selective_default"
    DEFAULT = "default"
    RESTRUCTURED = "restructured"


class FxRegime(StrEnum):
    FLOAT = "float"
    MANAGED_FLOAT = "managed_float"
    PEGGED = "pegged"
    CRAWLING_PEG = "crawling_peg"
    BASKET_PEG = "basket_peg"
    CURRENCY_BOARD = "currency_board"
    NO_SEPARATE_LEGAL_TENDER = "no_separate_legal_tender"


class Country(BaseModel):
    iso3: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    name: str
    capital: str
    region: str
    tags: list[str]
    tier: str
    status: CountryStatus
    fx_regime: FxRegime
    fx_regime_notes: str | None = None
    fx_parallel_premium: float | None = None
