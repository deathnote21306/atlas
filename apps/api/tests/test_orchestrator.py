from uuid import UUID

import pytest
from atlas_api.ingestion.base import Ingester, SourceStats
from atlas_api.ingestion.circuit_breaker import reset as reset_circuit
from atlas_api.ingestion.orchestrator import run_nightly

pytestmark = pytest.mark.asyncio


class FakeGood(Ingester):
    source_name = "fake_good"

    async def run(self, vintage_id: UUID) -> SourceStats:
        return SourceStats(source=self.source_name, rows_written=10)


class FakeFailing(Ingester):
    source_name = "fake_failing"

    async def run(self, vintage_id: UUID) -> SourceStats:
        raise RuntimeError("boom")


def _patch_session_local(engine, monkeypatch):
    # Patch SessionLocal everywhere it's bound. `orchestrator` imports it directly
    # (`from atlas_api.db import SessionLocal`), so patching only `db_mod` is not
    # enough — the orchestrator's own module-level reference must also be swapped.
    from atlas_api import db as db_mod
    from atlas_api.ingestion import orchestrator as orch_mod
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr(db_mod, "SessionLocal", factory)
    monkeypatch.setattr(orch_mod, "SessionLocal", factory)
    return factory


async def test_orchestrator_creates_vintage_and_reports(engine, monkeypatch):
    # Monkeypatch SessionLocal to use the test engine; `engine` fixture sets up tables.
    factory = _patch_session_local(engine, monkeypatch)
    # Clear any circuit state from prior runs so this test is deterministic.
    with factory() as s:
        reset_circuit(s, "fake_good")

    report = await run_nightly(factories=[FakeGood])
    assert report.ok is True
    assert report.sources[0].rows_written == 10
    assert report.sources[0].source == "fake_good"


async def test_orchestrator_records_failure(engine, monkeypatch):
    factory = _patch_session_local(engine, monkeypatch)
    # Clear any circuit state from prior runs so this test is deterministic
    # (run_nightly commits to the real DB; without reset, accumulated failures
    # across test invocations would eventually trip the breaker).
    with factory() as s:
        reset_circuit(s, "fake_failing")

    report = await run_nightly(factories=[FakeFailing])
    assert report.ok is False
    assert "boom" in "; ".join(report.sources[0].errors)
