"""Unit tests for the APScheduler integration."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from atlas_api import config as config_module
from atlas_api.ingestion.scheduler import build_scheduler


def test_build_scheduler_returns_asyncio_scheduler(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ingestion_schedule_enabled", True)
    scheduler = build_scheduler()
    assert isinstance(scheduler, AsyncIOScheduler)


def test_build_scheduler_enabled_registers_nightly_job(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ingestion_schedule_enabled", True)
    monkeypatch.setattr(config_module.settings, "ingestion_cron", "0 3 * * *")
    scheduler = build_scheduler()
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "nightly_ingestion"


def test_build_scheduler_disabled_registers_no_jobs(monkeypatch):
    monkeypatch.setattr(config_module.settings, "ingestion_schedule_enabled", False)
    scheduler = build_scheduler()
    assert scheduler.get_jobs() == []
