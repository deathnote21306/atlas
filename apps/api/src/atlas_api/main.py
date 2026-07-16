import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.config import settings
from atlas_api.ingestion.scheduler import build_scheduler
from atlas_api.logging_config import configure_logging
from atlas_api.routers import (
    auth,
    countries,
    dashboard,
    fx,
    health,
    news,
    reports,
    scenarios,
    synopses,
)

configure_logging()

logger = logging.getLogger("atlas")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = build_scheduler()
    if settings.ingestion_schedule_enabled or settings.news_poll_enabled:
        scheduler.start()

    for warning in settings.validate_for_production():
        if settings.is_production:
            raise RuntimeError(f"Production config error: {warning}")
        logger.warning("CONFIG: %s", warning)

    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Atlas API", version="0.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(countries.router)
app.include_router(dashboard.router)
app.include_router(fx.router)
app.include_router(scenarios.router)
app.include_router(news.router)
app.include_router(synopses.router)
app.include_router(reports.router)
