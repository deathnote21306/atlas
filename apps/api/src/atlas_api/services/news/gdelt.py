"""GDELT DOC 2.0 API poller."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from atlas_api.services.news import RawArticle

log = structlog.get_logger()

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Sovereign macro plus material politics. Keeps junk out at the source, which is
# far cheaper than filtering it later.
THEME_CLAUSE = (
    '(debt OR IMF OR inflation OR bond OR eurobond OR fiscal OR budget OR deficit '
    'OR "central bank" OR "interest rate" OR rating OR downgrade OR upgrade '
    'OR currency OR reserves OR "exchange rate" OR economy OR "economic growth" '
    'OR election OR coup OR sanctions OR protests OR reform)'
)

# Map our 10 countries to GDELT search terms
_COUNTRY_TERMS: dict[str, str] = {
    "CIV": '("Ivory Coast" OR "Cote Ivoire")',
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

COUNTRY_QUERIES: dict[str, str] = {
    iso3: f"{term} AND {THEME_CLAUSE}" for iso3, term in _COUNTRY_TERMS.items()
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
    max_records: int = 100,
    request_delay: float = 5.0,
) -> list[RawArticle]:
    """Query GDELT DOC API for each country and return raw articles.

    english_only stays False on purpose. Non-English articles are wanted and are
    translated downstream by the grader.
    """
    articles: list[RawArticle] = []
    first_request = True

    for iso3, query in COUNTRY_QUERIES.items():
        if not first_request:
            # GDELT rejects more than one request every 5 seconds with HTTP 429.
            await asyncio.sleep(request_delay)
        first_request = False
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
                        body_snippet=title,  # GDELT returns no body, title is the only text
                        source_feed="gdelt",
                    )
                )

            log.info("gdelt_polled", iso3=iso3, articles=len(art_list))
        except Exception:
            log.exception("gdelt_poll_failed", iso3=iso3)

    return articles
