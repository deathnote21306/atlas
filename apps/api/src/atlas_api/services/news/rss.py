"""RSS feed poller for news ingestion."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser  # type: ignore[import-untyped]
import httpx
import structlog

from atlas_api.services.news import RawArticle

log = structlog.get_logger()

RSS_FEEDS: list[str] = [
    "https://feeds.reuters.com/reuters/AFRICANewsrss",
    "https://blogs.imf.org/feed/",
    "https://blogs.worldbank.org/feed",
]


def _parse_pub_date(entry: dict) -> datetime | None:  # type: ignore[type-arg]
    """Extract publication date from RSS entry."""
    for field in ("published", "updated", "created"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except (ValueError, TypeError):
                pass
    # feedparser also provides a parsed tuple
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(  # noqa: DTZ001
                    parsed[0], parsed[1], parsed[2],
                    parsed[3], parsed[4], parsed[5],
                    tzinfo=UTC,
                )
            except (ValueError, TypeError):
                pass
    return None


async def poll_rss(http: httpx.AsyncClient) -> list[RawArticle]:
    """Fetch and parse all configured RSS feeds."""
    articles: list[RawArticle] = []

    for feed_url in RSS_FEEDS:
        try:
            resp = await http.get(feed_url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            feed_title = feed.feed.get("title", feed_url)

            for entry in feed.entries:
                url = entry.get("link", "").strip()
                title = entry.get("title", "").strip()
                if not url or not title:
                    continue

                # Extract body snippet from summary/description
                body = entry.get("summary", entry.get("description", ""))
                if body:
                    # Strip HTML tags naively for keyword scanning
                    body = re.sub(r"<[^>]+>", " ", body).strip()

                articles.append(
                    RawArticle(
                        url=url,
                        title=title,
                        source=str(feed_title)[:200],
                        published_at=_parse_pub_date(entry),
                        body_snippet=body[:2000] if body else "",
                        source_feed="rss",
                    )
                )

            log.info("rss_polled", feed=feed_url, articles=len(feed.entries))
        except Exception:
            log.exception("rss_poll_failed", feed=feed_url)

    return articles
