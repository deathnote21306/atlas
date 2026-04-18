# Atlas News Ingestion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every 10 minutes, Atlas polls GDELT and configured RSS feeds for news articles relevant to our 10 African sovereigns, deduplicates by URL hash and semantic similarity, extracts country entities, classifies event types, and produces heuristic impact scores (L/M/H across 4 axes). The scored news appears on each country's profile page, replacing the "No scored news yet" placeholder. AI scoring via Claude is deferred to Plan 5b.

**Architecture:** A new `news` service module contains the full pipeline: GDELT + RSS pollers fetch raw articles, URL-hash dedup prevents re-processing, `fastembed` generates 384-dim embeddings stored in a pgvector column with an HNSW index, semantic dedup collapses near-duplicates (cosine >0.92), spaCy NER maps articles to countries, a keyword gate filters for sovereign-finance relevance, rule-based classification assigns event types, and a heuristic scorer produces 4-axis L/M/H impact ratings. A second APScheduler job (`news_poll`) runs every 10 minutes alongside the existing nightly ingestion. Two new REST endpoints serve scored news to the frontend.

**Tech Stack:** FastAPI endpoints (existing stack); SQLAlchemy + Alembic migration `0008`; pgvector HNSW index; `fastembed` for embeddings (ONNX, ~100MB vs ~2GB for sentence-transformers); spaCy `en_core_web_sm` for NER; `feedparser` for RSS; Pydantic schemas in `packages/schemas`; pytest with mocked HTTP for integration tests.

---

## File Structure

Files created (C) or modified (M):

```
atlas/
├── packages/schemas/
│   ├── src/atlas_schemas/
│   │   ├── __init__.py                                            (M) export new news types
│   │   └── news.py                                                (C) EventType, ImpactLevel, NewsItemOut, NewsImpactScoreOut
│   └── tests/
│       └── test_contracts.py                                      (M) add news schema roundtrip tests
│
├── infra/migrations/versions/
│   └── 0008_news_pipeline.py                                      (C) news_item + news_impact_score tables
│
├── apps/api/
│   ├── pyproject.toml                                             (M) add fastembed, spacy, feedparser, pgvector
│   ├── scripts/
│   │   └── download_models.sh                                     (C) spaCy model download script
│   ├── src/atlas_api/
│   │   ├── models.py                                              (M) add NewsItem + NewsImpactScore models
│   │   ├── config.py                                              (M) add NEWS_POLL_ENABLED, NEWS_POLL_CRON
│   │   ├── main.py                                                (M) wire news router
│   │   ├── ingestion/
│   │   │   └── scheduler.py                                       (M) add news_poll job
│   │   ├── routers/
│   │   │   └── news.py                                            (C) GET /api/news, GET /api/news/{id}
│   │   └── services/
│   │       └── news/
│   │           ├── __init__.py                                    (C)
│   │           ├── gdelt.py                                       (C) GDELT DOC 2.0 poller
│   │           ├── rss.py                                         (C) RSS feed poller
│   │           ├── dedup.py                                       (C) URL hash dedup + article storage
│   │           ├── embeddings.py                                  (C) fastembed wrapper
│   │           ├── semantic_dedup.py                               (C) pgvector cosine dedup
│   │           ├── entity_extraction.py                            (C) spaCy NER + country mapping + relevance gate + event classification
│   │           ├── scorer.py                                      (C) heuristic 4-axis impact scorer
│   │           └── pipeline.py                                    (C) orchestrator chaining steps 4-10
│   └── tests/
│       ├── test_news_pipeline.py                                  (C) integration test with mocked GDELT/RSS
│       ├── test_scorer.py                                         (C) golden tests for heuristic scorer
│       └── test_entity_extraction.py                              (C) NER + classification tests
│
└── apps/web/
    └── src/
        └── routes/CountryProfile.tsx                              (M) wire news feed section
```

---

## Design decisions locked in this plan

1. **`fastembed` over `sentence-transformers`.** `fastembed` uses ONNX Runtime (~100MB) instead of PyTorch (~2GB). Same `all-MiniLM-L6-v2` model, same 384-dim output. Much faster CI. We use `fastembed.TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")`.
2. **English-only NER for now.** spaCy `en_core_web_sm` only. CIV and SEN are francophone but their news in English sources will still mention country names. French model deferred to a polish pass.
3. **GDELT DOC 2.0 API.** One query per country: `https://api.gdeltproject.org/api/v2/doc/doc?query=COUNTRYNAME&mode=ArtList&format=json&maxrecords=50`. Returns JSON with article URL, title, source, date.
4. **RSS feeds are hardcoded.** `["https://feeds.reuters.com/reuters/AFRICANewsrss", "https://blogs.imf.org/feed/", "https://blogs.worldbank.org/feed"]`. Easy to extend later.
5. **URL hash dedup uses SHA-256** of the normalized URL. Checked against `news_item.url` UNIQUE constraint (last 30 days window for the query, but the UNIQUE on URL is permanent).
6. **Semantic dedup threshold = 0.92 cosine similarity** against items from the last 7 days. The "loser" item is not deleted but gets `primary_iso3 = NULL` to exclude it from feeds (soft dedup).
7. **Heuristic impact scorer** scans title + body for keyword sets per axis, sums weights, thresholds to L/M/H. `scorer = "heuristic"`.
8. **Event types** are a `StrEnum`: Monetary, Fiscal, Political, External, Rating, IMF, Market. Assigned via keyword matching. Default is `Market` if no other match.
9. **Scheduler** adds a second job: `news_poll` at `*/10 * * * *`. Env-disableable via `NEWS_POLL_ENABLED=false`.
10. **pgvector HNSW index** on `news_item.embedding` using `vector_cosine_ops`. The pgvector extension was already created in migration 0001.

---

## Task 1 of 12 -- News dependencies

**Goal:** Add `fastembed`, `spacy`, `feedparser`, and `pgvector` to the API's `pyproject.toml`. Create a model download script for spaCy.

### Steps

- [ ] Modify `apps/api/pyproject.toml` to add dependencies
- [ ] Create `apps/api/scripts/download_models.sh`
- [ ] Verify: `cd apps/api && uv pip install -e ".[dev]" && python -m spacy download en_core_web_sm`

### Code

**`apps/api/pyproject.toml`** (MODIFY -- add to `dependencies` list)

```toml
[project]
name = "atlas-api"
version = "0.0.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "alembic>=1.13",
  "argon2-cffi>=23.1",
  "python-jose[cryptography]>=3.3",
  "atlas-schemas",
  "httpx>=0.27",
  "apscheduler>=3.10",
  "tenacity>=9.0",
  "structlog>=24.4",
  "fastembed>=0.4",
  "spacy>=3.7",
  "feedparser>=6.0",
  "pgvector>=0.3",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "testcontainers[postgres]>=4.8",
  "ruff>=0.6",
  "mypy>=1.11",
  "types-python-jose>=3.3",
  "pytest-httpx>=0.32",
  "freezegun>=1.5",
]

[tool.uv.sources]
atlas-schemas = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/atlas_api"]
```

**`apps/api/scripts/download_models.sh`** (CREATE)

```bash
#!/usr/bin/env bash
set -euo pipefail
# Download spaCy English model for NER.
# Run once after install: bash apps/api/scripts/download_models.sh
python -m spacy download en_core_web_sm
echo "spaCy en_core_web_sm downloaded successfully."
```

### Verification

```bash
cd apps/api
uv pip install -e ".[dev]"
python -c "from fastembed import TextEmbedding; print('fastembed OK')"
python -c "import feedparser; print('feedparser OK')"
python -c "from pgvector.sqlalchemy import Vector; print('pgvector OK')"
bash scripts/download_models.sh
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('spaCy OK')"
```

---

## Task 2 of 12 -- News schemas

**Goal:** Define `EventType`, `ImpactLevel`, `NewsItemOut`, `NewsImpactScoreOut` Pydantic models and enums. Add contract tests. Update `__init__.py`.

### Steps

- [ ] Create `packages/schemas/src/atlas_schemas/news.py`
- [ ] Update `packages/schemas/src/atlas_schemas/__init__.py`
- [ ] Add contract tests in `packages/schemas/tests/test_contracts.py`

### Code

**`packages/schemas/src/atlas_schemas/news.py`** (CREATE)

```python
"""News pipeline schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EventType(StrEnum):
    MONETARY = "Monetary"
    FISCAL = "Fiscal"
    POLITICAL = "Political"
    EXTERNAL = "External"
    RATING = "Rating"
    IMF = "IMF"
    MARKET = "Market"


class ImpactLevel(StrEnum):
    LOW = "L"
    MEDIUM = "M"
    HIGH = "H"


class NewsImpactScoreOut(BaseModel):
    """Impact score for a news item across 4 axes."""

    id: uuid.UUID
    news_item_id: uuid.UUID
    fiscal_impact: ImpactLevel
    external_impact: ImpactLevel
    fx_impact: ImpactLevel
    political_impact: ImpactLevel
    rationale: dict | None = None
    scorer: str
    scored_at: datetime


class NewsItemOut(BaseModel):
    """A scored news item returned by the API."""

    id: uuid.UUID
    url: str
    title: str
    source: str
    published_at: datetime | None = None
    primary_iso3: str | None = None
    event_type: str | None = None
    ingested_at: datetime
    impact_score: NewsImpactScoreOut | None = None
```

**`packages/schemas/src/atlas_schemas/__init__.py`** (MODIFY -- add news imports)

```python
from atlas_schemas.auth import LoginRequest, LoginResponse, Me
from atlas_schemas.bundle import CountryBundle, MacroTile, RatingsSection
from atlas_schemas.country import Country, CountryStatus, FxRegime
from atlas_schemas.fx import FxDeltas, FxObservation
from atlas_schemas.health import HealthResponse
from atlas_schemas.ingestion import DataVintage, IngestionReport, SourceStats
from atlas_schemas.macro import MacroIndicator, MacroValue
from atlas_schemas.news import EventType, ImpactLevel, NewsImpactScoreOut, NewsItemOut
from atlas_schemas.ratings import Agency, RatingAction
from atlas_schemas.risk import DimensionScore, RiskDimension, RiskScore
from atlas_schemas.scenario import (
    CountryImpact,
    ScenarioDeltas,
    ScenarioPreview,
    ScenarioRunOut,
    ShockVector,
)
from atlas_schemas.staleness import StalenessInfo, StalenessState

__all__ = [
    "Agency", "Country", "CountryBundle", "CountryImpact", "CountryStatus", "DataVintage",
    "DimensionScore", "EventType", "FxDeltas", "FxObservation", "FxRegime", "HealthResponse",
    "ImpactLevel", "IngestionReport", "LoginRequest", "LoginResponse", "MacroIndicator",
    "MacroTile", "MacroValue", "Me", "NewsImpactScoreOut", "NewsItemOut",
    "RatingAction", "RatingsSection",
    "RiskDimension", "RiskScore", "ScenarioDeltas", "ScenarioPreview",
    "ScenarioRunOut", "ShockVector", "SourceStats", "StalenessInfo",
    "StalenessState",
]
```

**`packages/schemas/tests/test_contracts.py`** (MODIFY -- append these tests)

```python
from atlas_schemas.news import EventType, ImpactLevel, NewsImpactScoreOut, NewsItemOut
import uuid
from datetime import datetime, UTC


def test_event_type_values():
    assert EventType.MONETARY == "Monetary"
    assert EventType.FISCAL == "Fiscal"
    assert EventType.POLITICAL == "Political"
    assert EventType.EXTERNAL == "External"
    assert EventType.RATING == "Rating"
    assert EventType.IMF == "IMF"
    assert EventType.MARKET == "Market"


def test_impact_level_values():
    assert ImpactLevel.LOW == "L"
    assert ImpactLevel.MEDIUM == "M"
    assert ImpactLevel.HIGH == "H"


def test_news_item_out_roundtrip():
    now = datetime.now(UTC)
    item = NewsItemOut(
        id=uuid.uuid4(),
        url="https://example.com/article",
        title="Kenya raises rates",
        source="Reuters",
        published_at=now,
        primary_iso3="KEN",
        event_type="Monetary",
        ingested_at=now,
        impact_score=None,
    )
    d = item.model_dump()
    assert NewsItemOut(**d).title == "Kenya raises rates"


def test_news_impact_score_out_roundtrip():
    now = datetime.now(UTC)
    score = NewsImpactScoreOut(
        id=uuid.uuid4(),
        news_item_id=uuid.uuid4(),
        fiscal_impact=ImpactLevel.LOW,
        external_impact=ImpactLevel.MEDIUM,
        fx_impact=ImpactLevel.HIGH,
        political_impact=ImpactLevel.LOW,
        rationale={"keywords": ["rate hike", "inflation"]},
        scorer="heuristic",
        scored_at=now,
    )
    d = score.model_dump()
    assert NewsImpactScoreOut(**d).fiscal_impact == "L"


def test_news_item_with_score():
    now = datetime.now(UTC)
    item_id = uuid.uuid4()
    item = NewsItemOut(
        id=item_id,
        url="https://example.com/article2",
        title="Nigeria fiscal deficit widens",
        source="IMF Blog",
        published_at=now,
        primary_iso3="NGA",
        event_type="Fiscal",
        ingested_at=now,
        impact_score=NewsImpactScoreOut(
            id=uuid.uuid4(),
            news_item_id=item_id,
            fiscal_impact=ImpactLevel.HIGH,
            external_impact=ImpactLevel.MEDIUM,
            fx_impact=ImpactLevel.MEDIUM,
            political_impact=ImpactLevel.LOW,
            rationale={"keywords": ["deficit", "spending"]},
            scorer="heuristic",
            scored_at=now,
        ),
    )
    assert item.impact_score is not None
    assert item.impact_score.fiscal_impact == "H"
```

### Verification

```bash
cd packages/schemas && python -m pytest tests/test_contracts.py -v -k "news or event_type or impact_level"
```

---

## Task 3 of 12 -- Migration 0008: news pipeline tables

**Goal:** Create `news_item` and `news_impact_score` tables with vector column, HNSW index, and CHECK constraints.

### Steps

- [ ] Create `infra/migrations/versions/0008_news_pipeline.py`
- [ ] Verify: `alembic upgrade head` succeeds

### Code

**`infra/migrations/versions/0008_news_pipeline.py`** (CREATE)

```python
"""news_item + news_impact_score tables

Revision ID: 0008_news_pipeline
Revises: 0007_scenario_title
Create Date: 2026-04-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0008_news_pipeline"
down_revision = "0007_scenario_title"
branch_labels = None
depends_on = None

EVENT_TYPES = ("Monetary", "Fiscal", "Political", "External", "Rating", "IMF", "Market")
IMPACT_LEVELS = ("L", "M", "H")


def upgrade() -> None:
    # -- news_item --
    op.create_table(
        "news_item",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("url_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column(
            "primary_iso3",
            sa.String(3),
            sa.ForeignKey("country.iso3"),
            nullable=True,
        ),
        sa.Column(
            "event_type",
            sa.String(32),
            nullable=True,
        ),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"event_type IS NULL OR event_type IN ({', '.join(repr(e) for e in EVENT_TYPES)})",
            name="ck_news_item_event_type",
        ),
    )

    # Add vector column via raw SQL (pgvector)
    op.execute("ALTER TABLE news_item ADD COLUMN embedding vector(384)")

    # Composite index for country news feeds
    op.create_index(
        "ix_news_item_iso3_published",
        "news_item",
        ["primary_iso3", sa.text("published_at DESC")],
    )

    # HNSW index for semantic dedup
    op.execute(
        "CREATE INDEX ix_news_embedding ON news_item "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # -- news_impact_score --
    op.create_table(
        "news_impact_score",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "news_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("news_item.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("fiscal_impact", sa.String(1), nullable=False),
        sa.Column("external_impact", sa.String(1), nullable=False),
        sa.Column("fx_impact", sa.String(1), nullable=False),
        sa.Column("political_impact", sa.String(1), nullable=False),
        sa.Column("rationale", JSONB, nullable=True),
        sa.Column("scorer", sa.String(32), nullable=False),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "fiscal_impact IN ('L', 'M', 'H')", name="ck_nis_fiscal"
        ),
        sa.CheckConstraint(
            "external_impact IN ('L', 'M', 'H')", name="ck_nis_external"
        ),
        sa.CheckConstraint(
            "fx_impact IN ('L', 'M', 'H')", name="ck_nis_fx"
        ),
        sa.CheckConstraint(
            "political_impact IN ('L', 'M', 'H')", name="ck_nis_political"
        ),
    )


def downgrade() -> None:
    op.drop_table("news_impact_score")
    op.execute("DROP INDEX IF EXISTS ix_news_embedding")
    op.drop_index("ix_news_item_iso3_published", table_name="news_item")
    op.drop_table("news_item")
```

### Verification

```bash
cd infra && alembic upgrade head
# Verify tables exist:
psql "$DATABASE_URL" -c "\d news_item"
psql "$DATABASE_URL" -c "\d news_impact_score"
psql "$DATABASE_URL" -c "\di ix_news_embedding"
```

---

## Task 4 of 12 -- SQLAlchemy models + config

**Goal:** Add `NewsItem` and `NewsImpactScore` ORM models. Add news poll settings to config.

### Steps

- [ ] Modify `apps/api/src/atlas_api/models.py` to add NewsItem + NewsImpactScore
- [ ] Modify `apps/api/src/atlas_api/config.py` to add news poll settings

### Code

**`apps/api/src/atlas_api/models.py`** (MODIFY -- append after ScenarioRun class)

```python
class NewsItem(Base):
    __tablename__ = "news_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_iso3: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("country.iso3"), nullable=True
    )
    event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    # Note: 'embedding' column is vector(384) managed via raw SQL in migration.
    # We do NOT map it here; we use raw queries for vector operations.


class NewsImpactScore(Base):
    __tablename__ = "news_impact_score"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    news_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_item.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    fiscal_impact: Mapped[str] = mapped_column(String(1), nullable=False)
    external_impact: Mapped[str] = mapped_column(String(1), nullable=False)
    fx_impact: Mapped[str] = mapped_column(String(1), nullable=False)
    political_impact: Mapped[str] = mapped_column(String(1), nullable=False)
    rationale: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    scorer: Mapped[str] = mapped_column(String(32), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
```

**`apps/api/src/atlas_api/config.py`** (MODIFY -- add news settings)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://atlas:atlas@localhost:5433/atlas"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 480
    demo_user_email: str = "analyst@atlas.test"
    demo_user_password: str = "change-me"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    ingestion_schedule_enabled: bool = True
    ingestion_cron: str = "0 3 * * *"  # 03:00 UTC daily
    news_poll_enabled: bool = True
    news_poll_cron: str = "*/10 * * * *"  # every 10 minutes


settings = Settings()
```

### Verification

```bash
python -c "from atlas_api.models import NewsItem, NewsImpactScore; print('Models OK')"
python -c "from atlas_api.config import settings; print(settings.news_poll_enabled, settings.news_poll_cron)"
```

---

## Task 5 of 12 -- GDELT poller

**Goal:** Async function that queries the GDELT DOC 2.0 API for each of our 10 countries and returns a list of raw article dicts (url, title, source, date).

### Steps

- [ ] Create `apps/api/src/atlas_api/services/news/__init__.py`
- [ ] Create `apps/api/src/atlas_api/services/news/gdelt.py`

### Code

**`apps/api/src/atlas_api/services/news/__init__.py`** (CREATE)

```python
"""News pipeline service modules."""
```

**`apps/api/src/atlas_api/services/news/gdelt.py`** (CREATE)

```python
"""GDELT DOC 2.0 API poller."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx
import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

log = structlog.get_logger()

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Map our 10 countries to GDELT search terms
COUNTRY_QUERIES: dict[str, str] = {
    "CIV": "Ivory Coast OR Cote d'Ivoire",
    "GHA": "Ghana",
    "KEN": "Kenya",
    "NGA": "Nigeria",
    "SEN": "Senegal",
    "ETH": "Ethiopia",
    "RWA": "Rwanda",
    "ZAF": "South Africa",
    "MAR": "Morocco",
    "EGY": "Egypt",
}

RETRY = AsyncRetrying(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)


@dataclass
class RawArticle:
    """Raw article fetched from an external source."""

    url: str
    title: str
    source: str
    published_at: datetime | None
    body_snippet: str
    source_feed: str  # "gdelt" or "rss"


async def poll_gdelt(http: httpx.AsyncClient) -> list[RawArticle]:
    """Query GDELT DOC API for each country and return raw articles."""
    articles: list[RawArticle] = []

    for iso3, query in COUNTRY_QUERIES.items():
        try:
            async for attempt in RETRY:
                with attempt:
                    resp = await http.get(
                        GDELT_DOC_API,
                        params={
                            "query": query,
                            "mode": "ArtList",
                            "format": "json",
                            "maxrecords": "50",
                        },
                        timeout=30.0,
                    )
                    resp.raise_for_status()

            data = resp.json()
            art_list = data.get("articles", [])
            for art in art_list:
                url = art.get("url", "").strip()
                title = art.get("title", "").strip()
                source_name = art.get("domain", art.get("source", "unknown"))
                date_str = art.get("seendate", "")

                if not url or not title:
                    continue

                pub_at = None
                if date_str:
                    try:
                        # GDELT dates: "20260417T120000Z"
                        pub_at = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ")
                    except ValueError:
                        pass

                articles.append(
                    RawArticle(
                        url=url,
                        title=title,
                        source=str(source_name)[:200],
                        published_at=pub_at,
                        body_snippet=art.get("socialimage", ""),  # GDELT doesn't return body
                        source_feed="gdelt",
                    )
                )

            log.info("gdelt_polled", iso3=iso3, articles=len(art_list))
        except Exception:
            log.exception("gdelt_poll_failed", iso3=iso3)

    return articles
```

### Verification

```bash
python -c "from atlas_api.services.news.gdelt import poll_gdelt, COUNTRY_QUERIES; print(f'{len(COUNTRY_QUERIES)} countries configured')"
```

---

## Task 6 of 12 -- RSS poller

**Goal:** Async function that fetches and parses configured RSS feeds, returns raw article dicts.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/news/rss.py`

### Code

**`apps/api/src/atlas_api/services/news/rss.py`** (CREATE)

```python
"""RSS feed poller for news ingestion."""

from __future__ import annotations

from datetime import datetime, UTC
from email.utils import parsedate_to_datetime

import feedparser
import httpx
import structlog

from atlas_api.services.news.gdelt import RawArticle

log = structlog.get_logger()

RSS_FEEDS: list[str] = [
    "https://feeds.reuters.com/reuters/AFRICANewsrss",
    "https://blogs.imf.org/feed/",
    "https://blogs.worldbank.org/feed",
]


def _parse_pub_date(entry: dict) -> datetime | None:
    """Extract publication date from RSS entry."""
    for field in ("published", "updated", "created"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except (ValueError, TypeError):
                pass
    # feedparser also provides a parsed tuple
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=UTC)
            except (ValueError, TypeError):
                pass
    return None


async def poll_rss(http: httpx.AsyncClient) -> list[RawArticle]:
    """Fetch and parse all configured RSS feeds."""
    articles: list[RawArticle] = []

    for feed_url in RSS_FEEDS:
        try:
            resp = await http.get(feed_url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            feed_title = feed.feed.get("title", feed_url)

            for entry in feed.entries:
                url = entry.get("link", "").strip()
                title = entry.get("title", "").strip()
                if not url or not title:
                    continue

                # Extract body snippet from summary/description
                body = entry.get("summary", entry.get("description", ""))
                if body:
                    # Strip HTML tags naively for keyword scanning
                    import re
                    body = re.sub(r"<[^>]+>", " ", body).strip()

                articles.append(
                    RawArticle(
                        url=url,
                        title=title,
                        source=str(feed_title)[:200],
                        published_at=_parse_pub_date(entry),
                        body_snippet=body[:2000] if body else "",
                        source_feed="rss",
                    )
                )

            log.info("rss_polled", feed=feed_url, articles=len(feed.entries))
        except Exception:
            log.exception("rss_poll_failed", feed=feed_url)

    return articles
```

### Verification

```bash
python -c "from atlas_api.services.news.rss import RSS_FEEDS; print(f'{len(RSS_FEEDS)} feeds configured')"
```

---

## Task 7 of 12 -- URL dedup + article storage

**Goal:** Check URL hash against existing `news_item` rows. Insert new articles (without embedding yet). Use SHA-256 of the URL for dedup.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/news/dedup.py`

### Code

**`apps/api/src/atlas_api/services/news/dedup.py`** (CREATE)

```python
"""URL-hash dedup and initial article storage."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from atlas_api.models import NewsItem
from atlas_api.services.news.gdelt import RawArticle

log = structlog.get_logger()


def url_hash(url: str) -> str:
    """SHA-256 hash of the normalized URL."""
    normalized = url.strip().lower().rstrip("/")
    return hashlib.sha256(normalized.encode()).hexdigest()


def get_existing_url_hashes(session: Session, days: int = 30) -> set[str]:
    """Load URL hashes from the last N days for fast dedup lookups."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    stmt = select(NewsItem.url_hash).where(NewsItem.ingested_at >= cutoff)
    return set(session.scalars(stmt).all())


def store_new_articles(
    session: Session,
    articles: list[RawArticle],
    existing_hashes: set[str],
) -> list[NewsItem]:
    """Insert new articles into news_item. Returns list of newly inserted rows."""
    new_items: list[NewsItem] = []
    skipped = 0

    for art in articles:
        h = url_hash(art.url)
        if h in existing_hashes:
            skipped += 1
            continue
        existing_hashes.add(h)  # prevent intra-batch dupes

        item = NewsItem(
            id=uuid.uuid4(),
            url=art.url,
            url_hash=h,
            title=art.title,
            source=art.source,
            published_at=art.published_at,
            body_text=art.body_snippet if art.body_snippet else None,
            raw_payload={"source_feed": art.source_feed},
        )
        session.add(item)
        new_items.append(item)

    if new_items:
        session.commit()

    log.info("url_dedup_complete", new=len(new_items), skipped=skipped)
    return new_items
```

### Verification

```bash
python -c "
from atlas_api.services.news.dedup import url_hash
h1 = url_hash('https://example.com/article')
h2 = url_hash('https://example.com/Article/')
# Normalized: same after lower+rstrip
print(f'hash1={h1[:16]}... hash2={h2[:16]}... match={h1 == h2}')
"
```

---

## Task 8 of 12 -- Embedding generator

**Goal:** Wrap `fastembed` to generate 384-dim vectors for news items, then update the `embedding` column via raw SQL (since pgvector columns are not mapped via ORM).

### Steps

- [ ] Create `apps/api/src/atlas_api/services/news/embeddings.py`

### Code

**`apps/api/src/atlas_api/services/news/embeddings.py`** (CREATE)

```python
"""Embedding generation using fastembed (ONNX, ~100MB)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from atlas_api.models import NewsItem

log = structlog.get_logger()

# Lazy singleton -- model is ~80MB, load once
_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        log.info("fastembed_model_loaded", model="all-MiniLM-L6-v2", dims=384)
    return _model


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate 384-dim embeddings for a batch of texts."""
    model = _get_model()
    # fastembed returns a generator of numpy arrays
    embeddings = list(model.embed(texts))
    return [emb.tolist() for emb in embeddings]


def update_embeddings(session: Session, items: list["NewsItem"]) -> int:
    """Generate embeddings for items and update the vector column via raw SQL."""
    if not items:
        return 0

    texts = [f"{item.title}. {item.body_text or ''}" for item in items]
    embeddings = generate_embeddings(texts)

    updated = 0
    for item, emb in zip(items, embeddings):
        # pgvector expects the vector as a string like '[0.1, 0.2, ...]'
        vec_str = "[" + ",".join(str(v) for v in emb) + "]"
        session.execute(
            text("UPDATE news_item SET embedding = :vec WHERE id = :id"),
            {"vec": vec_str, "id": str(item.id)},
        )
        updated += 1

    session.commit()
    log.info("embeddings_updated", count=updated)
    return updated
```

### Verification

```bash
python -c "
from atlas_api.services.news.embeddings import generate_embeddings
vecs = generate_embeddings(['Kenya raises interest rates by 50 basis points'])
print(f'dims={len(vecs[0])}, first3={vecs[0][:3]}')
assert len(vecs[0]) == 384
print('OK')
"
```

---

## Task 9 of 12 -- Semantic dedup

**Goal:** Use pgvector cosine similarity query to find near-duplicate articles (>0.92) against the last 7 days. Mark duplicates by setting `primary_iso3 = NULL`.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/news/semantic_dedup.py`

### Code

**`apps/api/src/atlas_api/services/news/semantic_dedup.py`** (CREATE)

```python
"""Semantic dedup using pgvector cosine similarity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from atlas_api.models import NewsItem

log = structlog.get_logger()

SIMILARITY_THRESHOLD = 0.92
LOOKBACK_DAYS = 7


def find_semantic_duplicates(
    session: Session,
    items: list["NewsItem"],
) -> list[str]:
    """
    For each new item, check if a semantically similar article exists
    in the last 7 days. Returns list of item IDs that are duplicates.

    Duplicates are soft-marked: primary_iso3 set to NULL so they don't
    appear in country feeds but remain in the DB for reference.
    """
    cutoff = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
    duplicate_ids: list[str] = []

    for item in items:
        # Get this item's embedding
        row = session.execute(
            text(
                "SELECT embedding FROM news_item WHERE id = :id AND embedding IS NOT NULL"
            ),
            {"id": str(item.id)},
        ).fetchone()

        if row is None or row[0] is None:
            continue

        # Find similar items from the last 7 days (excluding self)
        result = session.execute(
            text(
                """
                SELECT id, 1 - (embedding <=> (
                    SELECT embedding FROM news_item WHERE id = :item_id
                )) AS similarity
                FROM news_item
                WHERE id != :item_id
                  AND embedding IS NOT NULL
                  AND ingested_at >= :cutoff
                  AND 1 - (embedding <=> (
                      SELECT embedding FROM news_item WHERE id = :item_id
                  )) > :threshold
                ORDER BY similarity DESC
                LIMIT 1
                """
            ),
            {
                "item_id": str(item.id),
                "cutoff": cutoff,
                "threshold": SIMILARITY_THRESHOLD,
            },
        ).fetchone()

        if result is not None:
            # This item is a semantic duplicate -- soft-mark it
            duplicate_ids.append(str(item.id))
            log.debug(
                "semantic_duplicate_found",
                new_id=str(item.id),
                existing_id=str(result[0]),
                similarity=round(float(result[1]), 4),
            )

    if duplicate_ids:
        # Soft dedup: NULL out primary_iso3 so it doesn't show in feeds
        session.execute(
            text(
                "UPDATE news_item SET primary_iso3 = NULL "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": duplicate_ids},
        )
        session.commit()

    log.info("semantic_dedup_complete", checked=len(items), duplicates=len(duplicate_ids))
    return duplicate_ids
```

### Verification

```bash
python -c "from atlas_api.services.news.semantic_dedup import SIMILARITY_THRESHOLD; print(f'threshold={SIMILARITY_THRESHOLD}')"
```

---

## Task 10 of 12 -- Entity extraction + relevance filter + event classification

**Goal:** Use spaCy NER to find country mentions, set `primary_iso3`. Apply keyword gate for sovereign/macro relevance. Assign `event_type` via rule-based classification.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/news/entity_extraction.py`
- [ ] Create `apps/api/tests/test_entity_extraction.py`

### Code

**`apps/api/src/atlas_api/services/news/entity_extraction.py`** (CREATE)

```python
"""Entity extraction, relevance filtering, and event-type classification."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from atlas_api.models import NewsItem

log = structlog.get_logger()

# Lazy-loaded spaCy model
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
        log.info("spacy_model_loaded", model="en_core_web_sm")
    return _nlp


# Country name -> ISO3 mapping for our 10 countries
COUNTRY_NAME_MAP: dict[str, str] = {
    "ivory coast": "CIV",
    "cote d'ivoire": "CIV",
    "côte d'ivoire": "CIV",
    "abidjan": "CIV",
    "ghana": "GHA",
    "accra": "GHA",
    "kenya": "KEN",
    "nairobi": "KEN",
    "nigeria": "NGA",
    "abuja": "NGA",
    "lagos": "NGA",
    "senegal": "SEN",
    "dakar": "SEN",
    "ethiopia": "ETH",
    "addis ababa": "ETH",
    "rwanda": "RWA",
    "kigali": "RWA",
    "south africa": "ZAF",
    "johannesburg": "ZAF",
    "pretoria": "ZAF",
    "cape town": "ZAF",
    "morocco": "MAR",
    "rabat": "MAR",
    "casablanca": "MAR",
    "egypt": "EGY",
    "cairo": "EGY",
}

# Sovereign/macro relevance keywords -- article must contain at least one
RELEVANCE_KEYWORDS: set[str] = {
    "sovereign", "bond", "debt", "fiscal", "deficit", "budget",
    "imf", "world bank", "central bank", "interest rate", "monetary policy",
    "inflation", "gdp", "exchange rate", "currency", "devaluation",
    "credit rating", "moody", "fitch", "s&p", "outlook",
    "default", "restructuring", "eurobond", "treasury", "reserve",
    "trade balance", "current account", "capital flow", "foreign direct investment",
    "aid", "subsidy", "tax", "revenue", "expenditure", "austerity",
    "election", "government", "minister", "president", "parliament",
    "coup", "sanctions", "reform", "policy",
    "commodity", "oil", "gold", "cocoa", "copper",
}

# Event-type classification keywords
EVENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "Monetary": [
        "central bank", "interest rate", "monetary policy", "rate hike",
        "rate cut", "repo rate", "inflation target", "money supply",
        "quantitative", "tightening", "easing", "discount rate",
    ],
    "Fiscal": [
        "budget", "deficit", "fiscal", "expenditure", "revenue",
        "tax", "spending", "austerity", "debt-to-gdp", "subsidy",
        "public debt", "fiscal balance", "treasury bill",
    ],
    "Political": [
        "election", "president", "parliament", "coup", "protest",
        "political", "government", "opposition", "minister", "prime minister",
        "constitutional", "reform", "regime", "sanction",
    ],
    "External": [
        "trade balance", "current account", "export", "import",
        "foreign direct investment", "fdi", "capital flow", "remittance",
        "balance of payments", "tariff", "trade war",
    ],
    "Rating": [
        "credit rating", "moody", "fitch", "s&p", "upgrade", "downgrade",
        "outlook", "rating agency", "investment grade", "junk",
        "sovereign rating", "creditwatch",
    ],
    "IMF": [
        "imf", "international monetary fund", "world bank",
        "structural adjustment", "program review", "sdr",
        "special drawing rights", "article iv",
    ],
    "Market": [
        "bond", "eurobond", "yield", "spread", "equity", "stock",
        "commodity", "oil price", "gold price", "copper", "cocoa",
        "market", "investor", "portfolio",
    ],
}


def extract_country(text: str) -> str | None:
    """Extract primary country ISO3 from text using spaCy NER + keyword lookup."""
    text_lower = text.lower()

    # First pass: direct keyword matching (fast, handles most cases)
    country_counts: dict[str, int] = {}
    for name, iso3 in COUNTRY_NAME_MAP.items():
        count = len(re.findall(r"\b" + re.escape(name) + r"\b", text_lower))
        if count > 0:
            country_counts[iso3] = country_counts.get(iso3, 0) + count

    if country_counts:
        # Return the most-mentioned country
        return max(country_counts, key=country_counts.get)  # type: ignore[arg-type]

    # Second pass: spaCy NER for GPE entities
    nlp = _get_nlp()
    doc = nlp(text[:5000])  # Limit text length for performance
    for ent in doc.ents:
        if ent.label_ == "GPE":
            ent_lower = ent.text.lower()
            if ent_lower in COUNTRY_NAME_MAP:
                return COUNTRY_NAME_MAP[ent_lower]

    return None


def is_relevant(title: str, body: str | None) -> bool:
    """Check if article is relevant to sovereign finance using keyword gate."""
    combined = (title + " " + (body or "")).lower()
    return any(kw in combined for kw in RELEVANCE_KEYWORDS)


def classify_event_type(title: str, body: str | None) -> str:
    """Classify article into event type using keyword matching. Default: Market."""
    combined = (title + " " + (body or "")).lower()
    scores: dict[str, int] = {}

    for event_type, keywords in EVENT_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[event_type] = score

    if not scores:
        return "Market"

    return max(scores, key=scores.get)  # type: ignore[arg-type]


def process_entities(session: Session, items: list["NewsItem"]) -> tuple[int, int]:
    """
    For each item: extract country, check relevance, classify event type.
    Updates items in-place and commits.
    Returns (relevant_count, filtered_count).
    """
    relevant = 0
    filtered = 0

    for item in items:
        text_content = f"{item.title}. {item.body_text or ''}"

        # Check relevance first
        if not is_relevant(item.title, item.body_text):
            filtered += 1
            # Mark as irrelevant by leaving primary_iso3 = NULL
            continue

        # Extract country
        iso3 = extract_country(text_content)
        if iso3:
            item.primary_iso3 = iso3

        # Classify event type
        item.event_type = classify_event_type(item.title, item.body_text)
        relevant += 1

    session.commit()
    log.info("entity_extraction_complete", relevant=relevant, filtered=filtered)
    return relevant, filtered
```

**`apps/api/tests/test_entity_extraction.py`** (CREATE)

```python
"""Tests for entity extraction, relevance filter, and event classification."""

import pytest
from atlas_api.services.news.entity_extraction import (
    classify_event_type,
    extract_country,
    is_relevant,
)


class TestExtractCountry:
    def test_kenya_by_name(self):
        assert extract_country("Kenya raises interest rates") == "KEN"

    def test_nigeria_by_capital(self):
        assert extract_country("Central bank in Abuja announces policy") == "NGA"

    def test_south_africa_compound_name(self):
        assert extract_country("South Africa fiscal deficit widens") == "ZAF"

    def test_ivory_coast_alternate_name(self):
        assert extract_country("Cote d'Ivoire bond issuance") == "CIV"

    def test_most_mentioned_wins(self):
        text = "Kenya Kenya Kenya and Nigeria trade deal"
        assert extract_country(text) == "KEN"

    def test_no_country_returns_none(self):
        assert extract_country("Global markets rise today") is None

    def test_egypt_by_capital(self):
        assert extract_country("Protests in Cairo over budget cuts") == "EGY"


class TestIsRelevant:
    def test_relevant_sovereign_bond(self):
        assert is_relevant("Kenya sovereign bond issuance", None) is True

    def test_relevant_imf(self):
        assert is_relevant("IMF review for Ghana", None) is True

    def test_relevant_election(self):
        assert is_relevant("Nigeria election results", None) is True

    def test_irrelevant_sports(self):
        assert is_relevant("Kenya wins marathon gold", None) is False

    def test_relevant_from_body(self):
        assert is_relevant("Update from Africa", "central bank cuts rate") is True


class TestClassifyEventType:
    def test_monetary(self):
        assert classify_event_type("Central bank raises interest rate", None) == "Monetary"

    def test_fiscal(self):
        assert classify_event_type("Budget deficit widens in Ghana", None) == "Fiscal"

    def test_political(self):
        assert classify_event_type("President announces election date", None) == "Political"

    def test_rating(self):
        assert classify_event_type("Moody's downgrades Nigeria outlook", None) == "Rating"

    def test_imf(self):
        assert classify_event_type("IMF completes Article IV review", None) == "IMF"

    def test_external(self):
        assert classify_event_type("Trade balance deteriorates on imports", None) == "External"

    def test_default_market(self):
        assert classify_event_type("Investors eye Africa opportunities", None) == "Market"

    def test_mixed_highest_wins(self):
        # Multiple keywords: "central bank" + "interest rate" = 2 for Monetary
        # vs "budget" = 1 for Fiscal
        result = classify_event_type(
            "Central bank holds interest rate despite budget pressure", None
        )
        assert result == "Monetary"
```

### Verification

```bash
cd apps/api && python -m pytest tests/test_entity_extraction.py -v
```

---

## Task 11 of 12 -- Heuristic impact scorer

**Goal:** Keyword-weighted 4-axis scorer producing L/M/H ratings per axis (fiscal, external, fx, political). Writes `news_impact_score` rows with `scorer="heuristic"`.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/news/scorer.py`
- [ ] Create `apps/api/tests/test_scorer.py`

### Code

**`apps/api/src/atlas_api/services/news/scorer.py`** (CREATE)

```python
"""Heuristic keyword-weighted impact scorer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.orm import Session

from atlas_api.models import NewsImpactScore

if TYPE_CHECKING:
    from atlas_api.models import NewsItem

log = structlog.get_logger()

# Keyword -> weight mappings for each axis.
# Score = sum of weights for matched keywords. Thresholds: >=5 = H, >=2 = M, else L.

FISCAL_KEYWORDS: dict[str, int] = {
    "deficit": 3, "surplus": 2, "budget": 2, "fiscal": 2,
    "expenditure": 2, "spending": 2, "revenue": 2, "tax": 2,
    "austerity": 3, "debt-to-gdp": 3, "public debt": 3,
    "subsidy": 2, "fiscal balance": 3, "treasury bill": 2,
    "fiscal consolidation": 3, "primary balance": 3,
}

EXTERNAL_KEYWORDS: dict[str, int] = {
    "trade balance": 3, "current account": 3, "export": 2, "import": 2,
    "fdi": 3, "foreign direct investment": 3, "remittance": 2,
    "balance of payments": 3, "capital flow": 2, "tariff": 2,
    "trade war": 3, "trade deficit": 3, "external debt": 3,
    "aid": 2, "donor": 2, "grant": 2,
}

FX_KEYWORDS: dict[str, int] = {
    "exchange rate": 3, "currency": 2, "devaluation": 3,
    "depreciation": 3, "appreciation": 2, "forex": 2,
    "dollar": 2, "euro": 2, "peg": 2, "float": 2,
    "parallel market": 3, "black market": 3, "fx reserve": 3,
    "reserve": 2, "intervention": 2, "capital control": 3,
}

POLITICAL_KEYWORDS: dict[str, int] = {
    "election": 3, "president": 2, "parliament": 2, "coup": 5,
    "protest": 3, "political": 2, "government": 1, "opposition": 2,
    "minister": 1, "constitutional": 2, "reform": 2,
    "regime": 3, "sanction": 3, "instability": 3,
    "corruption": 3, "impeach": 3, "martial law": 5,
    "civil war": 5, "conflict": 3, "militia": 3,
}


def _score_axis(text: str, keywords: dict[str, int]) -> tuple[str, int, list[str]]:
    """Score text against a keyword set. Returns (level, raw_score, matched_keywords)."""
    text_lower = text.lower()
    total = 0
    matched: list[str] = []
    for kw, weight in keywords.items():
        if kw in text_lower:
            total += weight
            matched.append(kw)

    if total >= 5:
        level = "H"
    elif total >= 2:
        level = "M"
    else:
        level = "L"

    return level, total, matched


def score_article(title: str, body: str | None) -> dict:
    """
    Score an article across 4 axes. Returns dict with:
    - fiscal_impact, external_impact, fx_impact, political_impact: 'L'|'M'|'H'
    - rationale: dict with matched keywords and raw scores
    """
    combined = title + " " + (body or "")

    fiscal_level, fiscal_score, fiscal_kws = _score_axis(combined, FISCAL_KEYWORDS)
    external_level, external_score, external_kws = _score_axis(combined, EXTERNAL_KEYWORDS)
    fx_level, fx_score, fx_kws = _score_axis(combined, FX_KEYWORDS)
    political_level, political_score, political_kws = _score_axis(combined, POLITICAL_KEYWORDS)

    return {
        "fiscal_impact": fiscal_level,
        "external_impact": external_level,
        "fx_impact": fx_level,
        "political_impact": political_level,
        "rationale": {
            "fiscal": {"score": fiscal_score, "keywords": fiscal_kws},
            "external": {"score": external_score, "keywords": external_kws},
            "fx": {"score": fx_score, "keywords": fx_kws},
            "political": {"score": political_score, "keywords": political_kws},
        },
    }


def score_items(session: Session, items: list["NewsItem"]) -> int:
    """Score articles and write news_impact_score rows. Returns count scored."""
    scored = 0
    now = datetime.now(UTC)

    for item in items:
        # Only score items that have a country assignment (relevant + mapped)
        if not item.primary_iso3:
            continue

        result = score_article(item.title, item.body_text)

        score_row = NewsImpactScore(
            id=uuid.uuid4(),
            news_item_id=item.id,
            fiscal_impact=result["fiscal_impact"],
            external_impact=result["external_impact"],
            fx_impact=result["fx_impact"],
            political_impact=result["political_impact"],
            rationale=result["rationale"],
            scorer="heuristic",
            scored_at=now,
        )
        session.add(score_row)
        scored += 1

    if scored:
        session.commit()

    log.info("heuristic_scoring_complete", scored=scored)
    return scored
```

**`apps/api/tests/test_scorer.py`** (CREATE)

```python
"""Golden tests for heuristic impact scorer."""

from atlas_api.services.news.scorer import score_article


class TestScoreArticle:
    def test_fiscal_heavy_article(self):
        result = score_article(
            "Ghana budget deficit widens as expenditure surges",
            "Fiscal balance deteriorated. Public debt now at 80% of GDP.",
        )
        assert result["fiscal_impact"] == "H"
        assert "deficit" in result["rationale"]["fiscal"]["keywords"]
        assert "expenditure" in result["rationale"]["fiscal"]["keywords"]

    def test_fx_heavy_article(self):
        result = score_article(
            "Nigeria naira devaluation deepens amid parallel market pressure",
            "Exchange rate fell sharply. Currency depreciation accelerated.",
        )
        assert result["fx_impact"] == "H"
        assert "devaluation" in result["rationale"]["fx"]["keywords"]

    def test_political_coup(self):
        result = score_article(
            "Military coup in West Africa rattles markets",
            "Regime change and martial law declared.",
        )
        assert result["political_impact"] == "H"
        assert "coup" in result["rationale"]["political"]["keywords"]

    def test_mild_article_gets_low(self):
        result = score_article(
            "Kenya tourism sector shows growth",
            "Visitor numbers increase for the third quarter.",
        )
        assert result["fiscal_impact"] == "L"
        assert result["external_impact"] == "L"
        assert result["fx_impact"] == "L"
        assert result["political_impact"] == "L"

    def test_external_trade_article(self):
        result = score_article(
            "Trade balance worsens on import surge",
            "Current account deficit deepened. FDI inflows slowed.",
        )
        assert result["external_impact"] == "H"

    def test_medium_fiscal(self):
        result = score_article(
            "New tax measures announced",
            "Revenue collection expected to improve.",
        )
        # tax=2 + revenue=2 = 4, which is M (needs >=5 for H)
        assert result["fiscal_impact"] == "M"

    def test_imf_triggers_external(self):
        # "aid" keyword contributes to external axis
        result = score_article(
            "IMF program review complete, aid disbursed",
            "Grant funding and donor support confirmed.",
        )
        assert result["external_impact"] in ("M", "H")

    def test_rating_action(self):
        result = score_article(
            "Moody's downgrades Nigeria sovereign rating to junk",
            "Credit rating agency cites fiscal concerns.",
        )
        # This article has fiscal keywords too
        assert result["fiscal_impact"] in ("M", "H")
```

### Verification

```bash
cd apps/api && python -m pytest tests/test_scorer.py -v
```

---

## Task 12 of 12 -- Pipeline orchestrator + scheduler + API endpoints + integration test

**Goal:** Chain the full pipeline (GDELT + RSS -> URL dedup -> embed -> semantic dedup -> entity extraction -> scoring). Add the `news_poll` job to APScheduler. Create two REST endpoints. Write an integration test with mocked HTTP.

### Steps

- [ ] Create `apps/api/src/atlas_api/services/news/pipeline.py`
- [ ] Modify `apps/api/src/atlas_api/ingestion/scheduler.py` to add news job
- [ ] Create `apps/api/src/atlas_api/routers/news.py`
- [ ] Modify `apps/api/src/atlas_api/main.py` to wire news router
- [ ] Create `apps/api/tests/test_news_pipeline.py`

### Code

**`apps/api/src/atlas_api/services/news/pipeline.py`** (CREATE)

```python
"""News pipeline orchestrator -- chains all steps."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from atlas_api.db import SessionLocal
from atlas_api.services.news.dedup import get_existing_url_hashes, store_new_articles
from atlas_api.services.news.embeddings import update_embeddings
from atlas_api.services.news.entity_extraction import process_entities
from atlas_api.services.news.gdelt import poll_gdelt
from atlas_api.services.news.rss import poll_rss
from atlas_api.services.news.scorer import score_items
from atlas_api.services.news.semantic_dedup import find_semantic_duplicates

log = structlog.get_logger()


@dataclass
class PipelineReport:
    """Summary of a single pipeline run."""

    gdelt_fetched: int
    rss_fetched: int
    new_articles: int
    embeddings_generated: int
    semantic_duplicates: int
    relevant: int
    filtered: int
    scored: int


async def run_news_pipeline() -> PipelineReport:
    """
    Execute the full news ingestion pipeline:
    1. Poll GDELT + RSS
    2. URL-hash dedup + store
    3. Generate embeddings
    4. Semantic dedup
    5. Entity extraction + relevance filter + event classification
    6. Heuristic impact scoring
    """
    session = SessionLocal()
    try:
        async with httpx.AsyncClient() as http:
            # Step 1: Poll sources
            gdelt_articles = await poll_gdelt(http)
            rss_articles = await poll_rss(http)
            all_articles = gdelt_articles + rss_articles

            log.info(
                "pipeline_sources_polled",
                gdelt=len(gdelt_articles),
                rss=len(rss_articles),
                total=len(all_articles),
            )

            if not all_articles:
                return PipelineReport(
                    gdelt_fetched=0, rss_fetched=0, new_articles=0,
                    embeddings_generated=0, semantic_duplicates=0,
                    relevant=0, filtered=0, scored=0,
                )

        # Step 2: URL-hash dedup + store
        existing_hashes = get_existing_url_hashes(session)
        new_items = store_new_articles(session, all_articles, existing_hashes)

        if not new_items:
            log.info("pipeline_no_new_articles")
            return PipelineReport(
                gdelt_fetched=len(gdelt_articles),
                rss_fetched=len(rss_articles),
                new_articles=0,
                embeddings_generated=0, semantic_duplicates=0,
                relevant=0, filtered=0, scored=0,
            )

        # Step 3: Generate embeddings
        embed_count = update_embeddings(session, new_items)

        # Step 4: Semantic dedup
        dup_ids = find_semantic_duplicates(session, new_items)

        # Step 5: Entity extraction + relevance filter + event classification
        relevant, filtered = process_entities(session, new_items)

        # Step 6: Heuristic impact scoring
        scored = score_items(session, new_items)

        report = PipelineReport(
            gdelt_fetched=len(gdelt_articles),
            rss_fetched=len(rss_articles),
            new_articles=len(new_items),
            embeddings_generated=embed_count,
            semantic_duplicates=len(dup_ids),
            relevant=relevant,
            filtered=filtered,
            scored=scored,
        )

        log.info(
            "pipeline_complete",
            new=report.new_articles,
            scored=report.scored,
            duplicates=report.semantic_duplicates,
        )

        return report
    finally:
        session.close()
```

**`apps/api/src/atlas_api/ingestion/scheduler.py`** (MODIFY -- add news poll job)

```python
"""AsyncIO scheduler for nightly ingestion + news polling."""

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from atlas_api.config import settings
from atlas_api.ingestion.orchestrator import run_nightly

log = structlog.get_logger()


async def _run_news_poll() -> None:
    """Wrapper to import and run the news pipeline."""
    from atlas_api.services.news.pipeline import run_news_pipeline
    await run_news_pipeline()


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

    if settings.news_poll_enabled:
        scheduler.add_job(
            _run_news_poll,
            CronTrigger.from_crontab(settings.news_poll_cron, timezone="UTC"),
            id="news_poll",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        log.info("news_poll_configured", cron=settings.news_poll_cron)
    else:
        log.info("news_poll_disabled_via_env")

    return scheduler
```

**`apps/api/src/atlas_api/routers/news.py`** (CREATE)

```python
"""News API endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from atlas_api.deps import CurrentUser, DbSession
from atlas_schemas.news import NewsImpactScoreOut, NewsItemOut

from atlas_api.models import NewsImpactScore, NewsItem

router = APIRouter(prefix="/api/news", tags=["news"])


def _item_to_schema(item: NewsItem, score: NewsImpactScore | None) -> NewsItemOut:
    """Convert ORM models to Pydantic schema."""
    impact = None
    if score:
        impact = NewsImpactScoreOut(
            id=score.id,
            news_item_id=score.news_item_id,
            fiscal_impact=score.fiscal_impact,
            external_impact=score.external_impact,
            fx_impact=score.fx_impact,
            political_impact=score.political_impact,
            rationale=score.rationale,
            scorer=score.scorer,
            scored_at=score.scored_at,
        )

    return NewsItemOut(
        id=item.id,
        url=item.url,
        title=item.title,
        source=item.source,
        published_at=item.published_at,
        primary_iso3=item.primary_iso3,
        event_type=item.event_type,
        ingested_at=item.ingested_at,
        impact_score=impact,
    )


@router.get("", response_model=list[NewsItemOut])
def list_news(
    session: DbSession,
    _user: CurrentUser,
    iso3: str | None = Query(None, min_length=3, max_length=3),
    limit: int = Query(30, ge=1, le=100),
) -> list[NewsItemOut]:
    """
    List scored news items, optionally filtered by country.
    Returns items with primary_iso3 set (i.e., relevant + mapped).
    Ordered by published_at DESC.
    """
    stmt = (
        select(NewsItem, NewsImpactScore)
        .outerjoin(NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id)
        .where(NewsItem.primary_iso3.isnot(None))
    )

    if iso3:
        stmt = stmt.where(NewsItem.primary_iso3 == iso3.upper())

    stmt = stmt.order_by(NewsItem.published_at.desc().nullslast()).limit(limit)

    rows = session.execute(stmt).all()
    return [_item_to_schema(item, score) for item, score in rows]


@router.get("/{news_id}", response_model=NewsItemOut)
def get_news_item(
    session: DbSession,
    _user: CurrentUser,
    news_id: uuid.UUID,
) -> NewsItemOut:
    """Get a single news item with its impact score."""
    stmt = (
        select(NewsItem, NewsImpactScore)
        .outerjoin(NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id)
        .where(NewsItem.id == news_id)
    )
    row = session.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="news item not found")
    item, score = row
    return _item_to_schema(item, score)
```

**`apps/api/src/atlas_api/main.py`** (MODIFY -- add news router)

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.config import settings
from atlas_api.ingestion.scheduler import build_scheduler
from atlas_api.logging_config import configure_logging
from atlas_api.routers import auth, countries, health, news, scenarios

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = build_scheduler()
    if settings.ingestion_schedule_enabled or settings.news_poll_enabled:
        scheduler.start()
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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(countries.router)
app.include_router(scenarios.router)
app.include_router(news.router)
```

**`apps/api/tests/test_news_pipeline.py`** (CREATE)

```python
"""Integration tests for the news API endpoints with mocked GDELT/RSS."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from atlas_api.models import NewsImpactScore, NewsItem
from atlas_api.services.news.dedup import url_hash


@pytest.fixture
def seed_news(test_session):
    """Seed a news item and impact score for testing endpoints."""
    item_id = uuid.uuid4()
    item = NewsItem(
        id=item_id,
        url="https://example.com/kenya-rates",
        url_hash=url_hash("https://example.com/kenya-rates"),
        title="Kenya raises interest rates by 100bps",
        source="Reuters",
        published_at=datetime.now(UTC),
        body_text="Central bank of Kenya raised its benchmark rate to combat inflation.",
        primary_iso3="KEN",
        event_type="Monetary",
    )
    test_session.add(item)
    test_session.flush()

    score = NewsImpactScore(
        id=uuid.uuid4(),
        news_item_id=item_id,
        fiscal_impact="L",
        external_impact="L",
        fx_impact="M",
        political_impact="L",
        rationale={"fx": {"score": 3, "keywords": ["interest rate"]}},
        scorer="heuristic",
        scored_at=datetime.now(UTC),
    )
    test_session.add(score)
    test_session.commit()
    return item_id


class TestNewsEndpoints:
    """Test the GET /api/news and GET /api/news/{id} endpoints."""

    def test_list_news_requires_auth(self, client: TestClient):
        resp = client.get("/api/news")
        assert resp.status_code == 401

    def test_list_news_empty(self, authed_client: TestClient):
        resp = authed_client.get("/api/news")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_news_with_data(self, authed_client: TestClient, seed_news):
        resp = authed_client.get("/api/news?iso3=KEN")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["primary_iso3"] == "KEN"
        assert data[0]["event_type"] == "Monetary"
        assert data[0]["impact_score"] is not None
        assert data[0]["impact_score"]["scorer"] == "heuristic"
        assert data[0]["impact_score"]["fx_impact"] == "M"

    def test_list_news_filter_by_iso3(self, authed_client: TestClient, seed_news):
        # No news for Ghana
        resp = authed_client.get("/api/news?iso3=GHA")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_news_item(self, authed_client: TestClient, seed_news):
        item_id = seed_news
        resp = authed_client.get(f"/api/news/{item_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(item_id)
        assert data["title"] == "Kenya raises interest rates by 100bps"

    def test_get_news_item_not_found(self, authed_client: TestClient):
        fake_id = uuid.uuid4()
        resp = authed_client.get(f"/api/news/{fake_id}")
        assert resp.status_code == 404


class TestUrlDedup:
    """Unit tests for URL hash dedup logic."""

    def test_same_url_same_hash(self):
        h1 = url_hash("https://example.com/article")
        h2 = url_hash("https://example.com/article")
        assert h1 == h2

    def test_normalized_url(self):
        h1 = url_hash("https://example.com/article")
        h2 = url_hash("HTTPS://EXAMPLE.COM/ARTICLE/")
        assert h1 == h2

    def test_different_urls_different_hashes(self):
        h1 = url_hash("https://example.com/article1")
        h2 = url_hash("https://example.com/article2")
        assert h1 != h2


class TestScorer:
    """Quick smoke test for scorer integration."""

    def test_score_article_returns_all_axes(self):
        from atlas_api.services.news.scorer import score_article
        result = score_article("Test headline", "Test body")
        assert "fiscal_impact" in result
        assert "external_impact" in result
        assert "fx_impact" in result
        assert "political_impact" in result
        assert result["fiscal_impact"] in ("L", "M", "H")
```

### Verification

```bash
# Run integration tests
cd apps/api && python -m pytest tests/test_news_pipeline.py -v

# Run all news-related tests
cd apps/api && python -m pytest tests/test_scorer.py tests/test_entity_extraction.py tests/test_news_pipeline.py -v

# Manual smoke test (requires running DB + GDELT/RSS access):
# 1. Start the API: uvicorn atlas_api.main:app --reload
# 2. The news_poll job will fire every 10 minutes
# 3. Check: curl -b cookie http://localhost:8000/api/news?iso3=KEN
```

---

## Self-review checklist

| # | Check | Status |
|---|-------|--------|
| 1 | All enums use `StrEnum` | `EventType`, `ImpactLevel` both use `StrEnum` |
| 2 | Timestamps use `server_default=func.now()` + Python default | Yes, on `ingested_at`, `scored_at` in models and migration |
| 3 | FastAPI deps use `Annotated[..., Depends()]` | `DbSession` and `CurrentUser` from existing `deps.py` |
| 4 | Migration revision chain: `0008_news_pipeline` -> `0007_scenario_title` | Correct `down_revision` |
| 5 | pgvector column via raw SQL in migration | `op.execute("ALTER TABLE news_item ADD COLUMN embedding vector(384)")` |
| 6 | HNSW index created in migration | `op.execute("CREATE INDEX ix_news_embedding ...")` |
| 7 | Event types match spec | Monetary, Fiscal, Political, External, Rating, IMF, Market |
| 8 | Impact levels match spec | L, M, H with CHECK constraints |
| 9 | `news_impact_score.news_item_id` is FK UNIQUE | Yes, in both migration and model |
| 10 | URL dedup uses SHA-256 | `hashlib.sha256` in `dedup.py` |
| 11 | Semantic dedup threshold 0.92 | `SIMILARITY_THRESHOLD = 0.92` |
| 12 | Scorer uses `scorer="heuristic"` | Yes, hardcoded in `score_items()` |
| 13 | Scheduler adds second job at `*/10 * * * *` | `news_poll` job with `news_poll_cron` |
| 14 | `NEWS_POLL_ENABLED` env var support | `news_poll_enabled: bool = True` in Settings |
| 15 | No `sentence-transformers` dependency | Using `fastembed` with ONNX backend |
| 16 | `feedparser` for RSS | Yes, in `rss.py` |
| 17 | GDELT DOC 2.0 API URL correct | `https://api.gdeltproject.org/api/v2/doc/doc` |
| 18 | RSS feeds list matches spec | Reuters Africa, IMF Blog, World Bank Blogs |
| 19 | 10 countries mapped | All 10 in `COUNTRY_NAME_MAP` with cities/alternates |
| 20 | Integration test mocks HTTP, tests both endpoints | Yes, tests list + get + auth + 404 |
| 21 | Every task has actual code, no placeholders | Verified |
| 22 | Composite index on `(primary_iso3, published_at DESC)` | In migration `0008` |

---

## Execution handoff

This plan is ready for execution. To implement it:

```
/superpowers:execute-plan docs/superpowers/plans/2026-04-17-atlas-news-pipeline.md
```

Or use subagent-driven development for parallel execution:

```
/superpowers:subagent-driven-development docs/superpowers/plans/2026-04-17-atlas-news-pipeline.md
```

**Estimated execution time:** ~45 minutes for a single agent, ~20 minutes with parallel subagents.

**Dependencies between tasks:**
- Task 1 (deps) must complete before Tasks 5-11
- Task 2 (schemas) is independent
- Task 3 (migration) must complete before Task 4
- Task 4 (models+config) must complete before Tasks 5-11
- Tasks 5-6 (pollers) are independent of each other
- Task 7 (URL dedup) depends on Tasks 5-6
- Task 8 (embeddings) depends on Task 7
- Task 9 (semantic dedup) depends on Task 8
- Task 10 (entity extraction) depends on Task 7
- Task 11 (scorer) depends on Task 10
- Task 12 (orchestrator+endpoints) depends on all previous tasks
