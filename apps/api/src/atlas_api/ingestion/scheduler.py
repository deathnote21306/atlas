"""AsyncIO scheduler for nightly ingestion and news polling."""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import os

from atlas_api.config import settings
from atlas_api.ingestion.orchestrator import run_nightly
from atlas_api.services.news.daily_rescore import run_daily_rescore
from atlas_api.services.news.pipeline import run_news_pipeline

log = structlog.get_logger()


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    if settings.ingestion_schedule_enabled:
        scheduler.add_job(
            run_nightly,
            CronTrigger.from_crontab(settings.ingestion_cron, timezone="UTC"),
            id="nightly_ingestion",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        log.info("scheduler_nightly_configured", cron=settings.ingestion_cron)

    if settings.news_poll_enabled:
        scheduler.add_job(
            run_news_pipeline,
            CronTrigger.from_crontab(settings.news_poll_cron, timezone="UTC"),
            id="news_poll",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        log.info("scheduler_news_configured", cron=settings.news_poll_cron)

    # Nightly risk recomputation (3:15 UTC, after macro ingestion)
    def _run_risk_recompute() -> None:
        from atlas_api.db import SessionLocal
        from atlas_api.services.risk.compute_risk_decomposition import recompute_all
        with SessionLocal() as s:
            recompute_all(s)

    scheduler.add_job(
        _run_risk_recompute,
        CronTrigger.from_crontab("15 3 * * *", timezone="UTC"),
        id="nightly_risk_recompute",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("scheduler_risk_recompute_configured", cron="15 3 * * *")

    # Daily re-scoring cron (3:30 UTC, after nightly ingestion)
    scheduler.add_job(
        run_daily_rescore,
        CronTrigger.from_crontab("30 3 * * *", timezone="UTC"),
        id="daily_rescore",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("scheduler_rescore_configured", cron="30 3 * * *")

    # Monthly REER ingestion (15th at 04:00 UTC by default)
    reer_day = int(os.environ.get("REER_INGEST_CRON_DAY", "15"))
    reer_hour = int(os.environ.get("REER_INGEST_CRON_HOUR", "4"))

    def _run_reer() -> None:
        from atlas_api.db import SessionLocal
        from atlas_api.ingestion.reer import run_reer_ingest
        with SessionLocal() as s:
            run_reer_ingest(s)

    scheduler.add_job(
        _run_reer,
        CronTrigger(day=reer_day, hour=reer_hour, timezone="UTC"),
        id="monthly_reer",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    log.info("scheduler_reer_configured", day=reer_day, hour=reer_hour)

    if not settings.ingestion_schedule_enabled and not settings.news_poll_enabled:
        log.info("scheduler_all_disabled")

    return scheduler
