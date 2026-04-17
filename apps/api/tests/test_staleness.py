from datetime import UTC, datetime, timedelta

from atlas_api.services.country.staleness import classify_staleness
from atlas_schemas.staleness import StalenessState

NOW = datetime(2026, 4, 16, tzinfo=UTC)


def test_missing_when_ingested_at_is_none():
    info = classify_staleness(None, now=NOW)
    assert info.state is StalenessState.MISSING
    assert info.age_days is None


def test_fresh_when_under_6_months():
    info = classify_staleness(NOW - timedelta(days=30), now=NOW)
    assert info.state is StalenessState.FRESH
    assert info.age_days == 30


def test_yellow_between_6_and_12_months():
    info = classify_staleness(NOW - timedelta(days=200), now=NOW)
    assert info.state is StalenessState.YELLOW
    assert info.age_days == 200


def test_red_after_12_months():
    info = classify_staleness(NOW - timedelta(days=400), now=NOW)
    assert info.state is StalenessState.RED
    assert info.age_days == 400


def test_boundary_exact_6_months_is_yellow():
    info = classify_staleness(NOW - timedelta(days=181), now=NOW)
    assert info.state is StalenessState.YELLOW


def test_boundary_exact_12_months_is_red():
    info = classify_staleness(NOW - timedelta(days=366), now=NOW)
    assert info.state is StalenessState.RED
