"""Model-level checks for the news relevance columns and country links."""

from __future__ import annotations

from atlas_api.models import NewsItem, NewsItemCountry


def test_news_item_has_relevance_columns():
    cols = NewsItem.__table__.columns
    for name in (
        "relevant",
        "relevance_score",
        "relevance_rationale",
        "source_lang",
        "original_title",
        "summary_en",
        "ai_graded",
        "prompt_trace_id",
    ):
        assert name in cols, f"NewsItem missing column {name}"


def test_relevant_defaults_to_false():
    assert NewsItem.__table__.columns["relevant"].default.arg is False


def test_news_item_country_shape():
    cols = NewsItemCountry.__table__.columns
    assert "news_item_id" in cols
    assert "iso3" in cols
    assert "role" in cols
    pk = {c.name for c in NewsItemCountry.__table__.primary_key.columns}
    assert pk == {"news_item_id", "iso3"}
