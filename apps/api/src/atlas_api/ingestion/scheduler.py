"""AsyncIO scheduler for nightly ingestion and news polling."""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from atlas_api.config import settings
from atlas_api.ingestion.orchestrator import run_nightly
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

    if not settings.ingestion_schedule_enabled and not settings.news_poll_enabled:
        log.info("scheduler_all_disabled")

    return scheduler
