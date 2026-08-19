"""Source layer: themed queries, rate limiting, and resilient RSS."""

from __future__ import annotations

import httpx
import pytest
from atlas_api.services.news import gdelt as gdelt_mod
from atlas_api.services.news.gdelt import THEME_CLAUSE, poll_gdelt


def test_every_country_query_carries_the_theme_clause():
    for iso3, query in gdelt_mod.COUNTRY_QUERIES.items():
        assert THEME_CLAUSE in query, f"{iso3} query is missing the theme clause"


def test_theme_clause_covers_macro_and_material_politics():
    lowered = THEME_CLAUSE.lower()
    for term in ("debt", "imf", "inflation", "bond", "central bank", "rating", "election"):
        assert term in lowered, f"theme clause missing {term}"


@pytest.mark.asyncio
async def test_poll_gdelt_spaces_requests_and_tolerates_failure(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(gdelt_mod.asyncio, "sleep", fake_sleep)

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        # Kenya fails on every attempt, so it exhausts its retries and is skipped.
        # The other nine countries must still be polled.
        if "Kenya" in request.url.params.get("query", ""):
            return httpx.Response(429, text="Please limit requests")
        return httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "url": f"https://example.com/{calls['n']}",
                        "title": "Ghana debt restructuring advances",
                        "domain": "example.com",
                        "seendate": "20260819T120000Z",
                        "language": "English",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        articles = await poll_gdelt(http, max_records=10, request_delay=5.0)

    assert len(articles) == len(gdelt_mod.COUNTRY_QUERIES) - 1
    # One 5 second gap between each country. Other values come from tenacity backoff,
    # which shares the patched asyncio.sleep.
    assert sleeps.count(5.0) == len(gdelt_mod.COUNTRY_QUERIES) - 1
