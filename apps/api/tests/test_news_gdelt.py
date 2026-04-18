"""Tests for GDELT DOC 2.0 poller."""

from __future__ import annotations

import httpx
import pytest
from atlas_api.services.news.gdelt import COUNTRY_QUERIES, GDELT_DOC_API, poll_gdelt

pytestmark = pytest.mark.asyncio


def _gdelt_response(articles: list[dict]) -> httpx.Response:  # type: ignore[type-arg]
    """Build a mock GDELT JSON response."""
    return httpx.Response(200, json={"articles": articles})


def _empty_response() -> httpx.Response:
    return httpx.Response(200, json={})


class TestPollGdelt:
    async def test_returns_raw_articles(self, httpx_mock):
        """poll_gdelt should parse GDELT articles into RawArticle objects."""
        sample_articles = [
            {
                "url": "https://example.com/article1",
                "title": "Kenya raises rates",
                "domain": "example.com",
                "seendate": "20260417T120000Z",
                "socialimage": "",
            },
            {
                "url": "https://example.com/article2",
                "title": "Ghana bond issue",
                "domain": "example.com",
                "seendate": "20260417T130000Z",
                "socialimage": "",
            },
        ]

        # Mock all 10 country queries — return articles for first, empty for rest
        for i, (_iso3, query) in enumerate(COUNTRY_QUERIES.items()):
            if i == 0:
                httpx_mock.add_response(
                    url=httpx.URL(GDELT_DOC_API, params={
                        "query": query,
                        "mode": "ArtList",
                        "format": "json",
                        "maxrecords": "50",
                    }),
                    json={"articles": sample_articles},
                )
            else:
                httpx_mock.add_response(
                    url=httpx.URL(GDELT_DOC_API, params={
                        "query": query,
                        "mode": "ArtList",
                        "format": "json",
                        "maxrecords": "50",
                    }),
                    json={"articles": []},
                )

        async with httpx.AsyncClient() as client:
            result = await poll_gdelt(client)

        assert len(result) == 2
        assert result[0].url == "https://example.com/article1"
        assert result[0].title == "Kenya raises rates"
        assert result[0].source == "example.com"
        assert result[0].source_feed == "gdelt"
        assert result[0].published_at is not None

    async def test_skips_articles_without_url_or_title(self, httpx_mock):
        """Articles missing url or title should be skipped."""
        articles = [
            {"url": "", "title": "Has title", "domain": "x.com"},
            {"url": "https://x.com/a", "title": "", "domain": "x.com"},
            {"url": "https://x.com/b", "title": "Valid", "domain": "x.com"},
        ]

        for iso3, query in COUNTRY_QUERIES.items():
            httpx_mock.add_response(
                url=httpx.URL(GDELT_DOC_API, params={
                    "query": query,
                    "mode": "ArtList",
                    "format": "json",
                    "maxrecords": "50",
                }),
                json={"articles": articles} if iso3 == "CIV" else {"articles": []},
            )

        async with httpx.AsyncClient() as client:
            result = await poll_gdelt(client)

        assert len(result) == 1
        assert result[0].title == "Valid"

    async def test_handles_empty_response(self, httpx_mock):
        """Empty GDELT response (no 'articles' key) should return empty list."""
        for _iso3, query in COUNTRY_QUERIES.items():
            httpx_mock.add_response(
                url=httpx.URL(GDELT_DOC_API, params={
                    "query": query,
                    "mode": "ArtList",
                    "format": "json",
                    "maxrecords": "50",
                }),
                json={},
            )

        async with httpx.AsyncClient() as client:
            result = await poll_gdelt(client)

        assert result == []

    async def test_handles_http_error_gracefully(self, httpx_mock):
        """HTTP errors should be logged and skipped, not crash."""
        for _iso3, query in COUNTRY_QUERIES.items():
            # tenacity retries 3 times, so we need 3 responses per country
            for _ in range(3):
                httpx_mock.add_response(
                    url=httpx.URL(GDELT_DOC_API, params={
                        "query": query,
                        "mode": "ArtList",
                        "format": "json",
                        "maxrecords": "50",
                    }),
                    status_code=500,
                )

        async with httpx.AsyncClient() as client:
            result = await poll_gdelt(client)

        # Should return empty list, not raise
        assert result == []

    async def test_parses_seendate(self, httpx_mock):
        """GDELT seendate format should be parsed correctly."""
        articles = [
            {
                "url": "https://example.com/dated",
                "title": "Dated article",
                "domain": "example.com",
                "seendate": "20260417T120000Z",
            }
        ]

        for iso3, query in COUNTRY_QUERIES.items():
            httpx_mock.add_response(
                url=httpx.URL(GDELT_DOC_API, params={
                    "query": query,
                    "mode": "ArtList",
                    "format": "json",
                    "maxrecords": "50",
                }),
                json={"articles": articles} if iso3 == "CIV" else {"articles": []},
            )

        async with httpx.AsyncClient() as client:
            result = await poll_gdelt(client)

        assert len(result) == 1
        assert result[0].published_at is not None
        assert result[0].published_at.year == 2026
        assert result[0].published_at.month == 4
        assert result[0].published_at.day == 17


class TestCountryQueries:
    def test_ten_countries_configured(self):
        assert len(COUNTRY_QUERIES) == 10

    def test_all_expected_iso3_codes(self):
        expected = {"CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY"}
        assert set(COUNTRY_QUERIES.keys()) == expected
