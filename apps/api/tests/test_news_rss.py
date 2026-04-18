"""Tests for RSS feed poller."""

from __future__ import annotations

import httpx
import pytest
from atlas_api.services.news.rss import RSS_FEEDS, poll_rss

pytestmark = pytest.mark.asyncio

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Kenya central bank holds rate</title>
      <link>https://example.com/kenya-rate</link>
      <description>&lt;p&gt;The central bank of Kenya held rates steady.&lt;/p&gt;</description>
      <pubDate>Thu, 17 Apr 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Ghana fiscal outlook</title>
      <link>https://example.com/ghana-fiscal</link>
      <description>Ghana's fiscal balance improved in Q1.</description>
      <pubDate>Wed, 16 Apr 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

EMPTY_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
  </channel>
</rss>"""


class TestPollRss:
    async def test_returns_raw_articles(self, httpx_mock):
        """poll_rss should parse RSS entries into RawArticle objects."""
        for feed_url in RSS_FEEDS:
            httpx_mock.add_response(url=feed_url, text=SAMPLE_RSS)

        async with httpx.AsyncClient() as client:
            result = await poll_rss(client)

        # 2 articles per feed x 3 feeds = 6
        assert len(result) == 6
        assert result[0].title == "Kenya central bank holds rate"
        assert result[0].url == "https://example.com/kenya-rate"
        assert result[0].source == "Test Feed"
        assert result[0].source_feed == "rss"

    async def test_strips_html_from_body(self, httpx_mock):
        """HTML tags in description should be stripped."""
        for feed_url in RSS_FEEDS:
            httpx_mock.add_response(url=feed_url, text=SAMPLE_RSS)

        async with httpx.AsyncClient() as client:
            result = await poll_rss(client)

        # First article has HTML in description
        first = result[0]
        assert "<p>" not in first.body_snippet
        assert "central bank of Kenya" in first.body_snippet

    async def test_parses_pub_date(self, httpx_mock):
        """Publication date should be parsed from RSS pubDate."""
        for feed_url in RSS_FEEDS:
            httpx_mock.add_response(url=feed_url, text=SAMPLE_RSS)

        async with httpx.AsyncClient() as client:
            result = await poll_rss(client)

        assert result[0].published_at is not None
        assert result[0].published_at.year == 2026

    async def test_handles_empty_feed(self, httpx_mock):
        """Empty RSS feed should return no articles."""
        for feed_url in RSS_FEEDS:
            httpx_mock.add_response(url=feed_url, text=EMPTY_RSS)

        async with httpx.AsyncClient() as client:
            result = await poll_rss(client)

        assert result == []

    async def test_handles_http_error_gracefully(self, httpx_mock):
        """HTTP errors should be logged and skipped."""
        for feed_url in RSS_FEEDS:
            httpx_mock.add_response(url=feed_url, status_code=500)

        async with httpx.AsyncClient() as client:
            result = await poll_rss(client)

        assert result == []


class TestRssFeeds:
    def test_three_feeds_configured(self):
        assert len(RSS_FEEDS) == 3

    def test_feed_urls(self):
        assert "reuters" in RSS_FEEDS[0].lower()
        assert "imf" in RSS_FEEDS[1].lower()
        assert "worldbank" in RSS_FEEDS[2].lower()
