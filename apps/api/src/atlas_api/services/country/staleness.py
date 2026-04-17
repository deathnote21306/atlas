"""Staleness classifier per spec §8. Thresholds: fresh <=180d, yellow 181-365d, red >365d."""

from datetime import UTC, datetime

from atlas_schemas.staleness import StalenessInfo, StalenessState

FRESH_MAX_DAYS = 180
YELLOW_MAX_DAYS = 365


def classify_staleness(ingested_at: datetime | None, now: datetime | None = None) -> StalenessInfo:
    if ingested_at is None:
        return StalenessInfo(state=StalenessState.MISSING, age_days=None)
    ref = now or datetime.now(UTC)
    age = (ref - ingested_at).days
    if age <= FRESH_MAX_DAYS:
        state = StalenessState.FRESH
    elif age <= YELLOW_MAX_DAYS:
        state = StalenessState.YELLOW
    else:
        state = StalenessState.RED
    return StalenessInfo(state=state, age_days=age)
