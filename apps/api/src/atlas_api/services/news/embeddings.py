"""Embedding generation using fastembed (ONNX, ~100MB)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from atlas_api.models import NewsItem

log = structlog.get_logger()

# Lazy singleton -- model is ~80MB, load once
_model = None


def _get_model() -> Any:
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        log.info("fastembed_model_loaded", model="all-MiniLM-L6-v2", dims=384)
    return _model


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate 384-dim embeddings for a batch of texts."""
    model = _get_model()
    # fastembed returns a generator of numpy arrays
    embeddings = list(model.embed(texts))
    return [emb.tolist() for emb in embeddings]


def update_embeddings(session: Session, items: list[NewsItem]) -> int:
    """Generate embeddings for items and update the vector column via raw SQL."""
    if not items:
        return 0

    texts = [f"{item.title}. {item.body_text or ''}" for item in items]
    embeddings = generate_embeddings(texts)

    updated = 0
    for item, emb in zip(items, embeddings, strict=True):
        # pgvector expects the vector as a string like '[0.1, 0.2, ...]'
        vec_str = "[" + ",".join(str(v) for v in emb) + "]"
        session.execute(
            text("UPDATE news_item SET embedding = CAST(:vec AS vector) WHERE id = :id"),
            {"vec": vec_str, "id": str(item.id)},
        )
        updated += 1

    session.commit()
    log.info("embeddings_updated", count=updated)
    return updated
