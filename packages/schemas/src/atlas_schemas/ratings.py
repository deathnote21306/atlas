from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class Agency(StrEnum):
    SP = "S&P"
    MOODYS = "Moodys"
    FITCH = "Fitch"


class RatingAction(BaseModel):
    iso3: str
    agency: Agency
    rating: str
    outlook: str | None
    action: str
    action_date: date
    source_url: str | None
