"""The news tuning dials must exist with the agreed defaults."""

from __future__ import annotations

from atlas_api.config import Settings


def test_news_tuning_defaults():
    s = Settings()
    assert s.news_relevance_threshold == 60
    assert s.news_ai_calls_per_run == 40
    assert s.news_translate_enabled is True
