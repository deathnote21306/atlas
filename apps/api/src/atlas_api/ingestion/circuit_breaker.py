"""DB-backed per-source circuit breaker. 3 consecutive failures → open."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from atlas_api.models import IngestionCircuit

FAILURE_THRESHOLD = 3


def is_open(session: Session, source: str) -> bool:
    row = session.get(IngestionCircuit, source)
    return row is not None and row.state == "open"


def record_success(session: Session, source: str) -> None:
    row = session.get(IngestionCircuit, source)
    now = datetime.now(UTC)
    if row is None:
        row = IngestionCircuit(
            source=source, consecutive_failures=0, last_success_at=now, state="closed"
        )
        session.add(row)
    else:
        row.consecutive_failures = 0
        row.last_success_at = now
        row.state = "closed"
    session.commit()


def record_failure(session: Session, source: str) -> str:
    row = session.get(IngestionCircuit, source)
    now = datetime.now(UTC)
    if row is None:
        row = IngestionCircuit(
            source=source, consecutive_failures=1, last_failure_at=now, state="closed"
        )
        session.add(row)
    else:
        row.consecutive_failures += 1
        row.last_failure_at = now
        if row.consecutive_failures >= FAILURE_THRESHOLD:
            row.state = "open"
    session.commit()
    return row.state


def reset(session: Session, source: str) -> None:
    row = session.get(IngestionCircuit, source)
    if row is not None:
        row.consecutive_failures = 0
        row.state = "closed"
        session.commit()
