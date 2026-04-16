"""Base Ingester + retry helper."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog
from sqlalchemy.orm import Session
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger()


@dataclass
class SourceStats:
    source: str
    rows_written: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class IngestionReport:
    vintage_id: UUID
    started_at: datetime
    finished_at: datetime
    sources: list[SourceStats]
    ok: bool


RETRY = AsyncRetrying(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPError,)),
    reraise=True,
)


class Ingester(ABC):
    source_name: str = "abstract"

    def __init__(self, http: httpx.AsyncClient, session: Session) -> None:
        self.http = http
        self.session = session

    @abstractmethod
    async def run(self, vintage_id: UUID) -> SourceStats:
        """Execute the fetch+persist pipeline for this source."""


async def with_retry[T](op: Callable[[], Awaitable[T]]) -> T:  # pragma: no cover
    # tenacity handles retries; covered via integration
    async for attempt in RETRY:
        with attempt:
            return await op()
    raise RuntimeError("unreachable")  # pragma: no cover


async def timed_run(ingester: Ingester, vintage_id: UUID) -> SourceStats:
    started = datetime.now(UTC)
    try:
        stats = await ingester.run(vintage_id)
    except Exception as exc:
        stats = SourceStats(
            source=ingester.source_name, errors=[f"{type(exc).__name__}: {exc}"]
        )
        log.exception("ingester_failed", source=ingester.source_name)
    stats.duration_seconds = (datetime.now(UTC) - started).total_seconds()
    log.info(
        "ingester_complete",
        source=ingester.source_name,
        rows_written=stats.rows_written,
        errors=len(stats.errors),
        duration_s=round(stats.duration_seconds, 3),
    )
    return stats
