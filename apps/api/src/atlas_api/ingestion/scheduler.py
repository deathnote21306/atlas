"""AsyncIO scheduler for nightly ingestion."""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from atlas_api.config import settings
from atlas_api.ingestion.orchestrator import run_nightly

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
        log.info("scheduler_configured", cron=settings.ingestion_cron)
    else:
        log.info("scheduler_disabled_via_env")
    return scheduler
