"""News pipeline schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class EventType(StrEnum):
    MONETARY = "Monetary"
    FISCAL = "Fiscal"
    POLITICAL = "Political"
    EXTERNAL = "External"
    RATING = "Rating"
    IMF = "IMF"
    MARKET = "Market"


class ImpactLevel(StrEnum):
    LOW = "L"
    MEDIUM = "M"
    HIGH = "H"


class NewsImpactScoreOut(BaseModel):
    """Impact score for a news item across 4 axes."""

    id: uuid.UUID
    news_item_id: uuid.UUID
    fiscal_impact: ImpactLevel
    external_impact: ImpactLevel
    fx_impact: ImpactLevel
    political_impact: ImpactLevel
    rationale: dict[str, object] | None = None
    scorer: str
    scored_at: datetime


class NewsItemOut(BaseModel):
    """A scored news item returned by the API."""

    id: uuid.UUID
    url: str
    title: str
    source: str
    published_at: datetime | None = None
    primary_iso3: str | None = None
    event_type: str | None = None
    ingested_at: datetime
    impact_score: NewsImpactScoreOut | None = None
