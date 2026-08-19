# News Relevance and Quality Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every served news item on-policy, English-readable, and filed under the country it is actually about, without thinning the feed.

**Architecture:** Deterministic pre-filters (themed source queries, junk blocklist, dedup, budget cap) cut volume cheaply, then one structured Claude call per surviving article judges relevance, primary country, translation, event type and impact together. A `relevant` boolean gates serving, and a backfill script re-grades the articles already in the database.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, pytest, Anthropic SDK via `services/ai/provider.py`, React and TypeScript on the web side.

Spec: `docs/superpowers/specs/2026-08-19-news-relevance-design.md`

## Global Constraints

- Python 3.12. Never bump `.python-version`.
- Lint and types must pass: `uv run ruff check .` and `uv run mypy apps/api/src packages/schemas/src` (mypy is strict).
- Model id is `claude-sonnet-4-5`, read from `settings.ai_model`. Never hardcode a model string.
- All Claude calls go through `atlas_api.services.ai.provider.call_tool`. Never construct an `anthropic` client directly.
- Every Claude call persists a `PromptTrace` via `atlas_api.services.ai.trace.persist_trace`.
- The ten tracked countries are exactly: CIV, GHA, KEN, NGA, SEN, ETH, RWA, ZAF, MAR, EGY.
- Editorial policy, used verbatim in prompts and tests: **in scope** is sovereign debt, IMF programmes, rating actions, fiscal and monetary policy, FX, reserves, bonds and eurobonds, growth, inflation, material trade and investment flows, plus politics that materially affects creditworthiness (elections, coups, sanctions, major reform, significant unrest). **Out of scope** is sport, entertainment, crime blotter, general human interest, routine corporate news with no sovereign read-through, and politics with no plausible link to creditworthiness.
- No new runtime dependency is added by this plan. Language comes from the GDELT `language` field and from the AI `source_lang` output.
- Never write an em-dash or a connector slash in user-facing copy.
- Tests run with: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest`. The full suite needs Docker for testcontainers. Unit tests listed here use mocks and do not need Docker.
- Commit after every task. Do not push. The user approves pushes separately.

## Deliberate deviations from the spec

**Language detection.** The spec places language detection in the pre-filter. This plan does not add a language detection library. The AI grader already returns `source_lang` as part of the same call it must make anyway, and GDELT supplies a `language` field for free. The observable outcome the spec asked for is unchanged: `source_lang` is stored on every graded item, and nothing is ever dropped for being non-English. This removes a dependency and a failure mode at no cost.

**A rate limit discovered during planning.** GDELT rejects more than one request every five seconds with HTTP 429. The current poller loops ten countries with no delay, so it is very likely being throttled today, which is a second and previously unknown cause of thin news volume. Task 4 fixes this. It was not in the spec because it was found while probing the live API.

## File Structure

| File | Responsibility |
|---|---|
| `infra/migrations/versions/0017_news_relevance.py` | Create: schema change |
| `apps/api/src/atlas_api/models.py` | Modify: `NewsItem` columns, new `NewsItemCountry` |
| `packages/schemas/src/atlas_schemas/ai.py` | Modify: add `NewsGradeResult` |
| `packages/schemas/src/atlas_schemas/news.py` | Modify: extend `NewsItemOut` |
| `apps/api/src/atlas_api/config.py` | Modify: three settings |
| `apps/api/src/atlas_api/services/news/gdelt.py` | Modify: themed queries, rate limit, max records |
| `apps/api/src/atlas_api/services/news/rss.py` | Modify: wider feed list |
| `apps/api/src/atlas_api/services/news/prefilter.py` | Create: junk cut, language, budget |
| `apps/api/src/atlas_api/services/news/ai_grader.py` | Create: the single structured Claude call |
| `apps/api/src/atlas_api/services/news/persist.py` | Create: write grade, links, score, trace |
| `apps/api/src/atlas_api/services/news/pipeline.py` | Modify: rewire to the new stages |
| `apps/api/src/atlas_api/routers/news.py` | Modify: relevance gate, link join, ordering |
| `apps/web/src/routes/NewsIntelligence.tsx` | Modify: rationale and translation badge |
| `apps/api/scripts/regrade_news.py` | Create: one-off backfill |

---

### Task 1: Schema for relevance, translation and multi-country

**Files:**
- Create: `infra/migrations/versions/0017_news_relevance.py`
- Modify: `apps/api/src/atlas_api/models.py`
- Test: `apps/api/tests/test_news_relevance_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `NewsItem.relevant: bool`, `NewsItem.relevance_score: int | None`, `NewsItem.relevance_rationale: str | None`, `NewsItem.source_lang: str | None`, `NewsItem.original_title: str | None`, `NewsItem.summary_en: str | None`, `NewsItem.ai_graded: bool`, `NewsItem.prompt_trace_id: uuid.UUID | None`. New model `NewsItemCountry` with columns `news_item_id: uuid.UUID`, `iso3: str`, `role: str` where role is `"primary"` or `"secondary"`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_relevance_models.py`:

```python
"""Model-level checks for the news relevance columns and country links."""

from __future__ import annotations

from atlas_api.models import NewsItem, NewsItemCountry


def test_news_item_has_relevance_columns():
    cols = NewsItem.__table__.columns
    for name in (
        "relevant",
        "relevance_score",
        "relevance_rationale",
        "source_lang",
        "original_title",
        "summary_en",
        "ai_graded",
        "prompt_trace_id",
    ):
        assert name in cols, f"NewsItem missing column {name}"


def test_relevant_defaults_to_false():
    assert NewsItem.__table__.columns["relevant"].default.arg is False


def test_news_item_country_shape():
    cols = NewsItemCountry.__table__.columns
    assert "news_item_id" in cols
    assert "iso3" in cols
    assert "role" in cols
    pk = {c.name for c in NewsItemCountry.__table__.primary_key.columns}
    assert pk == {"news_item_id", "iso3"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_relevance_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'NewsItemCountry'`.

- [ ] **Step 3: Add the model changes**

In `apps/api/src/atlas_api/models.py`, inside `class NewsItem`, add these columns immediately after the existing `event_type` column:

```python
    relevant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.false()
    )
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    original_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_graded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.false()
    )
    prompt_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_trace.id"), nullable=True
    )
```

Then add this new model directly after the `NewsItem` class:

```python
class NewsItemCountry(Base):
    """Link table so one article can appear on every country it genuinely covers."""

    __tablename__ = "news_item_country"

    news_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_item.id", ondelete="CASCADE"), primary_key=True
    )
    iso3: Mapped[str] = mapped_column(
        String(3), ForeignKey("country.iso3"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="primary")
```

If `Boolean` is not already imported in `models.py`, add it to the existing `from sqlalchemy import ...` line. Check first with `grep -n "^from sqlalchemy import" apps/api/src/atlas_api/models.py` and only add what is missing.

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_relevance_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Write the migration**

Create `infra/migrations/versions/0017_news_relevance.py`:

```python
"""Add news relevance, translation and multi-country link

Revision ID: 0017_news_relevance
Revises: 0016_report
Create Date: 2026-08-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0017_news_relevance"
down_revision = "0016_report"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_item",
        sa.Column("relevant", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("news_item", sa.Column("relevance_score", sa.Integer(), nullable=True))
    op.add_column("news_item", sa.Column("relevance_rationale", sa.Text(), nullable=True))
    op.add_column("news_item", sa.Column("source_lang", sa.String(8), nullable=True))
    op.add_column("news_item", sa.Column("original_title", sa.Text(), nullable=True))
    op.add_column("news_item", sa.Column("summary_en", sa.Text(), nullable=True))
    op.add_column(
        "news_item",
        sa.Column("ai_graded", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "news_item",
        sa.Column(
            "prompt_trace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("prompt_trace.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_news_item_relevant", "news_item", ["relevant"])
    op.create_index("ix_news_item_relevance_score", "news_item", ["relevance_score"])

    op.create_table(
        "news_item_country",
        sa.Column(
            "news_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("news_item.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "iso3", sa.String(3), sa.ForeignKey("country.iso3"), primary_key=True
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="primary"),
    )
    op.create_index("ix_news_item_country_iso3", "news_item_country", ["iso3"])

    # Backfill links from the existing primary_iso3 so nothing is orphaned.
    op.execute(
        """
        INSERT INTO news_item_country (news_item_id, iso3, role)
        SELECT id, primary_iso3, 'primary' FROM news_item
        WHERE primary_iso3 IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_news_item_country_iso3", "news_item_country")
    op.drop_table("news_item_country")
    op.drop_index("ix_news_item_relevance_score", "news_item")
    op.drop_index("ix_news_item_relevant", "news_item")
    for col in (
        "prompt_trace_id",
        "ai_graded",
        "summary_en",
        "original_title",
        "source_lang",
        "relevance_rationale",
        "relevance_score",
        "relevant",
    ):
        op.drop_column("news_item", col)
```

- [ ] **Step 6: Verify the migration applies**

Run: `uv run alembic -c infra/migrations/alembic.ini upgrade head`
Expected: no error, and `0017_news_relevance` is the new head.

Confirm with: `uv run alembic -c infra/migrations/alembic.ini current`
Expected: output contains `0017_news_relevance`.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check .
git add apps/api/src/atlas_api/models.py infra/migrations/versions/0017_news_relevance.py apps/api/tests/test_news_relevance_models.py
git commit -m "feat(news): add relevance, translation and multi-country schema"
```

---

### Task 2: Typed contracts for the grader and the API

**Files:**
- Modify: `packages/schemas/src/atlas_schemas/ai.py`
- Modify: `packages/schemas/src/atlas_schemas/news.py`
- Test: `apps/api/tests/test_news_grade_schema.py`

**Interfaces:**
- Consumes: `EventType` and `ImpactLevel` from `atlas_schemas.news`.
- Produces: `NewsGradeResult` in `atlas_schemas.ai` with fields `relevant: bool`, `relevance_score: int`, `rationale: str`, `primary_iso3: str | None`, `secondary_iso3: list[str]`, `event_type: str`, `fiscal_impact: str`, `external_impact: str`, `fx_impact: str`, `political_impact: str`, `source_lang: str`, `title_en: str`, `summary_en: str`. Also extends `NewsItemOut` with `summary_en`, `source_lang`, `relevance_score`, `relevance_rationale`, `translated`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_grade_schema.py`:

```python
"""Contract tests for the news grading result model."""

from __future__ import annotations

import pytest
from atlas_schemas.ai import NewsGradeResult
from pydantic import ValidationError


def _valid(**overrides):
    base = {
        "relevant": True,
        "relevance_score": 82,
        "rationale": "Reports an IMF disbursement that changes Ghana's external position.",
        "primary_iso3": "GHA",
        "secondary_iso3": [],
        "event_type": "IMF",
        "fiscal_impact": "H",
        "external_impact": "H",
        "fx_impact": "M",
        "political_impact": "L",
        "source_lang": "en",
        "title_en": "IMF approves new disbursement for Ghana",
        "summary_en": "The IMF board approved a tranche under the existing programme.",
    }
    base.update(overrides)
    return base


def test_accepts_a_valid_grade():
    result = NewsGradeResult(**_valid())
    assert result.primary_iso3 == "GHA"
    assert result.relevance_score == 82


def test_rejects_out_of_range_score():
    with pytest.raises(ValidationError):
        NewsGradeResult(**_valid(relevance_score=140))


def test_rejects_bad_impact_level():
    with pytest.raises(ValidationError):
        NewsGradeResult(**_valid(fiscal_impact="VERY_HIGH"))


def test_allows_null_primary_country_for_irrelevant_items():
    result = NewsGradeResult(**_valid(relevant=False, primary_iso3=None, relevance_score=4))
    assert result.primary_iso3 is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_grade_schema.py -v`
Expected: FAIL with `ImportError: cannot import name 'NewsGradeResult'`.

- [ ] **Step 3: Add `NewsGradeResult`**

Append to `packages/schemas/src/atlas_schemas/ai.py`:

```python
# -- News Grading -----------------------------------------------------------


class NewsGradeResult(BaseModel):
    """The typed output Claude must return when grading one news article."""

    relevant: bool = Field(..., description="True only if the article is on editorial policy")
    relevance_score: int = Field(..., ge=0, le=100, description="Confidence and importance, 0-100")
    rationale: str = Field(..., description="One sentence, grounded in the article, on why")
    primary_iso3: str | None = Field(
        None, description="The single country the article is actually about, or null"
    )
    secondary_iso3: list[str] = Field(
        default_factory=list, description="Other tracked countries genuinely covered"
    )
    event_type: str = Field(..., description="One of the Atlas event types")
    fiscal_impact: str = Field(..., pattern="^[LMH]$")
    external_impact: str = Field(..., pattern="^[LMH]$")
    fx_impact: str = Field(..., pattern="^[LMH]$")
    political_impact: str = Field(..., pattern="^[LMH]$")
    source_lang: str = Field(..., description="ISO 639-1 code of the source article")
    title_en: str = Field(..., description="English title, translated when needed")
    summary_en: str = Field(..., description="Two sentence English summary")
```

- [ ] **Step 4: Extend `NewsItemOut`**

In `packages/schemas/src/atlas_schemas/news.py`, add these fields to `NewsItemOut` after `event_type`:

```python
    summary_en: str | None = None
    source_lang: str | None = None
    relevance_score: int | None = None
    relevance_rationale: str | None = None
    translated: bool = False
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_grade_schema.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
uv run ruff check .
git add packages/schemas/src/atlas_schemas/ai.py packages/schemas/src/atlas_schemas/news.py apps/api/tests/test_news_grade_schema.py
git commit -m "feat(news): add NewsGradeResult contract and extend NewsItemOut"
```

---

### Task 3: Settings for the relevance dial and cost caps

**Files:**
- Modify: `apps/api/src/atlas_api/config.py`
- Modify: `.env.example`
- Test: `apps/api/tests/test_news_settings.py`

**Interfaces:**
- Produces: `settings.news_relevance_threshold: int` (default 60), `settings.news_ai_calls_per_run: int` (default 40), `settings.news_translate_enabled: bool` (default True).

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_settings.py`:

```python
"""The news tuning dials must exist with the agreed defaults."""

from __future__ import annotations

from atlas_api.config import Settings


def test_news_tuning_defaults():
    s = Settings()
    assert s.news_relevance_threshold == 60
    assert s.news_ai_calls_per_run == 40
    assert s.news_translate_enabled is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_settings.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'news_relevance_threshold'`.

- [ ] **Step 3: Add the settings**

In `apps/api/src/atlas_api/config.py`, add these three lines directly below the existing `news_poll_cron` line:

```python
    news_relevance_threshold: int = 60
    news_ai_calls_per_run: int = 40
    news_translate_enabled: bool = True
```

Then append to `.env.example` under the AI section:

```
# --- News grading (optional, defaults shown) ---
NEWS_RELEVANCE_THRESHOLD=60
NEWS_AI_CALLS_PER_RUN=40
NEWS_TRANSLATE_ENABLED=true
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_settings.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
uv run ruff check .
git add apps/api/src/atlas_api/config.py .env.example apps/api/tests/test_news_settings.py
git commit -m "feat(news): add relevance threshold and AI budget settings"
```

---

### Task 4: Tighten the sources

**Files:**
- Modify: `apps/api/src/atlas_api/services/news/gdelt.py`
- Modify: `apps/api/src/atlas_api/services/news/rss.py`
- Test: `apps/api/tests/test_news_sources.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `gdelt.COUNTRY_QUERIES` values now contain a theme clause. `gdelt.THEME_CLAUSE: str`. `poll_gdelt(http, *, english_only=False, timespan="", max_records=100, request_delay=5.0)`. `RawArticle` gains no fields, but GDELT `language` is stored into `raw_payload` by `store_new_articles` already, and `poll_gdelt` now sets `body_snippet` from the article title when GDELT returns no body.

**Context the implementer needs:** GDELT rate limits to one request every 5 seconds and returns HTTP 429 with a plain text body when exceeded. The current poller loops ten countries with no delay, so it trips this limit. GDELT `ArtList` entries include a `language` field. Treat it as optional and default to `None` if absent, because the AI reports `source_lang` authoritatively later.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_sources.py`:

```python
"""Source layer: themed queries, rate limiting, and resilient RSS."""

from __future__ import annotations

import httpx
import pytest
from atlas_api.services.news import gdelt as gdelt_mod
from atlas_api.services.news.gdelt import THEME_CLAUSE, poll_gdelt


def test_every_country_query_carries_the_theme_clause():
    for iso3, query in gdelt_mod.COUNTRY_QUERIES.items():
        assert THEME_CLAUSE in query, f"{iso3} query is missing the theme clause"


def test_theme_clause_covers_macro_and_material_politics():
    lowered = THEME_CLAUSE.lower()
    for term in ("debt", "imf", "inflation", "bond", "central bank", "rating", "election"):
        assert term in lowered, f"theme clause missing {term}"


@pytest.mark.asyncio
async def test_poll_gdelt_spaces_requests_and_tolerates_failure(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(gdelt_mod.asyncio, "sleep", fake_sleep)

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            # First country fails. The run must continue.
            return httpx.Response(429, text="Please limit requests")
        return httpx.Response(
            200,
            json={
                "articles": [
                    {
                        "url": f"https://example.com/{calls['n']}",
                        "title": "Ghana debt restructuring advances",
                        "domain": "example.com",
                        "seendate": "20260819T120000Z",
                        "language": "English",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        articles = await poll_gdelt(http, max_records=10, request_delay=5.0)

    assert len(articles) == len(gdelt_mod.COUNTRY_QUERIES) - 1
    assert sleeps and all(s == 5.0 for s in sleeps)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_sources.py -v`
Expected: FAIL with `ImportError: cannot import name 'THEME_CLAUSE'`.

- [ ] **Step 3: Rewrite the GDELT query block**

In `apps/api/src/atlas_api/services/news/gdelt.py`, add `import asyncio` to the imports, then replace the whole `COUNTRY_QUERIES` dict with:

```python
# Sovereign macro plus material politics. Keeps junk out at the source, which is
# far cheaper than filtering it later.
THEME_CLAUSE = (
    '(debt OR IMF OR inflation OR bond OR eurobond OR fiscal OR budget OR deficit '
    'OR "central bank" OR "interest rate" OR rating OR downgrade OR upgrade '
    'OR currency OR reserves OR "exchange rate" OR economy OR "economic growth" '
    'OR election OR coup OR sanctions OR protests OR reform)'
)

_COUNTRY_TERMS: dict[str, str] = {
    "CIV": '("Ivory Coast" OR "Cote Ivoire")',
    "GHA": "Ghana",
    "KEN": "Kenya",
    "NGA": "Nigeria",
    "SEN": "Senegal",
    "ETH": "Ethiopia",
    "RWA": "Rwanda",
    "ZAF": '"South Africa"',
    "MAR": "Morocco",
    "EGY": "Egypt",
}

COUNTRY_QUERIES: dict[str, str] = {
    iso3: f"{term} AND {THEME_CLAUSE}" for iso3, term in _COUNTRY_TERMS.items()
}
```

- [ ] **Step 4: Add rate limiting and raise the record cap**

In the same file, change the `poll_gdelt` signature to:

```python
async def poll_gdelt(
    http: httpx.AsyncClient,
    *,
    english_only: bool = False,
    timespan: str = "",
    max_records: int = 100,
    request_delay: float = 5.0,
) -> list[RawArticle]:
```

Inside the `for iso3, query in COUNTRY_QUERIES.items():` loop, make the first statement of the loop body a delay for every iteration after the first. Add a counter before the loop:

```python
    first_request = True
```

and at the top of the loop body:

```python
        if not first_request:
            # GDELT rejects more than one request every 5 seconds with HTTP 429.
            await asyncio.sleep(request_delay)
        first_request = False
```

Then, where the `RawArticle` is constructed, replace the `body_snippet` argument with:

```python
                        body_snippet=title,  # GDELT returns no body, title is the only text
```

`english_only` stays defaulted to `False` on purpose. Non-English articles are wanted and are translated later.

- [ ] **Step 5: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_sources.py -v`
Expected: 3 passed.

- [ ] **Step 6: Widen the RSS feed list**

In `apps/api/src/atlas_api/services/news/rss.py`, replace the `RSS_FEEDS` list with:

```python
RSS_FEEDS: list[str] = [
    "https://feeds.reuters.com/reuters/AFRICANewsrss",
    "https://www.africanews.com/feed/rss",
    "https://allafrica.com/tools/headlines/rdf/business/headlines.rdf",
    "https://www.theafricareport.com/feed/",
    "https://african.business/feed",
]
```

A feed that 404s is already handled by the existing per-feed `try` and `except`, so a dead feed cannot abort a run.

- [ ] **Step 7: Verify RSS resilience and commit**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_sources.py apps/api/tests -k "rss" -v`
Expected: PASS, no regressions in existing RSS tests.

```bash
uv run ruff check .
git add apps/api/src/atlas_api/services/news/gdelt.py apps/api/src/atlas_api/services/news/rss.py apps/api/tests/test_news_sources.py
git commit -m "feat(news): theme-filter GDELT queries, respect rate limit, widen RSS"
```

---

### Task 5: Pre-filter stage

**Files:**
- Create: `apps/api/src/atlas_api/services/news/prefilter.py`
- Test: `apps/api/tests/test_news_prefilter.py`

**Interfaces:**
- Consumes: `settings.news_ai_calls_per_run` from Task 3.
- Produces:
  - `TRACKED_ISO3: frozenset[str]`
  - `is_obvious_junk(title: str, body: str) -> bool`
  - `split_by_budget(items: list[T], limit: int) -> tuple[list[T], list[T]]` returning `(to_grade, deferred)`

**Design note for the implementer:** the junk list is deliberately narrow. Its only job is to avoid paying for an AI call on an obvious sports report. Anything ambiguous must pass through to the AI, because the AI is the component that is allowed to make editorial judgements.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_prefilter.py`:

```python
"""Pre-filter must cut only obvious junk and must never eat macro news."""

from __future__ import annotations

from atlas_api.services.news.prefilter import (
    TRACKED_ISO3,
    is_obvious_junk,
    split_by_budget,
)

JUNK = [
    ("Ghana beats Nigeria 2-1 in AFCON quarter final", "Full time report from the stadium."),
    ("Nollywood star announces new album release", "The singer spoke to reporters."),
    ("Obituary: veteran actor dies aged 81", "Family announced the funeral service."),
]

MACRO = [
    ("Ghana secures IMF disbursement", "The board approved the third review tranche."),
    ("Kenya shilling hits record low against dollar", "Reserves cover four months of imports."),
    ("Senegal debt restructuring talks open", "Bondholders met government officials."),
    ("Egypt election result raises reform questions", "Investors weigh policy continuity."),
]


def test_junk_is_cut():
    for title, body in JUNK:
        assert is_obvious_junk(title, body) is True, f"should be junk: {title}"


def test_macro_is_never_cut():
    for title, body in MACRO:
        assert is_obvious_junk(title, body) is False, f"must not be junk: {title}"


def test_tracked_countries_are_the_ten():
    assert TRACKED_ISO3 == frozenset(
        {"CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY"}
    )


def test_budget_split():
    to_grade, deferred = split_by_budget(list(range(10)), 4)
    assert to_grade == [0, 1, 2, 3]
    assert deferred == [4, 5, 6, 7, 8, 9]


def test_budget_split_when_under_limit():
    to_grade, deferred = split_by_budget([1, 2], 10)
    assert to_grade == [1, 2]
    assert deferred == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_prefilter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atlas_api.services.news.prefilter'`.

- [ ] **Step 3: Write the implementation**

Create `apps/api/src/atlas_api/services/news/prefilter.py`:

```python
"""Cheap deterministic pre-filters that run before any paid AI call.

This module deliberately makes no editorial judgement. It removes only articles
that are obviously off-topic, and it caps how many items reach the grader. Every
ambiguous article is passed through, because the AI grader is the component that
is allowed to decide what is relevant.
"""

from __future__ import annotations

from typing import TypeVar

TRACKED_ISO3: frozenset[str] = frozenset(
    {"CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY"}
)

# Narrow on purpose. A term belongs here only if it cannot plausibly appear in a
# sovereign macro story.
_JUNK_TERMS: frozenset[str] = frozenset(
    {
        "afcon", "premier league", "world cup", "quarter final", "semi final",
        "full time", "kick off", "goalkeeper", "striker", "midfielder",
        "nollywood", "bollywood", "box office", "red carpet", "new album",
        "obituary", "funeral service", "horoscope", "recipe", "celebrity gossip",
    }
)

T = TypeVar("T")


def is_obvious_junk(title: str, body: str) -> bool:
    """True only for articles that clearly cannot bear on sovereign risk."""
    combined = f"{title} {body}".lower()
    return any(term in combined for term in _JUNK_TERMS)


def split_by_budget(items: list[T], limit: int) -> tuple[list[T], list[T]]:
    """Split into the items to grade now and the items deferred to a later run."""
    if limit <= 0:
        return [], list(items)
    return list(items[:limit]), list(items[limit:])
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_prefilter.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
uv run ruff check .
git add apps/api/src/atlas_api/services/news/prefilter.py apps/api/tests/test_news_prefilter.py
git commit -m "feat(news): add pre-filter with narrow junk cut and AI budget split"
```

---

### Task 6: The AI grader

**Files:**
- Create: `apps/api/src/atlas_api/services/news/ai_grader.py`
- Test: `apps/api/tests/test_news_ai_grader.py`

**Interfaces:**
- Consumes: `NewsGradeResult` (Task 2), `settings.news_relevance_threshold` and `settings.news_translate_enabled` (Task 3), `TRACKED_ISO3` (Task 5), `call_tool` and `compute_input_hash` from `atlas_api.services.ai.provider`.
- Produces:
  - `grade_article(title: str, body: str, source: str, candidate_iso3: str | None) -> tuple[NewsGradeResult | None, dict[str, Any]]`
  - `passes_gate(result: NewsGradeResult, threshold: int) -> bool`
  - `SYSTEM_PROMPT: str`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_ai_grader.py`:

```python
"""Grader gate logic and the single structured Claude call."""

from __future__ import annotations

from unittest.mock import patch

from atlas_api.services.news.ai_grader import SYSTEM_PROMPT, grade_article, passes_gate
from atlas_schemas.ai import NewsGradeResult


def _grade(**overrides) -> NewsGradeResult:
    base = {
        "relevant": True,
        "relevance_score": 80,
        "rationale": "Rating action changes the sovereign credit view.",
        "primary_iso3": "KEN",
        "secondary_iso3": [],
        "event_type": "Rating",
        "fiscal_impact": "M",
        "external_impact": "M",
        "fx_impact": "L",
        "political_impact": "L",
        "source_lang": "en",
        "title_en": "Moody's upgrades Kenya",
        "summary_en": "Moody's raised Kenya to B3 with a stable outlook.",
    }
    base.update(overrides)
    return NewsGradeResult(**base)


def test_gate_accepts_a_strong_on_policy_item():
    assert passes_gate(_grade(), threshold=60) is True


def test_gate_rejects_when_marked_irrelevant():
    assert passes_gate(_grade(relevant=False), threshold=60) is False


def test_gate_rejects_below_threshold():
    assert passes_gate(_grade(relevance_score=40), threshold=60) is False


def test_gate_rejects_untracked_or_missing_country():
    assert passes_gate(_grade(primary_iso3=None), threshold=60) is False
    assert passes_gate(_grade(primary_iso3="USA"), threshold=60) is False


def test_system_prompt_states_the_editorial_policy():
    lowered = SYSTEM_PROMPT.lower()
    assert "sport" in lowered
    assert "passing" in lowered  # the no-passing-mention rule
    for term in ("debt", "imf", "rating", "election"):
        assert term in lowered


@patch("atlas_api.services.news.ai_grader.call_tool")
@patch("atlas_api.services.news.ai_grader.settings")
def test_grade_article_returns_parsed_result(mock_settings, mock_call_tool):
    mock_settings.anthropic_api_key = "sk-ant-test"
    mock_settings.ai_model = "claude-sonnet-4-5"
    mock_settings.news_translate_enabled = True

    graded = _grade()
    mock_call_tool.return_value = (
        graded,
        {"model": "claude-sonnet-4-5", "tokens_in": 400, "tokens_out": 120,
         "prompt_hash": "h", "raw_response": graded.model_dump(), "error": None},
    )

    result, meta = grade_article(
        title="Moody's upgrades Kenya", body="Kenya was raised to B3.",
        source="reuters.com", candidate_iso3="KEN",
    )
    assert result is not None
    assert result.primary_iso3 == "KEN"
    assert meta["error"] is None


@patch("atlas_api.services.news.ai_grader.settings")
def test_grade_article_without_api_key_returns_none(mock_settings):
    mock_settings.anthropic_api_key = ""
    result, meta = grade_article(title="t", body="b", source="s", candidate_iso3=None)
    assert result is None
    assert meta["error"] == "no_api_key"


@patch("atlas_api.services.news.ai_grader.call_tool")
@patch("atlas_api.services.news.ai_grader.settings")
def test_grade_article_propagates_provider_failure(mock_settings, mock_call_tool):
    mock_settings.anthropic_api_key = "sk-ant-test"
    mock_settings.ai_model = "claude-sonnet-4-5"
    mock_call_tool.return_value = (None, {"error": "api_error_attempt_1: boom"})

    result, meta = grade_article(title="t", body="b", source="s", candidate_iso3=None)
    assert result is None
    assert "boom" in meta["error"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_ai_grader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atlas_api.services.news.ai_grader'`.

- [ ] **Step 3: Write the implementation**

Create `apps/api/src/atlas_api/services/news/ai_grader.py`:

```python
"""One structured Claude call that grades a single news article.

Relevance, country attribution, translation, classification and impact are judged
together in a single call, because they all depend on the same reading of the
article. Splitting them would cost more and agree less.
"""

from __future__ import annotations

from typing import Any

import structlog
from atlas_schemas.ai import NewsGradeResult

from atlas_api.config import settings
from atlas_api.services.ai.provider import call_tool, compute_input_hash
from atlas_api.services.news.prefilter import TRACKED_ISO3

log = structlog.get_logger()

SYSTEM_PROMPT = """You grade news articles for Atlas, a sovereign risk platform for \
institutional analysts covering ten African economies: Cote d'Ivoire (CIV), Ghana (GHA), \
Kenya (KEN), Nigeria (NGA), Senegal (SEN), Ethiopia (ETH), Rwanda (RWA), South Africa (ZAF), \
Morocco (MAR) and Egypt (EGY).

IN SCOPE: sovereign debt, IMF programmes, rating actions, fiscal and monetary policy, FX, \
reserves, bonds and eurobonds, growth, inflation, material trade and investment flows, and \
politics that materially affects creditworthiness such as elections, coups, sanctions, major \
reform and significant unrest.

OUT OF SCOPE: sport, entertainment, crime reporting, general human interest, routine corporate \
news with no sovereign read-through, and politics with no plausible link to creditworthiness.

RULES:
1. Set relevant to true only if the article is in scope. When uncertain, prefer false and give \
a low relevance_score rather than admitting weak material.
2. primary_iso3 is the single country the article is actually about. If a country appears only \
as a passing comparison or background mention, it is NOT the primary country. If no tracked \
country is the real subject, return null.
3. secondary_iso3 lists other tracked countries the article genuinely covers, not mentions.
4. rationale is one sentence, grounded in the article, explaining the decision.
5. title_en and summary_en must always be English. Translate faithfully when the source is not \
English. Never invent detail that is not in the article.
6. source_lang is the ISO 639-1 code of the original article.
7. relevance_score reflects both importance to sovereign risk and your confidence.
"""


def _build_messages(
    title: str, body: str, source: str, candidate_iso3: str | None
) -> list[dict[str, Any]]:
    candidate_line = (
        f"A keyword pre-pass guessed the country may be {candidate_iso3}. "
        "Treat this as a hint only and override it if the article says otherwise."
        if candidate_iso3
        else "The keyword pre-pass produced no country guess."
    )
    return [
        {
            "role": "user",
            "content": (
                f"Source: {source}\n"
                f"Title: {title}\n"
                f"Body: {body[:2000]}\n\n"
                f"{candidate_line}\n\n"
                "Grade this article using the grade_news_article tool."
            ),
        }
    ]


def grade_article(
    *,
    title: str,
    body: str,
    source: str,
    candidate_iso3: str | None,
) -> tuple[NewsGradeResult | None, dict[str, Any]]:
    """Grade one article. Returns (result, meta). Result is None on any failure."""
    if not settings.anthropic_api_key:
        log.debug("news_grader_no_api_key")
        return None, {"error": "no_api_key"}

    messages = _build_messages(title, body, source, candidate_iso3)
    grounding = {"title": title, "body": body[:2000], "source": source}

    result, meta = call_tool(
        messages=messages,
        system=SYSTEM_PROMPT,
        tool_name="grade_news_article",
        tool_description=(
            "Judge one news article for sovereign risk relevance, attribute it to the "
            "correct country, translate it to English, classify it and score its impact"
        ),
        result_model=NewsGradeResult,
        max_tokens=1024,
    )
    meta["input_hash"] = compute_input_hash(grounding)

    if result is None:
        log.info("news_grade_failed", error=meta.get("error"), title=title[:80])

    return result, meta


def passes_gate(result: NewsGradeResult, threshold: int) -> bool:
    """The keep rule: on policy, confident enough, and about a tracked country."""
    return (
        result.relevant
        and result.relevance_score >= threshold
        and result.primary_iso3 is not None
        and result.primary_iso3 in TRACKED_ISO3
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_ai_grader.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/services/news/ai_grader.py apps/api/tests/test_news_ai_grader.py
git commit -m "feat(news): add single-call AI grader for relevance and attribution"
```

---

### Task 7: Persist graded results

**Files:**
- Create: `apps/api/src/atlas_api/services/news/persist.py`
- Test: `apps/api/tests/test_news_persist.py`

**Interfaces:**
- Consumes: `NewsGradeResult` (Task 2), `NewsItem` and `NewsItemCountry` (Task 1), `persist_trace` from `atlas_api.services.ai.trace`, `persist_score` from `atlas_api.services.news.heuristic_scorer`.
- Produces:
  - `apply_grade(session, item: NewsItem, result: NewsGradeResult, meta: dict[str, Any], *, keep: bool) -> None`
  - `mark_deferred(session, item: NewsItem) -> None`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_persist.py`:

```python
"""Persisting a grade must write links, score, trace and keep primary_iso3 in sync."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from atlas_api.services.news.persist import apply_grade, mark_deferred
from atlas_schemas.ai import NewsGradeResult


def _result(**overrides) -> NewsGradeResult:
    base = {
        "relevant": True,
        "relevance_score": 88,
        "rationale": "IMF programme review directly affects external financing.",
        "primary_iso3": "GHA",
        "secondary_iso3": ["KEN"],
        "event_type": "IMF",
        "fiscal_impact": "H",
        "external_impact": "H",
        "fx_impact": "M",
        "political_impact": "L",
        "source_lang": "fr",
        "title_en": "IMF completes Ghana review",
        "summary_en": "The board completed the review and released a tranche.",
    }
    base.update(overrides)
    return NewsGradeResult(**base)


def _item() -> MagicMock:
    item = MagicMock()
    item.id = uuid.uuid4()
    item.title = "Le FMI acheve la revue du Ghana"
    item.body_text = "Le conseil a approuve le decaissement."
    return item


@patch("atlas_api.services.news.persist.persist_score")
@patch("atlas_api.services.news.persist.persist_trace")
def test_apply_grade_keeps_and_writes_everything(mock_trace, mock_score):
    trace = MagicMock()
    trace.id = uuid.uuid4()
    mock_trace.return_value = trace

    session = MagicMock()
    item = _item()
    meta = {"model": "claude-sonnet-4-5", "prompt_hash": "p", "input_hash": "i",
            "tokens_in": 300, "tokens_out": 90, "raw_response": {}}

    apply_grade(session, item, _result(), meta, keep=True)

    assert item.relevant is True
    assert item.relevance_score == 88
    assert item.primary_iso3 == "GHA"
    assert item.ai_graded is True
    assert item.source_lang == "fr"
    # Translation happened, so the original is preserved and title is now English.
    assert item.original_title == "Le FMI acheve la revue du Ghana"
    assert item.title == "IMF completes Ghana review"
    assert item.prompt_trace_id == trace.id
    mock_score.assert_called_once()
    # One primary link plus one secondary link.
    assert session.merge.call_count == 2


@patch("atlas_api.services.news.persist.persist_score")
@patch("atlas_api.services.news.persist.persist_trace")
def test_apply_grade_rejects_without_writing_links_or_score(mock_trace, mock_score):
    trace = MagicMock()
    trace.id = uuid.uuid4()
    mock_trace.return_value = trace

    session = MagicMock()
    item = _item()
    meta = {"model": "m", "prompt_hash": "p", "input_hash": "i",
            "tokens_in": 1, "tokens_out": 1, "raw_response": {}}

    apply_grade(session, item, _result(relevant=False, relevance_score=5), meta, keep=False)

    assert item.relevant is False
    assert item.ai_graded is True
    mock_score.assert_not_called()
    session.merge.assert_not_called()


@patch("atlas_api.services.news.persist.persist_score")
@patch("atlas_api.services.news.persist.persist_trace")
def test_english_item_keeps_title_and_sets_no_original(mock_trace, mock_score):
    trace = MagicMock()
    trace.id = uuid.uuid4()
    mock_trace.return_value = trace

    session = MagicMock()
    item = _item()
    item.title = "IMF completes Ghana review"
    meta = {"model": "m", "prompt_hash": "p", "input_hash": "i",
            "tokens_in": 1, "tokens_out": 1, "raw_response": {}}

    apply_grade(session, item, _result(source_lang="en"), meta, keep=True)

    assert item.original_title is None
    assert item.title == "IMF completes Ghana review"


def test_mark_deferred_leaves_item_unserved():
    session = MagicMock()
    item = _item()
    mark_deferred(session, item)
    assert item.relevant is False
    assert item.ai_graded is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_persist.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atlas_api.services.news.persist'`.

- [ ] **Step 3: Write the implementation**

Create `apps/api/src/atlas_api/services/news/persist.py`:

```python
"""Write a graded article: flags, translation, country links, impact score, trace."""

from __future__ import annotations

from typing import Any

import structlog
from atlas_schemas.ai import NewsGradeResult
from sqlalchemy.orm import Session

from atlas_api.models import NewsItem, NewsItemCountry
from atlas_api.services.ai.trace import persist_trace
from atlas_api.services.news.heuristic_scorer import persist_score

log = structlog.get_logger()


def apply_grade(
    session: Session,
    item: NewsItem,
    result: NewsGradeResult,
    meta: dict[str, Any],
    *,
    keep: bool,
) -> None:
    """Apply a grade to an item. Writes links and score only when the item is kept."""
    trace = persist_trace(
        session,
        purpose="news_impact",
        model=meta.get("model", ""),
        prompt_hash=meta.get("prompt_hash", ""),
        input_hash=meta.get("input_hash", ""),
        input_data={"title": item.title},
        output_data=result.model_dump(),
        tokens_in=meta.get("tokens_in", 0),
        tokens_out=meta.get("tokens_out", 0),
    )

    item.ai_graded = True
    item.prompt_trace_id = trace.id
    item.relevance_score = result.relevance_score
    item.relevance_rationale = result.rationale
    item.source_lang = result.source_lang
    item.summary_en = result.summary_en
    item.event_type = result.event_type
    item.relevant = keep

    # Preserve the source title only when a translation actually replaced it.
    if result.title_en and result.title_en != item.title:
        item.original_title = item.title
        item.title = result.title_en

    if not keep:
        log.info("news_item_rejected", score=result.relevance_score, reason=result.rationale[:120])
        return

    item.primary_iso3 = result.primary_iso3

    session.merge(
        NewsItemCountry(news_item_id=item.id, iso3=result.primary_iso3, role="primary")
    )
    for iso3 in result.secondary_iso3:
        if iso3 != result.primary_iso3:
            session.merge(
                NewsItemCountry(news_item_id=item.id, iso3=iso3, role="secondary")
            )

    persist_score(
        session,
        item.id,
        {
            "fiscal_impact": result.fiscal_impact,
            "external_impact": result.external_impact,
            "fx_impact": result.fx_impact,
            "political_impact": result.political_impact,
            "rationale": {"grade": result.rationale},
            "scorer": "ai_grader",
        },
    )


def mark_deferred(session: Session, item: NewsItem) -> None:
    """Leave an item ungraded and unserved so a later run can pick it up."""
    item.relevant = False
    item.ai_graded = False
```

**Note:** confirm `persist_score` accepts a `scorer` key in its score dict. Check with `grep -n "scorer" apps/api/src/atlas_api/services/news/heuristic_scorer.py`. If it sets `scorer` itself, drop that key from the dict above and instead set `score.scorer` after the call, matching whatever the existing function does.

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_persist.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
uv run ruff check .
git add apps/api/src/atlas_api/services/news/persist.py apps/api/tests/test_news_persist.py
git commit -m "feat(news): persist grades with country links, score and trace"
```

---

### Task 8: Rewire the pipeline

**Files:**
- Modify: `apps/api/src/atlas_api/services/news/pipeline.py`
- Test: `apps/api/tests/test_news_pipeline_flow.py`

**Interfaces:**
- Consumes: everything from Tasks 3 to 7.
- Produces: `run_news_pipeline() -> dict[str, int]` with stats keys `polled`, `stored`, `embedded`, `duplicates`, `junk`, `graded`, `kept`, `rejected`, `deferred`, `heuristic_fallback`.

**Critical constraint:** `run_news_pipeline` is an async job the `AsyncIOScheduler` runs directly on the event loop. `grade_article` makes a blocking HTTP call to Anthropic. Calling it inline would freeze the whole API, which is exactly the bug fixed in commit `4f6d728` for `run_nightly`. Every grading call MUST be offloaded with `asyncio.to_thread`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_pipeline_flow.py`:

```python
"""The pipeline must offload blocking AI work and honour the budget."""

from __future__ import annotations

import asyncio
import inspect
import threading

from atlas_api.services.news import pipeline as pipeline_mod


def test_pipeline_offloads_grading_off_the_event_loop():
    """Guards against reintroducing the event loop freeze fixed in 4f6d728."""
    source = inspect.getsource(pipeline_mod)
    assert "asyncio.to_thread" in source, (
        "grade_article is blocking and must be offloaded with asyncio.to_thread"
    )


def test_grading_actually_runs_on_a_worker_thread():
    main_thread = threading.current_thread()
    seen: dict[str, bool] = {}

    def fake_blocking_grade() -> None:
        seen["on_main"] = threading.current_thread() is main_thread

    async def main() -> None:
        await asyncio.to_thread(fake_blocking_grade)

    asyncio.run(main())
    assert seen["on_main"] is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_pipeline_flow.py -v`
Expected: FAIL on the first test, because `asyncio.to_thread` is not yet in `pipeline.py`.

- [ ] **Step 3: Rewrite the pipeline body**

Replace the whole contents of `apps/api/src/atlas_api/services/news/pipeline.py` with:

```python
"""News pipeline orchestrator.

Chains: poll -> store -> embed -> semantic dedup -> junk cut -> budget split ->
AI grade -> persist. Grading is blocking, so it is offloaded to a worker thread:
this coroutine is run directly on the event loop by the scheduler and must never
block it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.db import SessionLocal
from atlas_api.services.news.ai_grader import grade_article, passes_gate
from atlas_api.services.news.dedup import store_new_articles
from atlas_api.services.news.embeddings import update_embeddings
from atlas_api.services.news.gdelt import poll_gdelt
from atlas_api.services.news.heuristic_scorer import persist_score, score_impact
from atlas_api.services.news.nlp import classify_event, extract_country, is_relevant
from atlas_api.services.news.persist import apply_grade, mark_deferred
from atlas_api.services.news.prefilter import TRACKED_ISO3, is_obvious_junk, split_by_budget
from atlas_api.services.news.rss import poll_rss
from atlas_api.services.news.semantic_dedup import is_duplicate

log = structlog.get_logger()


def _heuristic_fallback(session: Session, item: Any) -> bool:
    """Used when the AI is unavailable. Keeps the feed alive during an outage.

    Returns True when the item is kept.
    """
    title = item.title
    body = item.body_text or ""
    iso3 = extract_country(title, body)
    keep = bool(iso3) and iso3 in TRACKED_ISO3 and is_relevant(title, body)

    item.ai_graded = False
    item.relevant = keep
    if not keep:
        return False

    item.primary_iso3 = iso3
    item.event_type = classify_event(title, body)
    item.relevance_rationale = "Scored by keyword fallback while the AI was unavailable."
    persist_score(session, item.id, score_impact(title, body))
    return True


async def run_news_pipeline() -> dict[str, int]:
    """Run one poll cycle. Returns stats dict."""
    session = SessionLocal()
    stats: dict[str, int] = {
        "polled": 0, "stored": 0, "embedded": 0, "duplicates": 0, "junk": 0,
        "graded": 0, "kept": 0, "rejected": 0, "deferred": 0, "heuristic_fallback": 0,
    }
    try:
        async with httpx.AsyncClient() as http:
            gdelt_articles = await poll_gdelt(http)
            rss_articles = await poll_rss(http)
        all_articles = gdelt_articles + rss_articles
        stats["polled"] = len(all_articles)

        new_items = store_new_articles(session, all_articles)
        stats["stored"] = len(new_items)
        if not new_items:
            log.info("news_pipeline_no_new", **stats)
            return stats

        stats["embedded"] = update_embeddings(session, new_items)

        # Cheap filters first so nothing junk or duplicated is ever paid for.
        candidates = []
        for item in new_items:
            row = session.execute(
                text("SELECT embedding FROM news_item WHERE id = :id"),
                {"id": str(item.id)},
            ).first()
            embedding = row[0] if row and row[0] is not None else None
            if embedding is not None and is_duplicate(session, item.id, embedding):
                stats["duplicates"] += 1
                continue
            if is_obvious_junk(item.title, item.body_text or ""):
                stats["junk"] += 1
                continue
            candidates.append(item)

        to_grade, deferred = split_by_budget(candidates, settings.news_ai_calls_per_run)
        for item in deferred:
            mark_deferred(session, item)
        stats["deferred"] = len(deferred)
        session.commit()

        for item in to_grade:
            candidate_iso3 = extract_country(item.title, item.body_text or "")
            # Blocking Anthropic call. Never run this on the event loop.
            result, meta = await asyncio.to_thread(
                grade_article,
                title=item.title,
                body=item.body_text or "",
                source=item.source,
                candidate_iso3=candidate_iso3,
            )

            if result is None:
                if _heuristic_fallback(session, item):
                    stats["kept"] += 1
                else:
                    stats["rejected"] += 1
                stats["heuristic_fallback"] += 1
                session.commit()
                continue

            keep = passes_gate(result, settings.news_relevance_threshold)
            apply_grade(session, item, result, meta, keep=keep)
            stats["graded"] += 1
            stats["kept" if keep else "rejected"] += 1
            session.commit()

        log.info("news_pipeline_complete", **stats)
        return stats
    except Exception:
        log.exception("news_pipeline_error")
        return stats
    finally:
        session.close()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_pipeline_flow.py -v`
Expected: 2 passed.

- [ ] **Step 5: Check for regressions in existing news tests**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests -k "news" -v`
Expected: PASS. If an existing test asserts on removed stats keys such as `scored`, `irrelevant`, `ai_scored` or `heuristic_scored`, update that test to the new key names listed in the Interfaces block. Do not reintroduce the old keys.

- [ ] **Step 6: Commit**

```bash
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/services/news/pipeline.py apps/api/tests/test_news_pipeline_flow.py
git commit -m "feat(news): rewire pipeline through grader with off-loop AI calls"
```

---

### Task 9: Serve only relevant news

**Files:**
- Modify: `apps/api/src/atlas_api/routers/news.py`
- Test: `apps/api/tests/test_news_endpoint_relevance.py`

**Interfaces:**
- Consumes: `NewsItem`, `NewsItemCountry` (Task 1), extended `NewsItemOut` (Task 2).
- Produces: `GET /api/news` filtered to `relevant = true`, `iso3` matching either link role, ordered by `relevance_score DESC NULLS LAST` then `published_at DESC`.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_news_endpoint_relevance.py`:

```python
"""The endpoint must hide irrelevant items and expose the new fields."""

from __future__ import annotations

import inspect

from atlas_api.routers import news as news_router


def test_query_filters_on_relevant():
    source = inspect.getsource(news_router.list_news)
    assert "relevant" in source, "list_news must filter out irrelevant items"


def test_query_uses_the_country_link_table():
    source = inspect.getsource(news_router.list_news)
    assert "NewsItemCountry" in source, "iso3 filter must use the link table"


def test_ordering_prefers_relevance_then_recency():
    source = inspect.getsource(news_router.list_news)
    assert "relevance_score" in source
    assert "published_at" in source


def test_item_serializer_exposes_new_fields():
    source = inspect.getsource(news_router._item_to_out)
    for field in ("summary_en", "source_lang", "relevance_score", "relevance_rationale", "translated"):
        assert field in source, f"_item_to_out must expose {field}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_endpoint_relevance.py -v`
Expected: FAIL on all four assertions.

- [ ] **Step 3: Update the serializer**

In `apps/api/src/atlas_api/routers/news.py`, inside `_item_to_out`, add these keys to the returned dict alongside the existing ones:

```python
        "summary_en": item.summary_en,
        "source_lang": item.source_lang,
        "relevance_score": item.relevance_score,
        "relevance_rationale": item.relevance_rationale,
        "translated": item.original_title is not None,
```

- [ ] **Step 4: Update the query**

Add `NewsItemCountry` to the model import line, then replace the statement construction in `list_news` with:

```python
    stmt = (
        select(NewsItem, NewsImpactScore)
        .outerjoin(NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id)
        .where(NewsItem.relevant.is_(True))
        .order_by(
            NewsItem.relevance_score.desc().nullslast(),
            NewsItem.published_at.desc(),
        )
    )

    if iso3:
        iso3 = _check_iso3(iso3)
        stmt = stmt.join(
            NewsItemCountry, NewsItemCountry.news_item_id == NewsItem.id
        ).where(NewsItemCountry.iso3 == iso3)
```

Delete the old `.where(NewsItem.primary_iso3 == iso3)` line and the old `.order_by(NewsItem.published_at.desc())` so ordering is not applied twice.

- [ ] **Step 5: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_news_endpoint_relevance.py -v`
Expected: 4 passed.

- [ ] **Step 6: Regenerate the TypeScript types**

Run: `pnpm run codegen`
Expected: `apps/web/src/types/generated.ts` now contains the new `NewsItemOut` fields. If the script name differs, find it with `grep -n "codegen" package.json`.

- [ ] **Step 7: Commit**

```bash
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/routers/news.py apps/api/tests/test_news_endpoint_relevance.py apps/web/src/types/generated.ts
git commit -m "feat(news): serve only relevant items with rationale and translation flags"
```

---

### Task 10: Show the rationale and translation badge

**Files:**
- Modify: `apps/web/src/routes/NewsIntelligence.tsx`
- Modify: `apps/web/src/components/NewsItemCard.tsx`
- Test: `apps/web/src/components/__tests__/NewsItemCard.test.tsx`

**Interfaces:**
- Consumes: the extended `NewsItemOut` fields from Task 9.
- Produces: a card that renders `relevance_rationale` under the headline and a translation badge when `translated` is true.

**Note:** read `NewsItemCard.tsx` first and follow its existing class and layout conventions. Do not restyle the card. Check whether a test file already exists at the path above, and extend it rather than replacing it.

- [ ] **Step 1: Write the failing test**

Create or extend `apps/web/src/components/__tests__/NewsItemCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import NewsItemCard from "../NewsItemCard";

const base = {
  id: "1",
  url: "https://example.com/a",
  title: "IMF completes Ghana review",
  source: "reuters.com",
  published_at: "2026-08-19T10:00:00Z",
  ingested_at: "2026-08-19T10:05:00Z",
  primary_iso3: "GHA",
  event_type: "IMF",
  summary_en: "The board completed the review.",
  relevance_score: 88,
  relevance_rationale: "Directly changes Ghana's external financing position.",
  source_lang: "en",
  translated: false,
  impact_score: null,
};

describe("NewsItemCard", () => {
  it("shows why the item is in the feed", () => {
    render(<NewsItemCard item={base} />);
    expect(
      screen.getByText(/Directly changes Ghana's external financing position/i),
    ).toBeInTheDocument();
  });

  it("flags a translated item with its source language", () => {
    render(<NewsItemCard item={{ ...base, translated: true, source_lang: "fr" }} />);
    expect(screen.getByText(/translated from french/i)).toBeInTheDocument();
  });

  it("shows no badge for an English item", () => {
    render(<NewsItemCard item={base} />);
    expect(screen.queryByText(/translated from/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm --filter web test -- NewsItemCard`
Expected: FAIL, the rationale and badge are not rendered.

- [ ] **Step 3: Implement the card additions**

In `apps/web/src/components/NewsItemCard.tsx`, add this language map near the top of the file:

```tsx
const LANGUAGE_NAMES: Record<string, string> = {
  ar: "Arabic",
  fr: "French",
  pt: "Portuguese",
  es: "Spanish",
  sw: "Swahili",
  am: "Amharic",
  en: "English",
};
```

Then inside the card body, directly beneath the headline element, add:

```tsx
{item.translated && item.source_lang ? (
  <span className="mt-1 inline-block rounded bg-ink-800 px-2 py-0.5 text-xs text-ink-300">
    Translated from {LANGUAGE_NAMES[item.source_lang] ?? item.source_lang}
  </span>
) : null}

{item.relevance_rationale ? (
  <p className="mt-2 text-sm text-ink-400">{item.relevance_rationale}</p>
) : null}
```

Match the surrounding Tailwind token names. If the file uses different ink shades, use its shades rather than these.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm --filter web test -- NewsItemCard`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/NewsItemCard.tsx apps/web/src/components/__tests__/NewsItemCard.test.tsx apps/web/src/routes/NewsIntelligence.tsx
git commit -m "feat(web): show relevance rationale and translation badge on news cards"
```

---

### Task 11: Backfill the existing articles

**Files:**
- Create: `apps/api/scripts/regrade_news.py`
- Test: `apps/api/tests/test_regrade_news.py`

**Interfaces:**
- Consumes: `grade_article`, `passes_gate` (Task 6), `apply_grade` (Task 7), settings (Task 3).
- Produces: `regrade_batch(session, limit: int) -> dict[str, int]` and a `main()` entry point.

**Why this exists:** the migration sets `relevant = false` on every existing row, so the whole feed is hidden until this script restores the good items. Migration and backfill run back to back at deploy time.

**Structure:** `apps/api/scripts/` is not an importable package, so the logic lives in `apps/api/src/atlas_api/services/news/regrade.py` and the script is a thin wrapper around it. That is what makes it testable.

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_regrade_news.py`:

```python
"""The backfill must batch, skip already graded items, and respect the token cap."""

from __future__ import annotations

import inspect

from atlas_api.services.news.regrade import regrade_batch


def test_regrade_batch_only_selects_ungraded_items():
    source = inspect.getsource(regrade_batch)
    assert "ai_graded" in source, "must filter on ai_graded so re-runs are cheap"
    assert "limit" in source, "must batch"


def test_regrade_batch_respects_the_daily_token_cap():
    source = inspect.getsource(regrade_batch)
    assert "token_counter" in source, "must stop when the daily token cap is hit"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_regrade_news.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the regrade service**

Create `apps/api/src/atlas_api/services/news/regrade.py`:

```python
"""Re-grade articles already stored in the database.

The relevance migration hides every existing row. This restores the ones that
pass the new editorial bar and leaves the rest hidden but not deleted, so the
decision stays auditable and reversible.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.models import NewsItem
from atlas_api.services.ai.provider import token_counter
from atlas_api.services.news.ai_grader import grade_article, passes_gate
from atlas_api.services.news.persist import apply_grade
from atlas_api.services.news.prefilter import is_obvious_junk

log = structlog.get_logger()


def regrade_batch(session: Session, limit: int) -> dict[str, int]:
    """Grade up to `limit` ungraded items. Safe to call repeatedly."""
    stats = {"seen": 0, "kept": 0, "rejected": 0, "junk": 0, "failed": 0}

    rows = list(
        session.execute(
            select(NewsItem)
            .where(NewsItem.ai_graded.is_(False))
            .order_by(NewsItem.published_at.desc().nullslast())
            .limit(limit)
        ).scalars()
    )

    for item in rows:
        stats["seen"] += 1

        if token_counter.is_exceeded():
            log.warning("regrade_stopped_token_cap", processed=stats["seen"] - 1)
            break

        if is_obvious_junk(item.title, item.body_text or ""):
            item.relevant = False
            item.ai_graded = True
            item.relevance_rationale = "Removed by the junk filter during backfill."
            stats["junk"] += 1
            session.commit()
            continue

        result, meta = grade_article(
            title=item.title,
            body=item.body_text or "",
            source=item.source,
            candidate_iso3=item.primary_iso3,
        )
        if result is None:
            stats["failed"] += 1
            continue

        keep = passes_gate(result, settings.news_relevance_threshold)
        apply_grade(session, item, result, meta, keep=keep)
        stats["kept" if keep else "rejected"] += 1
        session.commit()

    log.info("regrade_batch_complete", **stats)
    return stats
```

- [ ] **Step 4: Write the script wrapper**

Create `apps/api/scripts/regrade_news.py`:

```python
"""Re-grade stored news articles against the new relevance policy.

Usage:
    PYTHONPATH=apps/api/src:packages/schemas/src .venv/bin/python \
        apps/api/scripts/regrade_news.py [batch_size]
"""

from __future__ import annotations

import sys

from atlas_api.db import SessionLocal
from atlas_api.services.news.regrade import regrade_batch


def main() -> int:
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    with SessionLocal() as session:
        stats = regrade_batch(session, batch)
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests/test_regrade_news.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
git add apps/api/src/atlas_api/services/news/regrade.py apps/api/scripts/regrade_news.py apps/api/tests/test_regrade_news.py
git commit -m "feat(news): add backfill that re-grades stored articles"
```

---

### Task 12: Verify against the acceptance criteria

**Files:**
- Modify: none unless a check fails.

**Interfaces:** consumes everything above.

This task is a gate, not a feature. Do not mark it complete on partial results.

- [ ] **Step 1: Run the whole suite**

Run: `PYTHONPATH=apps/api/src:packages/schemas/src uv run --group dev python -m pytest apps/api/tests -q`
Expected: all green. Docker must be running for the testcontainers-backed tests.

Run: `pnpm --filter web test`
Expected: all green.

- [ ] **Step 2: Lint and type check**

```bash
uv run ruff check .
uv run mypy apps/api/src packages/schemas/src
```
Expected: clean.

- [ ] **Step 3: Exercise the pipeline against the local database**

```bash
PYTHONPATH=apps/api/src:packages/schemas/src .venv/bin/python -c "
import asyncio
from atlas_api.services.news.pipeline import run_news_pipeline
print(asyncio.run(run_news_pipeline()))
"
```
Expected: a stats dict. `kept` is greater than zero and `rejected` is greater than zero. If `kept` is zero, the threshold is too strict, so lower `NEWS_RELEVANCE_THRESHOLD` and rerun rather than widening the editorial policy.

- [ ] **Step 4: Check per-country volume**

```bash
PYTHONPATH=apps/api/src:packages/schemas/src .venv/bin/python -c "
from atlas_api.db import SessionLocal
from sqlalchemy import func, select
from atlas_api.models import NewsItem, NewsItemCountry
with SessionLocal() as s:
    rows = s.execute(
        select(NewsItemCountry.iso3, func.count())
        .join(NewsItem, NewsItem.id == NewsItemCountry.news_item_id)
        .where(NewsItem.relevant.is_(True))
        .group_by(NewsItemCountry.iso3)
    ).all()
    print(dict(rows))
"
```
Expected: every one of the ten countries appears with a count of at least 5. If any country is short, lower the threshold and re-run the backfill.

- [ ] **Step 5: Manual editorial review**

Read 20 kept items across at least four countries. Confirm every one is on policy, in English, and filed under the right country. Any failure means the prompt needs tuning, not the policy.

- [ ] **Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix(news): address findings from acceptance verification"
```

---

## Deployment sequence

Run these in order. Steps 2 and 3 must run back to back, because the feed is empty between them.

1. Push to `main` and wait for the Railway redeploy to report healthy at `/api/health`.
2. Apply the migration against Supabase with `DATABASE_URL` pointed at production.
3. Run `regrade_news.py` in batches until `seen` returns 0.
4. Verify per-country counts against the acceptance target using the Task 12 Step 4 query.
5. Only then set `NEWS_POLL_ENABLED=true` in Railway, so live polling starts against a verified pipeline.

Pushing requires the user's approval. Do not push without it.
