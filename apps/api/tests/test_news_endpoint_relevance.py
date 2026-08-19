"""The endpoint must hide irrelevant items and expose the new fields."""

from __future__ import annotations

import inspect

from atlas_api.routers import news as news_router


def test_query_filters_on_relevant():
    source = inspect.getsource(news_router.list_news)
    assert "relevant" in source, "list_news must filter out irrelevant items"


def test_query_uses_the_country_link_table():
    source = inspect.getsource(news_router.list_news)
    assert "NewsItemCountry" in source, "iso3 filter must use the link table"


def test_ordering_prefers_relevance_then_recency():
    source = inspect.getsource(news_router.list_news)
    assert "relevance_score" in source
    assert "published_at" in source


def test_item_serializer_exposes_new_fields():
    source = inspect.getsource(news_router._item_to_out)
    for field in (
        "summary_en",
        "source_lang",
        "relevance_score",
        "relevance_rationale",
        "translated",
    ):
        assert field in source, f"_item_to_out must expose {field}"
