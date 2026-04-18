"""Tests for embedding generation."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from atlas_api.models import NewsItem
from atlas_api.services.news.dedup import url_hash
from atlas_api.services.news.embeddings import generate_embeddings, update_embeddings


class TestGenerateEmbeddings:
    def test_generates_384_dim_embedding(self):
        """Embedding should be a 384-dim list of floats."""
        texts = ["Kenya raises interest rates by 50 basis points"]
        result = generate_embeddings(texts)

        assert len(result) == 1
        assert len(result[0]) == 384
        assert all(isinstance(v, float) for v in result[0])

    def test_batch_embeddings(self):
        """Multiple texts should produce multiple embeddings."""
        texts = [
            "Kenya raises rates",
            "Ghana fiscal deficit widens",
            "Nigeria bond issuance",
        ]
        result = generate_embeddings(texts)

        assert len(result) == 3
        for emb in result:
            assert len(emb) == 384


class TestUpdateEmbeddings:
    def test_updates_embedding_column(self, session):
        """update_embeddings should write vector to the embedding column."""
        # Insert a test article
        item_id = uuid.uuid4()
        item = NewsItem(
            id=item_id,
            url="https://example.com/embed-test",
            url_hash=url_hash("https://example.com/embed-test"),
            title="Kenya raises interest rates",
            source="Reuters",
            body_text="Central bank raised benchmark rate by 50bps.",
        )
        session.add(item)
        session.commit()

        # Mock generate_embeddings to avoid slow model download in CI
        fake_emb = [0.1] * 384
        with patch(
            "atlas_api.services.news.embeddings.generate_embeddings",
            return_value=[fake_emb],
        ):
            count = update_embeddings(session, [item])

        assert count == 1

        # Verify the embedding was stored by reading it back via raw SQL
        from sqlalchemy import text

        row = session.execute(
            text("SELECT embedding FROM news_item WHERE id = :id"),
            {"id": str(item_id)},
        ).fetchone()
        assert row is not None
        assert row[0] is not None

    def test_empty_items_returns_zero(self, session):
        """Empty item list should return 0."""
        count = update_embeddings(session, [])
        assert count == 0
