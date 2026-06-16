"""Nightly orchestrator: creates one vintage, runs all four ingesters, records circuit state."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import httpx
import structlog
from atlas_schemas.ingestion import IngestionReport as IngestionReportSchema
from atlas_schemas.ingestion import SourceStats as SourceStatsSchema

from atlas_api.db import SessionLocal
from atlas_api.ingestion.base import Ingester, timed_run
from atlas_api.ingestion.circuit_breaker import is_open, record_failure, record_success
from atlas_api.ingestion.fx import ExchangeRateHostIngester
from atlas_api.ingestion.imf import ImfWeoIngester
from atlas_api.ingestion.ratings import RatingsJsonLoader
from atlas_api.ingestion.worldbank import WorldBankIngester
from atlas_api.models import DataVintage
from atlas_api.services.ai.debt_commentary import run_debt_commentary_for_all

log = structlog.get_logger()


def _default_ingester_factories() -> list[type[Ingester]]:
    return [WorldBankIngester, ImfWeoIngester, ExchangeRateHostIngester, RatingsJsonLoader]


async def run_nightly(factories: Sequence[type[Ingester]] | None = None) -> IngestionReportSchema:
    factories = list(factories) if factories is not None else _default_ingester_factories()
    started_at = datetime.now(UTC)
    session = SessionLocal()
    try:
        vintage = DataVintage(id=uuid.uuid4(), source="nightly", created_at=started_at)
        session.add(vintage)
        session.commit()
        log.info("vintage_created", vintage_id=str(vintage.id))

        sources: list[SourceStatsSchema] = []
        async with httpx.AsyncClient() as http:
            for factory in factories:
                ingester = factory(http, session)
                if is_open(session, ingester.source_name):
                    log.warning("circuit_open_skipping", source=ingester.source_name)
                    sources.append(
                        SourceStatsSchema(
                            source=ingester.source_name,
                            rows_written=0,
                            rows_skipped=0,
                            errors=["circuit breaker open"],
                            duration_seconds=0.0,
                        )
                    )
                    continue
                stats = await timed_run(ingester, vintage.id)
                sources.append(
                    SourceStatsSchema(
                        source=stats.source,
                        rows_written=stats.rows_written,
                        rows_skipped=stats.rows_skipped,
                        errors=stats.errors,
                        duration_seconds=stats.duration_seconds,
                    )
                )
                if stats.errors and stats.rows_written == 0:
                    record_failure(session, ingester.source_name)
                else:
                    record_success(session, ingester.source_name)

        # Generate debt commentary for all seeded countries. A failure here must
        # never prevent the rest of the nightly report from being built/returned.
        try:
            with SessionLocal() as commentary_session:
                run_debt_commentary_for_all(commentary_session)
        except Exception:
            log.exception("debt_commentary_batch_failed")

        finished_at = datetime.now(UTC)
        ok = all(s.rows_written > 0 or s.source == "ratings_json" for s in sources)
        report = IngestionReportSchema(
            vintage_id=vintage.id,
            started_at=started_at,
            finished_at=finished_at,
            sources=sources,
            ok=ok,
        )
        log.info(
            "nightly_complete",
            vintage_id=str(vintage.id),
            duration_s=(finished_at - started_at).total_seconds(),
            sources=[
                {"source": s.source, "rows": s.rows_written, "errors": len(s.errors)}
                for s in sources
            ],
            ok=ok,
        )
        return report
    finally:
        session.close()
