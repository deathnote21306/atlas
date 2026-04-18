"""Tests for URL dedup + article storage."""

from __future__ import annotations

from datetime import UTC, datetime

from atlas_api.models import NewsItem
from atlas_api.services.news import RawArticle
from atlas_api.services.news.dedup import store_new_articles, url_hash


def _make_article(url: str, title: str = "Test article") -> RawArticle:
    return RawArticle(
        url=url,
        title=title,
        source="test-source",
        published_at=datetime.now(UTC),
        body_snippet="Test body",
        source_feed="test",
    )


class TestUrlHash:
    def test_same_url_same_hash(self):
        h1 = url_hash("https://example.com/article")
        h2 = url_hash("https://example.com/article")
        assert h1 == h2

    def test_normalized_url(self):
        h1 = url_hash("https://example.com/article")
        h2 = url_hash("HTTPS://EXAMPLE.COM/ARTICLE/")
        assert h1 == h2

    def test_different_urls_different_hashes(self):
        h1 = url_hash("https://example.com/article1")
        h2 = url_hash("https://example.com/article2")
        assert h1 != h2

    def test_hash_is_64_chars(self):
        h = url_hash("https://example.com")
        assert len(h) == 64


class TestStoreNewArticles:
    def test_inserts_new_articles(self, session):
        """New articles should be inserted into the database."""
        articles = [
            _make_article(f"https://example.com/article-{i}")
            for i in range(5)
        ]

        result = store_new_articles(session, articles)

        assert len(result) == 5
        # Verify they're in the database
        count = session.query(NewsItem).count()
        assert count == 5

    def test_skips_duplicates(self, session):
        """Re-inserting the same articles should skip them."""
        articles = [
            _make_article(f"https://example.com/article-{i}")
            for i in range(5)
        ]

        # First insert
        first_result = store_new_articles(session, articles)
        assert len(first_result) == 5

        # Second insert of same articles
        second_result = store_new_articles(session, articles)
        assert len(second_result) == 0

        # Total count should still be 5
        count = session.query(NewsItem).count()
        assert count == 5

    def test_intra_batch_dedup(self, session):
        """Duplicate URLs within the same batch should be deduped."""
        articles = [
            _make_article("https://example.com/same-url", "First"),
            _make_article("https://example.com/same-url", "Second"),
        ]

        result = store_new_articles(session, articles)

        assert len(result) == 1
        assert result[0].title == "First"

    def test_stores_metadata(self, session):
        """Stored articles should have correct metadata."""
        articles = [
            RawArticle(
                url="https://example.com/metadata-test",
                title="Test Title",
                source="Reuters",
                published_at=datetime(2026, 4, 17, tzinfo=UTC),
                body_snippet="Article body text",
                source_feed="gdelt",
            )
        ]

        result = store_new_articles(session, articles)

        assert len(result) == 1
        item = result[0]
        assert item.url == "https://example.com/metadata-test"
        assert item.title == "Test Title"
        assert item.source == "Reuters"
        assert item.body_text == "Article body text"
        assert item.raw_payload == {"source_feed": "gdelt"}
        assert item.url_hash == url_hash("https://example.com/metadata-test")

    def test_mixed_new_and_existing(self, session):
        """Mix of new and existing articles should only insert new ones."""
        # Insert first batch
        batch1 = [_make_article(f"https://example.com/a-{i}") for i in range(3)]
        store_new_articles(session, batch1)

        # Insert second batch with some overlap
        batch2 = [
            _make_article("https://example.com/a-0"),  # existing
            _make_article("https://example.com/a-1"),  # existing
            _make_article("https://example.com/new-1"),  # new
            _make_article("https://example.com/new-2"),  # new
        ]
        result = store_new_articles(session, batch2)

        assert len(result) == 2
        total = session.query(NewsItem).count()
        assert total == 5
