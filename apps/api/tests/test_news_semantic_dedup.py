"""Test semantic dedup via pgvector cosine similarity."""

import uuid
from datetime import UTC, datetime

from atlas_api.models import NewsItem
from atlas_api.services.news.dedup import url_hash
from atlas_api.services.news.semantic_dedup import find_near_duplicates, is_duplicate
from sqlalchemy import text


def _insert_with_embedding(session, url: str, embedding: list[float]) -> NewsItem:
    item = NewsItem(
        id=uuid.uuid4(),
        url=url,
        url_hash=url_hash(url),
        title=f"Article {url}",
        source="test",
        published_at=datetime.now(UTC),
        body_text="Test body",
        ingested_at=datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
    session.execute(
        text("UPDATE news_item SET embedding = CAST(:vec AS vector) WHERE id = :id"),
        {"vec": vec_str, "id": str(item.id)},
    )
    session.commit()
    return item


def test_finds_near_duplicate(session):
    # Two nearly identical 384-dim vectors (differ by tiny amount)
    base = [0.1] * 384
    similar = [0.1 + 0.0001 * (i % 3) for i in range(384)]

    item1 = _insert_with_embedding(session, "https://a.com/1", base)
    item2 = _insert_with_embedding(session, "https://a.com/2", similar)

    dupes = find_near_duplicates(session, item2.id, similar)
    assert item1.id in dupes


def test_no_duplicate_for_different_articles(session):
    # Two very different vectors
    vec1 = [1.0 if i < 192 else 0.0 for i in range(384)]
    vec2 = [0.0 if i < 192 else 1.0 for i in range(384)]

    item1 = _insert_with_embedding(session, "https://b.com/1", vec1)
    item2 = _insert_with_embedding(session, "https://b.com/2", vec2)

    dupes = find_near_duplicates(session, item2.id, vec2)
    assert item1.id not in dupes


def test_is_duplicate_returns_bool(session):
    base = [0.5] * 384
    item1 = _insert_with_embedding(session, "https://c.com/1", base)
    assert is_duplicate(session, item1.id, base) is False  # no other items

    similar = [0.5 + 0.00001] * 384
    item2 = _insert_with_embedding(session, "https://c.com/2", similar)
    assert is_duplicate(session, item2.id, similar) is True  # item1 is near-dupe
