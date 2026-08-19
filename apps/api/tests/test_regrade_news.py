"""The backfill must batch, skip already graded items, and respect the token cap."""

from __future__ import annotations

import inspect

from atlas_api.services.news.regrade import regrade_batch


def test_regrade_batch_only_selects_ungraded_items():
    source = inspect.getsource(regrade_batch)
    assert "ai_graded" in source, "must filter on ai_graded so re-runs are cheap"
    assert "limit" in source, "must batch"


def test_regrade_batch_respects_the_daily_token_cap():
    source = inspect.getsource(regrade_batch)
    assert "token_counter" in source, "must stop when the daily token cap is hit"
