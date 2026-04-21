"""GDELT DOC 2.0 API poller."""

from __future__ import annotations

import contextlib
from datetime import datetime

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from atlas_api.services.news import RawArticle

log = structlog.get_logger()

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Map our 10 countries to GDELT search terms
COUNTRY_QUERIES: dict[str, str] = {
    "CIV": '"Ivory Coast" OR "Cote Ivoire"',
    "GHA": "Ghana",
    "KEN": "Kenya",
    "NGA": "Nigeria",
    "SEN": "Senegal",
    "ETH": "Ethiopia",
    "RWA": "Rwanda",
    "ZAF": '"South Africa"',
    "MAR": "Morocco",
    "EGY": "Egypt",
}

RETRY = AsyncRetrying(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)


async def poll_gdelt(
    http: httpx.AsyncClient,
    *,
    english_only: bool = False,
    timespan: str = "",
    max_records: int = 50,
) -> list[RawArticle]:
    """Query GDELT DOC API for each country and return raw articles."""
    articles: list[RawArticle] = []

    for iso3, query in COUNTRY_QUERIES.items():
        try:
            full_query = f"{query} sourcelang:english" if english_only else query
            params: dict[str, str] = {
                "query": full_query,
                "mode": "ArtList",
                "format": "json",
                "maxrecords": str(max_records),
            }
            if timespan:
                params["timespan"] = timespan

            resp: httpx.Response | None = None
            async for attempt in RETRY:
                with attempt:
                    resp = await http.get(
                        GDELT_DOC_API,
                        params=params,
                        timeout=30.0,
                    )
                    resp.raise_for_status()

            if resp is None:
                continue

            data = resp.json()
            art_list = data.get("articles", [])
            for art in art_list:
                url = art.get("url", "").strip()
                title = art.get("title", "").strip()
                source_name = art.get("domain", art.get("source", "unknown"))
                date_str = art.get("seendate", "")

                if not url or not title:
                    continue

                pub_at = None
                if date_str:
                    with contextlib.suppress(ValueError):
                        # GDELT dates: "20260417T120000Z"
                        pub_at = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ")

                articles.append(
                    RawArticle(
                        url=url,
                        title=title,
                        source=str(source_name)[:200],
                        published_at=pub_at,
                        body_snippet=art.get("socialimage", ""),  # GDELT doesn't return body
                        source_feed="gdelt",
                    )
                )

            log.info("gdelt_polled", iso3=iso3, articles=len(art_list))
        except Exception:
            log.exception("gdelt_poll_failed", iso3=iso3)

    return articles
