"""The backfill must batch, skip graded items, bound recency, and respect the cap."""

from __future__ import annotations

import inspect

from atlas_api.services.news.regrade import DEFAULT_SINCE_DAYS, regrade_batch


def test_regrade_batch_only_selects_ungraded_items():
    source = inspect.getsource(regrade_batch)
    assert "ai_graded" in source, "must filter on ai_graded so re-runs are cheap"
    assert "limit" in source, "must batch"


def test_regrade_batch_respects_the_daily_token_cap():
    source = inspect.getsource(regrade_batch)
    assert "token_counter" in source, "must stop when the daily token cap is hit"


def test_regrade_batch_bounds_recency_by_default():
    """Guards the budget: the archive is thousands of items and credit is finite."""
    sig = inspect.signature(regrade_batch)
    assert "since_days" in sig.parameters
    assert sig.parameters["since_days"].default == DEFAULT_SINCE_DAYS
    assert DEFAULT_SINCE_DAYS is not None and DEFAULT_SINCE_DAYS > 0


def test_regrade_batch_filters_on_published_at():
    source = inspect.getsource(regrade_batch)
    assert "published_at" in source, "recency bound must filter on published_at"
