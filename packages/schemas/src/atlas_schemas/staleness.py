from enum import StrEnum

from pydantic import BaseModel


class StalenessState(StrEnum):
    MISSING = "missing"
    FRESH = "fresh"
    YELLOW = "yellow"
    RED = "red"


class StalenessInfo(BaseModel):
    state: StalenessState
    age_days: int | None
