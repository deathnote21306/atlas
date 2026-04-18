"""News pipeline service modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawArticle:
    """Raw article fetched from an external source."""

    url: str
    title: str
    source: str
    published_at: datetime | None
    body_snippet: str
    source_feed: str  # "gdelt" or "rss"
