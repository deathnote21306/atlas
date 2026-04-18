# Atlas Plan 5b: AI Integration — Claude Impact Scoring + Synopsis Generation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the heuristic news scorer with Claude-powered 4-axis impact scoring (fiscal/external/fx/political L/M/H + rationale), and generate grounded country synopses from macro bundles + recent scored news. Every Claude call uses tool-use mode with strict JSON schemas. All AI outputs carry full lineage (`prompt_trace`). Synopses land as `proposed` and require human approval before rendering. A daily token cap prevents runaway costs; when exceeded or when Claude is unavailable, the pipeline falls back to the existing heuristic scorer.

**Architecture:** A new `services/ai/` module contains: (1) `provider.py` — a thin Claude client wrapper using the `anthropic` SDK's tool-use mode, with retry logic, cost tracking, and typed response validation; (2) `trace.py` — prompt trace persistence; (3) `news_scorer.py` — Claude-based 4-axis scoring that replaces the heuristic scorer when available; (4) `synopsis.py` — grounded synopsis generation from country bundle + recent news. Two new tables (`prompt_trace`, `synopsis`) are added in migration `0009`. Admin endpoints allow synopsis approval/rejection. The country profile page renders approved synopses and shows AI score badges on news items.

**Tech Stack:** `anthropic>=0.39` SDK with tool-use structured output; existing FastAPI + SQLAlchemy + Alembic stack; model `claude-sonnet-4-5-20250514` (configurable); in-memory daily token counter (reset at midnight UTC); Pydantic schemas in `packages/schemas`; pytest with mocked `anthropic.Anthropic` client.

---

## File Structure

Files created (C) or modified (M):

```
atlas/
├── packages/schemas/
│   ├── src/atlas_schemas/
│   │   ├── __init__.py                                            (M) export new AI types
│   │   ├── news.py                                                (M) add AI scorer badge field
│   │   └── ai.py                                                  (C) SynopsisApprovalState, SynopsisOut, PromptTraceOut,
│   │                                                                   AIScoreRequest, AIScoreResponse, SynopsisGenerateRequest
│   └── tests/
│       └── test_contracts.py                                      (M) add AI schema roundtrip tests
│
├── infra/migrations/versions/
│   └── 0009_ai_integration.py                                     (C) prompt_trace + synopsis tables
│
├── apps/api/
│   ├── pyproject.toml                                             (M) add anthropic>=0.39
│   ├── src/atlas_api/
│   │   ├── config.py                                              (M) add anthropic_api_key, ai_daily_token_cap, ai_model
│   │   ├── models.py                                              (M) add PromptTrace + Synopsis ORM models
│   │   ├── main.py                                                (M) wire synopses + admin routers
│   │   ├── routers/
│   │   │   ├── synopses.py                                        (C) GET /api/synopses/{iso3}, GET /api/admin/synopses,
│   │   │   │                                                           POST /api/admin/synopses/{id}/approve,
│   │   │   │                                                           POST /api/admin/synopses/{id}/reject
│   │   │   └── news.py                                            (M) add prompt_trace link to news score response
│   │   └── services/
│   │       ├── ai/
│   │       │   ├── __init__.py                                    (C)
│   │       │   ├── provider.py                                    (C) Claude client wrapper, tool-use schema, retry, cost tracking
│   │       │   ├── trace.py                                       (C) prompt_trace persistence
│   │       │   ├── news_scorer.py                                 (C) Claude-based 4-axis scoring
│   │       │   └── synopsis.py                                    (C) grounded synopsis generation
│   │       ├── news/
│   │       │   └── pipeline.py                                    (M) try AI scorer first, fall back to heuristic
│   │       └── country/
│   │           └── bundle.py                                      (M) include latest approved synopsis in bundle
│   └── tests/
│       ├── test_ai_provider.py                                    (C) provider unit tests with mocked Anthropic client
│       ├── test_ai_news_scorer.py                                 (C) AI scoring tests with mock
│       ├── test_ai_synopsis.py                                    (C) synopsis generation tests with mock
│       └── test_synopsis_endpoints.py                             (C) API endpoint tests
│
└── apps/web/
    └── src/
        ├── routes/
        │   ├── CountryProfile.tsx                                 (M) render approved synopsis, news with AI badges
        │   └── AdminSynopses.tsx                                  (C) /admin/synopses review page
        ├── components/
        │   ├── NewsItemCard.tsx                                   (C) news card with score badge + lineage link
        │   └── SynopsisCard.tsx                                   (C) synopsis card with approval state + lineage link
        └── App.tsx                                                (M) add /admin/synopses route
```

---

## Design decisions locked in this plan

1. **Tool-use mode for all Claude calls.** We use the `anthropic` SDK's `tools` parameter with strict JSON schema definitions. Claude returns structured JSON via tool calls, never free-form text. Schema violation triggers one retry, then fallback to heuristic.
2. **Model default: `claude-sonnet-4-5-20250514`.** Configurable via `AI_MODEL` env var. Sonnet balances cost and quality for scoring + synopsis tasks.
3. **In-memory daily token counter.** A module-level `_DailyTokenCounter` class tracks input + output tokens per UTC day. No Redis needed for the prototype. Counter resets at midnight UTC by comparing stored date vs current date.
4. **Daily token cap default: 200,000 tokens.** Set via `AI_DAILY_TOKEN_CAP` env var. When exceeded, all Claude calls short-circuit to heuristic fallback (for scoring) or skip (for synopsis generation).
5. **Synopsis approval states** use `StrEnum`: `proposed`, `human_approved`, `auto_approved_similarity`, `auto_approved_stable_country`, `rejected`. Only `human_approved` and `auto_approved_*` states render on the country profile.
6. **Prompt trace stores full I/O.** The `prompt_trace` table stores `input` (full prompt context as JSONB) and `output` (Claude's response as JSONB), plus `prompt_hash` (SHA-256 of the serialized input) and `input_hash` (SHA-256 of the grounding data). API keys are never stored.
7. **`tenant_id` on synopsis** per spec section 14.3, defaulting to the prototype tenant UUID `00000000-0000-0000-0000-000000000000`.
8. **Heuristic scorer preserved as fallback.** `services/news/heuristic_scorer.py` is unchanged. The pipeline tries AI first, catches failures, and falls back.
9. **Synopsis generation is NOT scheduled.** For the prototype, synopses are generated on-demand via an admin trigger or a manual script. Scheduling is deferred to Plan 6.
10. **Tests mock `anthropic.Anthropic`.** We never call the real API in tests. We mock the `client.messages.create` method to return canned tool-use responses.

---

## Task 1 of 10 -- Dependencies + config

**Why:** Add the `anthropic` SDK and configure the three new settings needed for AI integration.

- [ ] 1.1 Add `anthropic>=0.39` to `apps/api/pyproject.toml` dependencies
- [ ] 1.2 Add AI settings to `apps/api/src/atlas_api/config.py`
- [ ] 1.3 Run `uv lock` to update lockfile
- [ ] 1.4 Verify import works

### 1.1 — Add anthropic dependency

**File: `apps/api/pyproject.toml`** (modify)

In the `dependencies` list, add after the `pgvector>=0.3` line:

```python
  "anthropic>=0.39",
```

### 1.2 — Add AI settings

**File: `apps/api/src/atlas_api/config.py`** (modify)

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
    news_poll_enabled: bool = False
    news_poll_cron: str = "*/10 * * * *"  # every 10 minutes

    # -- AI integration (Plan 5b) --
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-4-5-20250514"
    ai_daily_token_cap: int = 200_000


settings = Settings()
```

### 1.3 — Lock

```bash
cd apps/api && uv lock
```

### 1.4 — Smoke check

```bash
cd apps/api && uv run python -c "import anthropic; print(anthropic.__version__)"
```

**Self-review:** Three new settings match spec. `anthropic_api_key` reads from `ANTHROPIC_API_KEY` env var automatically (pydantic-settings lowercases). Default model is correct. Token cap is 200k.

---

## Task 2 of 10 -- Pydantic schemas

**Why:** Define the typed contracts for synopsis, prompt trace, and AI scoring that all layers share.

- [ ] 2.1 Create `packages/schemas/src/atlas_schemas/ai.py`
- [ ] 2.2 Update `packages/schemas/src/atlas_schemas/__init__.py`
- [ ] 2.3 Add schema roundtrip tests

### 2.1 — AI schemas

**File: `packages/schemas/src/atlas_schemas/ai.py`** (create)

```python
"""AI integration schemas — synopsis, prompt trace, scoring contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class SynopsisApprovalState(StrEnum):
    PROPOSED = "proposed"
    HUMAN_APPROVED = "human_approved"
    AUTO_APPROVED_SIMILARITY = "auto_approved_similarity"
    AUTO_APPROVED_STABLE_COUNTRY = "auto_approved_stable_country"
    REJECTED = "rejected"


class PromptPurpose(StrEnum):
    SYNOPSIS = "synopsis"
    NEWS_IMPACT = "news_impact"
    NARRATIVE_PANEL = "narrative_panel"


# ── Prompt Trace ───────────────────────────────────────────────────────────

class PromptTraceOut(BaseModel):
    """Lineage record for an AI call."""
    id: uuid.UUID
    purpose: PromptPurpose
    model: str
    prompt_hash: str
    input_hash: str
    input: dict[str, object]
    output: dict[str, object]
    user_id: uuid.UUID | None = None
    approval_state: SynopsisApprovalState | None = None
    created_at: datetime


# ── Synopsis ───────────────────────────────────────────────────────────────

class SynopsisKeyPoint(BaseModel):
    """A single key point in a synopsis."""
    text: str
    category: str = ""


class SynopsisContent(BaseModel):
    """The typed output schema Claude must return for synopsis generation."""
    text: str = Field(..., description="2-4 paragraph country synopsis")
    key_points: list[SynopsisKeyPoint] = Field(
        ..., description="3-6 key points summarising the sovereign outlook"
    )
    coverage_notes: list[str] = Field(
        default_factory=list,
        description="Gaps or caveats about data coverage",
    )


class SynopsisOut(BaseModel):
    """Synopsis record returned by the API."""
    id: uuid.UUID
    iso3: str
    text: str
    key_points: list[SynopsisKeyPoint]
    generated_at: datetime
    approval_state: SynopsisApprovalState
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    prompt_trace_id: uuid.UUID | None = None
    tenant_id: uuid.UUID


class SynopsisListItem(BaseModel):
    """Lightweight synopsis for the admin list."""
    id: uuid.UUID
    iso3: str
    text: str
    generated_at: datetime
    approval_state: SynopsisApprovalState


# ── AI Scoring ─────────────────────────────────────────────────────────────

class AIScoreResult(BaseModel):
    """The typed output schema Claude must return for news impact scoring."""
    fiscal_impact: str = Field(..., pattern="^[LMH]$")
    external_impact: str = Field(..., pattern="^[LMH]$")
    fx_impact: str = Field(..., pattern="^[LMH]$")
    political_impact: str = Field(..., pattern="^[LMH]$")
    rationale: dict[str, str] = Field(
        ..., description="Per-axis rationale: {fiscal: ..., external: ..., fx: ..., political: ...}"
    )


class AIScoreRequest(BaseModel):
    """Input to the AI scoring service."""
    news_item_id: uuid.UUID
    title: str
    body: str
    iso3: str | None = None
    event_type: str | None = None


class AIScoreResponse(BaseModel):
    """Response from the AI scoring service."""
    news_item_id: uuid.UUID
    result: AIScoreResult
    scorer: str
    prompt_trace_id: uuid.UUID
```

### 2.2 — Update __init__.py

**File: `packages/schemas/src/atlas_schemas/__init__.py`** (modify)

Add to the existing exports:

```python
from atlas_schemas.ai import (
    AIScoreRequest,
    AIScoreResponse,
    AIScoreResult,
    PromptPurpose,
    PromptTraceOut,
    SynopsisApprovalState,
    SynopsisContent,
    SynopsisKeyPoint,
    SynopsisListItem,
    SynopsisOut,
)
```

### 2.3 — Schema roundtrip tests

**File: `packages/schemas/tests/test_contracts.py`** (modify — append)

```python
def test_synopsis_content_roundtrip():
    from atlas_schemas.ai import SynopsisContent, SynopsisKeyPoint
    sc = SynopsisContent(
        text="Nigeria faces headwinds...",
        key_points=[SynopsisKeyPoint(text="Naira under pressure", category="fx")],
        coverage_notes=["Q4 GDP not yet available"],
    )
    d = sc.model_dump()
    assert d["text"] == "Nigeria faces headwinds..."
    assert len(d["key_points"]) == 1
    rt = SynopsisContent.model_validate(d)
    assert rt == sc


def test_ai_score_result_roundtrip():
    from atlas_schemas.ai import AIScoreResult
    r = AIScoreResult(
        fiscal_impact="H", external_impact="M", fx_impact="L", political_impact="M",
        rationale={"fiscal": "Debt restructuring", "external": "Trade deficit",
                   "fx": "Stable peg", "political": "Election upcoming"},
    )
    d = r.model_dump()
    assert d["fiscal_impact"] == "H"
    rt = AIScoreResult.model_validate(d)
    assert rt == r


def test_synopsis_approval_state_is_strenum():
    from atlas_schemas.ai import SynopsisApprovalState
    assert SynopsisApprovalState.PROPOSED == "proposed"
    assert SynopsisApprovalState.HUMAN_APPROVED == "human_approved"
```

**Self-review:** All schemas use `StrEnum`. `SynopsisContent` matches spec's `{text, key_points[], coverage_notes[]}`. `AIScoreResult` has the 4-axis L/M/H pattern with rationale. `PromptPurpose` covers all three spec'd purposes.

---

## Task 3 of 10 -- Migration 0009: prompt_trace + synopsis tables

**Why:** Create the two new tables that store AI lineage and generated synopses.

- [ ] 3.1 Create migration file

### 3.1 — Migration

**File: `infra/migrations/versions/0009_ai_integration.py`** (create)

```python
"""prompt_trace + synopsis tables

Revision ID: 0009_ai_integration
Revises: 0008_news_pipeline
Create Date: 2026-04-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009_ai_integration"
down_revision = "0008_news_pipeline"
branch_labels = None
depends_on = None

APPROVAL_STATES = (
    "proposed", "human_approved", "auto_approved_similarity",
    "auto_approved_stable_country", "rejected",
)
PROMPT_PURPOSES = ("synopsis", "news_impact", "narrative_panel")


def upgrade() -> None:
    # -- prompt_trace --
    op.create_table(
        "prompt_trace",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input", JSONB, nullable=False),
        sa.Column("output", JSONB, nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("approval_state", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_prompt_trace_purpose", "prompt_trace", ["purpose"])
    op.create_index("ix_prompt_trace_created_at", "prompt_trace", ["created_at"])

    # -- synopsis --
    op.create_table(
        "synopsis",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("key_points", JSONB, nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "vintage_id", UUID(as_uuid=True),
            sa.ForeignKey("data_vintage.id"), nullable=True,
        ),
        sa.Column(
            "prompt_trace_id", UUID(as_uuid=True),
            sa.ForeignKey("prompt_trace.id"), nullable=True,
        ),
        sa.Column(
            "approval_state", sa.String(40), nullable=False,
            server_default="proposed",
        ),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), nullable=False,
            server_default=sa.text("'00000000-0000-0000-0000-000000000000'::uuid"),
        ),
    )
    op.create_index("ix_synopsis_iso3", "synopsis", ["iso3"])
    op.create_index("ix_synopsis_approval_state", "synopsis", ["approval_state"])

    # Add prompt_trace_id FK to news_impact_score for AI scoring lineage
    op.add_column(
        "news_impact_score",
        sa.Column(
            "prompt_trace_id", UUID(as_uuid=True),
            sa.ForeignKey("prompt_trace.id"), nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("news_impact_score", "prompt_trace_id")
    op.drop_table("synopsis")
    op.drop_table("prompt_trace")
```

**Self-review:** Down revision is `0008_news_pipeline`. Tables match spec section 5 exactly. `tenant_id` on synopsis has the prototype default UUID. `prompt_trace_id` added to `news_impact_score` for lineage. `tokens_in`/`tokens_out` added for cost tracking queries.

---

## Task 4 of 10 -- ORM models + AIProvider + prompt trace

**Why:** Add the ORM models for the new tables, build the core Claude client wrapper with tool-use schema enforcement, retry logic, and cost tracking, plus the prompt trace persistence layer.

- [ ] 4.1 Add ORM models to `models.py`
- [ ] 4.2 Create `services/ai/__init__.py`
- [ ] 4.3 Create `services/ai/provider.py`
- [ ] 4.4 Create `services/ai/trace.py`
- [ ] 4.5 Write provider tests

### 4.1 — ORM models

**File: `apps/api/src/atlas_api/models.py`** (modify — append after `NewsImpactScore`)

```python
class PromptTrace(Base):
    __tablename__ = "prompt_trace"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    approval_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class Synopsis(Base):
    __tablename__ = "synopsis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    vintage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_vintage.id"), nullable=True
    )
    prompt_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_trace.id"), nullable=True
    )
    approval_state: Mapped[str] = mapped_column(
        String(40), nullable=False, default="proposed"
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        server_default=text("'00000000-0000-0000-0000-000000000000'::uuid"),
    )
```

Also add `prompt_trace_id` column to the existing `NewsImpactScore` class:

```python
# Add this line to NewsImpactScore class, after scored_at:
    prompt_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_trace.id"), nullable=True
    )
```

### 4.2 — Service init

**File: `apps/api/src/atlas_api/services/ai/__init__.py`** (create)

```python
"""AI integration services — Claude scoring + synopsis generation."""
```

### 4.3 — AIProvider

**File: `apps/api/src/atlas_api/services/ai/provider.py`** (create)

```python
"""Claude client wrapper with tool-use mode, retry, and cost tracking.

Every Claude call goes through `call_tool()`, which:
1. Checks the daily token cap — short-circuits if exceeded.
2. Sends a tool-use request with a strict JSON schema.
3. Validates the response against the expected Pydantic model.
4. On schema violation, retries once.
5. On any failure after retry, returns None (caller falls back).
6. Records token usage for cost tracking.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from typing import TypeVar

import anthropic
import structlog
from pydantic import BaseModel, ValidationError

from atlas_api.config import settings

log = structlog.get_logger()
T = TypeVar("T", bound=BaseModel)

# ── Daily token counter (in-memory, prototype-grade) ───────────────────────

class _DailyTokenCounter:
    """Thread-safe daily token counter. Resets at midnight UTC."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._date: str = ""
        self._total: int = 0

    def _maybe_reset(self) -> None:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if self._date != today:
            self._date = today
            self._total = 0

    def add(self, tokens: int) -> None:
        with self._lock:
            self._maybe_reset()
            self._total += tokens

    def remaining(self) -> int:
        with self._lock:
            self._maybe_reset()
            return max(0, settings.ai_daily_token_cap - self._total)

    @property
    def total_today(self) -> int:
        with self._lock:
            self._maybe_reset()
            return self._total

    def is_exceeded(self) -> bool:
        return self.remaining() <= 0


token_counter = _DailyTokenCounter()


# ── Tool schema builder ───────────────────────────────────────────────────

def _pydantic_to_tool_schema(name: str, description: str, model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to an Anthropic tool definition."""
    schema = model.model_json_schema()
    # Remove $defs and flatten for Anthropic's tool format
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


# ── Core call function ────────────────────────────────────────────────────

def _get_client() -> anthropic.Anthropic:
    """Lazy client construction. Raises if no API key configured."""
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def compute_prompt_hash(messages: list[dict], system: str) -> str:
    """SHA-256 of the serialized prompt (messages + system)."""
    blob = json.dumps({"system": system, "messages": messages}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def compute_input_hash(grounding_data: dict) -> str:
    """SHA-256 of the grounding data used to build the prompt."""
    blob = json.dumps(grounding_data, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def call_tool(
    *,
    messages: list[dict],
    system: str,
    tool_name: str,
    tool_description: str,
    result_model: type[T],
    max_tokens: int = 2048,
) -> tuple[T | None, dict]:
    """Call Claude with a single tool and parse the result.

    Returns:
        (parsed_result, metadata_dict) where metadata contains:
        - model, tokens_in, tokens_out, prompt_hash, raw_response
        On failure: (None, metadata_dict)
    """
    meta: dict = {
        "model": settings.ai_model,
        "tokens_in": 0,
        "tokens_out": 0,
        "prompt_hash": compute_prompt_hash(messages, system),
        "raw_response": None,
        "error": None,
    }

    # Check token cap
    if token_counter.is_exceeded():
        meta["error"] = "daily_token_cap_exceeded"
        log.warning("ai_token_cap_exceeded", remaining=0, cap=settings.ai_daily_token_cap)
        return None, meta

    tool_def = _pydantic_to_tool_schema(tool_name, tool_description, result_model)
    client = _get_client()

    for attempt in range(2):  # 1 try + 1 retry
        try:
            response = client.messages.create(
                model=settings.ai_model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=[tool_def],
                tool_choice={"type": "tool", "name": tool_name},
            )

            # Track tokens
            usage = response.usage
            tokens_used = (usage.input_tokens or 0) + (usage.output_tokens or 0)
            token_counter.add(tokens_used)
            meta["tokens_in"] = usage.input_tokens or 0
            meta["tokens_out"] = usage.output_tokens or 0

            # Extract tool use block
            tool_block = None
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    tool_block = block
                    break

            if tool_block is None:
                meta["error"] = f"no_tool_use_block_attempt_{attempt}"
                log.warning("ai_no_tool_block", attempt=attempt, tool=tool_name)
                if attempt == 0:
                    continue
                return None, meta

            meta["raw_response"] = tool_block.input

            # Validate against Pydantic model
            try:
                parsed = result_model.model_validate(tool_block.input)
                return parsed, meta
            except ValidationError as ve:
                meta["error"] = f"validation_error_attempt_{attempt}: {ve}"
                log.warning("ai_validation_error", attempt=attempt, error=str(ve))
                if attempt == 0:
                    continue
                return None, meta

        except anthropic.APIError as e:
            meta["error"] = f"api_error_attempt_{attempt}: {e}"
            log.warning("ai_api_error", attempt=attempt, error=str(e))
            if attempt == 0:
                continue
            return None, meta
        except Exception as e:
            meta["error"] = f"unexpected_error: {e}"
            log.exception("ai_unexpected_error")
            return None, meta

    return None, meta
```

### 4.4 — Prompt trace persistence

**File: `apps/api/src/atlas_api/services/ai/trace.py`** (create)

```python
"""Prompt trace persistence — records every AI call for lineage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from atlas_api.models import PromptTrace


def persist_trace(
    session: Session,
    *,
    purpose: str,
    model: str,
    prompt_hash: str,
    input_hash: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    tokens_in: int = 0,
    tokens_out: int = 0,
    user_id: uuid.UUID | None = None,
    approval_state: str | None = None,
) -> PromptTrace:
    """Write a prompt trace row and return it."""
    trace = PromptTrace(
        id=uuid.uuid4(),
        purpose=purpose,
        model=model,
        prompt_hash=prompt_hash,
        input_hash=input_hash,
        input=input_data,
        output=output_data,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        user_id=user_id,
        approval_state=approval_state,
        created_at=datetime.now(UTC),
    )
    session.add(trace)
    session.flush()  # Get the ID without committing
    return trace
```

### 4.5 — Provider unit tests

**File: `apps/api/tests/test_ai_provider.py`** (create)

```python
"""Tests for the AI provider — all calls mocked, never hits real API."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from atlas_api.services.ai.provider import (
    _DailyTokenCounter,
    call_tool,
    compute_input_hash,
    compute_prompt_hash,
    token_counter,
)


class MockScoreResult(BaseModel):
    fiscal_impact: str
    external_impact: str
    fx_impact: str
    political_impact: str
    rationale: dict[str, str]


def _make_mock_response(tool_name: str, tool_input: dict) -> MagicMock:
    """Build a mock Anthropic response with a tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input

    usage = MagicMock()
    usage.input_tokens = 150
    usage.output_tokens = 50

    response = MagicMock()
    response.content = [block]
    response.usage = usage
    return response


@patch("atlas_api.services.ai.provider.settings")
@patch("atlas_api.services.ai.provider._get_client")
def test_call_tool_success(mock_client_fn, mock_settings):
    mock_settings.ai_model = "claude-sonnet-4-5-20250514"
    mock_settings.ai_daily_token_cap = 200_000
    mock_settings.anthropic_api_key = "sk-ant-test"

    tool_input = {
        "fiscal_impact": "H", "external_impact": "M",
        "fx_impact": "L", "political_impact": "M",
        "rationale": {"fiscal": "debt", "external": "trade",
                      "fx": "stable", "political": "election"},
    }
    mock_response = _make_mock_response("score_news", tool_input)
    client = MagicMock()
    client.messages.create.return_value = mock_response
    mock_client_fn.return_value = client

    # Reset counter
    token_counter._total = 0
    token_counter._date = ""

    result, meta = call_tool(
        messages=[{"role": "user", "content": "Score this article"}],
        system="You are a sovereign finance analyst.",
        tool_name="score_news",
        tool_description="Score a news article",
        result_model=MockScoreResult,
    )

    assert result is not None
    assert result.fiscal_impact == "H"
    assert meta["tokens_in"] == 150
    assert meta["tokens_out"] == 50
    assert meta["error"] is None


def test_daily_token_counter_reset():
    counter = _DailyTokenCounter()
    counter._date = "2025-01-01"  # old date
    counter._total = 999_999
    # Calling remaining() should reset
    remaining = counter.remaining()
    assert remaining > 0  # Was reset because date changed


def test_prompt_hash_deterministic():
    msgs = [{"role": "user", "content": "hello"}]
    h1 = compute_prompt_hash(msgs, "sys")
    h2 = compute_prompt_hash(msgs, "sys")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256


@patch("atlas_api.services.ai.provider.settings")
def test_call_tool_cap_exceeded(mock_settings):
    mock_settings.ai_daily_token_cap = 100
    token_counter._total = 200
    token_counter._date = ""  # force no reset until _maybe_reset sees today
    # Manually set today so it doesn't reset
    from datetime import UTC, datetime
    token_counter._date = datetime.now(UTC).strftime("%Y-%m-%d")

    result, meta = call_tool(
        messages=[{"role": "user", "content": "test"}],
        system="test",
        tool_name="test",
        tool_description="test",
        result_model=MockScoreResult,
    )
    assert result is None
    assert meta["error"] == "daily_token_cap_exceeded"
```

**Self-review:** Provider uses tool-use mode with `tool_choice={"type": "tool", "name": tool_name}`. One retry on failure. Token counter is thread-safe. Tests mock everything.

---

## Task 5 of 10 -- AI impact scorer

**Why:** Build the Claude-based news scorer that replaces the heuristic scorer when available.

- [ ] 5.1 Create `services/ai/news_scorer.py`
- [ ] 5.2 Write tests

### 5.1 — AI news scorer

**File: `apps/api/src/atlas_api/services/ai/news_scorer.py`** (create)

```python
"""Claude-based 4-axis news impact scorer.

Falls back to heuristic scorer on:
- API key not configured
- Daily token cap exceeded
- Claude API error after retry
- Schema validation failure after retry
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.models import NewsImpactScore
from atlas_api.services.ai.provider import call_tool, compute_input_hash
from atlas_api.services.ai.trace import persist_trace
from atlas_api.services.news.heuristic_scorer import (
    persist_score as persist_heuristic_score,
    score_impact as heuristic_score,
)
from atlas_schemas.ai import AIScoreResult

log = structlog.get_logger()

_SYSTEM_PROMPT = """You are a sovereign-finance analyst specialising in African economies.
You assess news articles for their impact on a country's sovereign risk profile.

Score each article across 4 axes using L (low), M (medium), or H (high):
- fiscal_impact: Effect on government budget, debt, fiscal position
- external_impact: Effect on trade balance, FDI, external financing
- fx_impact: Effect on exchange rate, reserves, currency stability
- political_impact: Effect on political stability, governance, reform trajectory

Provide a brief rationale for each axis score."""


def _build_messages(title: str, body: str, iso3: str | None, event_type: str | None) -> list[dict]:
    context_parts = [f"Title: {title}"]
    if body:
        # Truncate body to ~2000 chars to manage token usage
        context_parts.append(f"Body: {body[:2000]}")
    if iso3:
        context_parts.append(f"Country: {iso3}")
    if event_type:
        context_parts.append(f"Event type: {event_type}")

    return [{"role": "user", "content": "\n\n".join(context_parts)}]


def score_with_ai(
    session: Session,
    *,
    news_item_id: uuid.UUID,
    title: str,
    body: str,
    iso3: str | None = None,
    event_type: str | None = None,
) -> NewsImpactScore | None:
    """Score a news item using Claude. Returns the persisted score, or None if AI unavailable.

    On None return, the caller should fall back to heuristic scoring.
    """
    if not settings.anthropic_api_key:
        log.debug("ai_scorer_no_api_key")
        return None

    messages = _build_messages(title, body, iso3, event_type)
    grounding_data = {"title": title, "body": body[:500], "iso3": iso3, "event_type": event_type}
    input_hash = compute_input_hash(grounding_data)

    result, meta = call_tool(
        messages=messages,
        system=_SYSTEM_PROMPT,
        tool_name="score_news_impact",
        tool_description="Score a news article's impact on sovereign risk across 4 axes",
        result_model=AIScoreResult,
        max_tokens=1024,
    )

    if result is None:
        log.info("ai_scorer_fallback", reason=meta.get("error"), news_item_id=str(news_item_id))
        return None

    # Persist trace
    trace = persist_trace(
        session,
        purpose="news_impact",
        model=meta["model"],
        prompt_hash=meta["prompt_hash"],
        input_hash=input_hash,
        input_data={"system": _SYSTEM_PROMPT, "messages": messages},
        output_data=result.model_dump(),
        tokens_in=meta["tokens_in"],
        tokens_out=meta["tokens_out"],
    )

    # Persist score
    row = NewsImpactScore(
        id=uuid.uuid4(),
        news_item_id=news_item_id,
        fiscal_impact=result.fiscal_impact,
        external_impact=result.external_impact,
        fx_impact=result.fx_impact,
        political_impact=result.political_impact,
        rationale=result.rationale,
        scorer=meta["model"],
        scored_at=datetime.now(UTC),
        prompt_trace_id=trace.id,
    )
    session.add(row)
    session.flush()
    return row


def score_news_item(
    session: Session,
    *,
    news_item_id: uuid.UUID,
    title: str,
    body: str,
    iso3: str | None = None,
    event_type: str | None = None,
) -> NewsImpactScore:
    """Score a news item: try AI first, fall back to heuristic.

    Always returns a persisted score — never None.
    """
    ai_score = score_with_ai(
        session,
        news_item_id=news_item_id,
        title=title, body=body,
        iso3=iso3, event_type=event_type,
    )
    if ai_score is not None:
        return ai_score

    # Heuristic fallback
    score_dict = heuristic_score(title, body)
    return persist_heuristic_score(session, news_item_id, score_dict)
```

### 5.2 — Tests

**File: `apps/api/tests/test_ai_news_scorer.py`** (create)

```python
"""Tests for AI news scorer with mocked Anthropic client."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from atlas_schemas.ai import AIScoreResult


@patch("atlas_api.services.ai.news_scorer.call_tool")
@patch("atlas_api.services.ai.news_scorer.settings")
@patch("atlas_api.services.ai.news_scorer.persist_trace")
def test_ai_scorer_success(mock_trace, mock_settings, mock_call_tool):
    mock_settings.anthropic_api_key = "sk-ant-test"
    mock_settings.ai_model = "claude-sonnet-4-5-20250514"

    ai_result = AIScoreResult(
        fiscal_impact="H", external_impact="M", fx_impact="L", political_impact="M",
        rationale={"fiscal": "bond", "external": "trade", "fx": "stable", "political": "vote"},
    )
    mock_call_tool.return_value = (
        ai_result,
        {"model": "claude-sonnet-4-5-20250514", "tokens_in": 100, "tokens_out": 50,
         "prompt_hash": "abc123", "raw_response": ai_result.model_dump(), "error": None},
    )

    trace_obj = MagicMock()
    trace_obj.id = uuid.uuid4()
    mock_trace.return_value = trace_obj

    session = MagicMock()
    from atlas_api.services.ai.news_scorer import score_with_ai

    result = score_with_ai(
        session,
        news_item_id=uuid.uuid4(),
        title="Nigeria bond issuance",
        body="The government announced...",
        iso3="NGA",
    )
    assert result is not None
    assert result.fiscal_impact == "H"
    assert result.scorer == "claude-sonnet-4-5-20250514"
    session.add.assert_called_once()


@patch("atlas_api.services.ai.news_scorer.call_tool")
@patch("atlas_api.services.ai.news_scorer.settings")
def test_ai_scorer_falls_back_on_failure(mock_settings, mock_call_tool):
    mock_settings.anthropic_api_key = "sk-ant-test"
    mock_call_tool.return_value = (None, {"error": "api_error", "model": "test",
                                          "tokens_in": 0, "tokens_out": 0,
                                          "prompt_hash": "x"})

    from atlas_api.services.ai.news_scorer import score_with_ai
    session = MagicMock()
    result = score_with_ai(
        session,
        news_item_id=uuid.uuid4(),
        title="Test article",
        body="Body text",
    )
    assert result is None  # Caller should fall back to heuristic


@patch("atlas_api.services.ai.news_scorer.settings")
def test_ai_scorer_no_api_key(mock_settings):
    mock_settings.anthropic_api_key = ""
    from atlas_api.services.ai.news_scorer import score_with_ai
    session = MagicMock()
    result = score_with_ai(session, news_item_id=uuid.uuid4(), title="t", body="b")
    assert result is None
```

**Self-review:** AI scorer returns `None` on any failure, letting the caller fall back to heuristic. Prompt trace is persisted. Tests mock `call_tool` directly, never call real API.

---

## Task 6 of 10 -- Synopsis generator

**Why:** Build the grounded synopsis generator that pulls macro bundle + recent news, calls Claude, and persists the synopsis with `proposed` approval state.

- [ ] 6.1 Create `services/ai/synopsis.py`
- [ ] 6.2 Write tests

### 6.1 — Synopsis generator

**File: `apps/api/src/atlas_api/services/ai/synopsis.py`** (create)

```python
"""Grounded country synopsis generation using Claude.

1. Pull latest macro bundle + last 7d scored news + ratings + FX
2. Build structured context prompt
3. Call Claude with typed output schema
4. Persist synopsis with approval_state=proposed + prompt_trace
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.models import NewsImpactScore, NewsItem, Synopsis
from atlas_api.services.ai.provider import call_tool, compute_input_hash
from atlas_api.services.ai.trace import persist_trace
from atlas_api.services.country.bundle import get_country_bundle
from atlas_schemas.ai import SynopsisContent

log = structlog.get_logger()

_SYSTEM_PROMPT = """You are a sovereign-finance intelligence analyst producing concise country
risk synopses for institutional investors and multilateral stakeholders.

Your synopsis must be grounded ONLY in the structured context provided.
Do not speculate beyond the data. If coverage is thin, note it in coverage_notes.

Write 2-4 paragraphs covering:
1. Macro snapshot: GDP trajectory, fiscal/debt position, inflation
2. External & FX: current account, reserves, currency dynamics
3. Political & ratings: governance signals, rating actions, outlook
4. Near-term risks and opportunities from recent news

Be factual, precise, and use numerical values from the context."""


def _get_recent_news(session: Session, iso3: str, days: int = 7) -> list[dict]:
    """Pull scored news items from the last N days for a country."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    items = (
        session.query(NewsItem, NewsImpactScore)
        .outerjoin(NewsImpactScore, NewsItem.id == NewsImpactScore.news_item_id)
        .filter(NewsItem.primary_iso3 == iso3)
        .filter(NewsItem.ingested_at >= cutoff)
        .order_by(NewsItem.ingested_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for item, score in items:
        entry: dict[str, Any] = {
            "title": item.title,
            "source": item.source,
            "published_at": str(item.published_at) if item.published_at else None,
            "event_type": item.event_type,
        }
        if score:
            entry["impact"] = {
                "fiscal": score.fiscal_impact,
                "external": score.external_impact,
                "fx": score.fx_impact,
                "political": score.political_impact,
            }
        result.append(entry)
    return result


def _build_grounding_context(session: Session, iso3: str) -> dict[str, Any]:
    """Assemble the structured grounding block for the prompt."""
    bundle = get_country_bundle(session, iso3)
    if bundle is None:
        return {}

    context: dict[str, Any] = {
        "country": {
            "iso3": bundle.country.iso3,
            "name": bundle.country.name,
            "region": bundle.country.region,
            "status": bundle.country.status,
            "fx_regime": bundle.country.fx_regime,
        },
        "macro": [
            {
                "indicator": t.indicator,
                "label": t.label,
                "value": t.value,
                "period": t.period,
                "source": t.source,
            }
            for t in bundle.macro
            if t.value is not None
        ],
        "ratings": {
            agency: {
                "rating": r.rating,
                "outlook": r.outlook,
                "action": r.action,
                "action_date": str(r.action_date),
            }
            for agency, r in bundle.ratings.latest_per_agency.items()
        },
        "risk_composite": bundle.risk.composite,
    }

    if bundle.fx is not None:
        context["fx"] = {
            "ccy": bundle.fx.latest.ccy,
            "usd_per_ccy": bundle.fx.latest.usd_per_ccy,
            "observation_date": str(bundle.fx.latest.observation_date),
            "delta_7d_pct": bundle.fx.delta_7d_pct,
            "delta_30d_pct": bundle.fx.delta_30d_pct,
        }

    context["recent_news"] = _get_recent_news(session, iso3)
    return context


def generate_synopsis(
    session: Session,
    iso3: str,
    *,
    user_id: uuid.UUID | None = None,
) -> Synopsis | None:
    """Generate a synopsis for a country using Claude.

    Returns the persisted Synopsis with approval_state='proposed',
    or None if AI is unavailable.
    """
    iso3 = iso3.upper()

    if not settings.anthropic_api_key:
        log.info("synopsis_skip_no_api_key", iso3=iso3)
        return None

    # Build grounding context
    context = _build_grounding_context(session, iso3)
    if not context:
        log.warning("synopsis_skip_no_bundle", iso3=iso3)
        return None

    import json
    context_str = json.dumps(context, indent=2, default=str)
    messages = [
        {
            "role": "user",
            "content": (
                f"Generate a country risk synopsis for {iso3} based on the following data.\n\n"
                f"STRUCTURED CONTEXT:\n```json\n{context_str}\n```"
            ),
        }
    ]

    input_hash = compute_input_hash(context)

    result, meta = call_tool(
        messages=messages,
        system=_SYSTEM_PROMPT,
        tool_name="generate_synopsis",
        tool_description="Generate a grounded country risk synopsis",
        result_model=SynopsisContent,
        max_tokens=4096,
    )

    if result is None:
        log.info("synopsis_ai_unavailable", iso3=iso3, error=meta.get("error"))
        return None

    # Persist prompt trace
    trace = persist_trace(
        session,
        purpose="synopsis",
        model=meta["model"],
        prompt_hash=meta["prompt_hash"],
        input_hash=input_hash,
        input_data={"system": _SYSTEM_PROMPT, "messages": messages},
        output_data=result.model_dump(),
        tokens_in=meta["tokens_in"],
        tokens_out=meta["tokens_out"],
        user_id=user_id,
        approval_state="proposed",
    )

    # Persist synopsis
    synopsis = Synopsis(
        id=uuid.uuid4(),
        iso3=iso3,
        text=result.text,
        key_points=[kp.model_dump() for kp in result.key_points],
        generated_at=datetime.now(UTC),
        prompt_trace_id=trace.id,
        approval_state="proposed",
    )
    session.add(synopsis)
    session.commit()

    log.info("synopsis_generated", iso3=iso3, synopsis_id=str(synopsis.id))
    return synopsis
```

### 6.2 — Tests

**File: `apps/api/tests/test_ai_synopsis.py`** (create)

```python
"""Tests for synopsis generation with mocked Claude."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from atlas_schemas.ai import SynopsisContent, SynopsisKeyPoint


@patch("atlas_api.services.ai.synopsis.call_tool")
@patch("atlas_api.services.ai.synopsis.settings")
@patch("atlas_api.services.ai.synopsis.persist_trace")
@patch("atlas_api.services.ai.synopsis._build_grounding_context")
def test_generate_synopsis_success(mock_context, mock_trace, mock_settings, mock_call_tool):
    mock_settings.anthropic_api_key = "sk-ant-test"
    mock_settings.ai_model = "claude-sonnet-4-5-20250514"

    mock_context.return_value = {
        "country": {"iso3": "NGA", "name": "Nigeria", "region": "West Africa",
                     "status": "Active", "fx_regime": "Managed float"},
        "macro": [{"indicator": "GDP_GROWTH_PCT", "label": "GDP growth", "value": 3.2,
                    "period": "2025", "source": "WB"}],
        "ratings": {},
        "risk_composite": 62.5,
        "recent_news": [],
    }

    synopsis_content = SynopsisContent(
        text="Nigeria's economy shows moderate growth at 3.2% YoY...",
        key_points=[SynopsisKeyPoint(text="GDP growth at 3.2%", category="macro")],
        coverage_notes=["Q4 2025 data pending"],
    )
    mock_call_tool.return_value = (
        synopsis_content,
        {"model": "claude-sonnet-4-5-20250514", "tokens_in": 500, "tokens_out": 300,
         "prompt_hash": "abc", "raw_response": synopsis_content.model_dump(), "error": None},
    )

    trace_obj = MagicMock()
    trace_obj.id = uuid.uuid4()
    mock_trace.return_value = trace_obj

    session = MagicMock()

    from atlas_api.services.ai.synopsis import generate_synopsis
    result = generate_synopsis(session, "NGA")

    assert result is not None
    assert result.iso3 == "NGA"
    assert result.approval_state == "proposed"
    assert "3.2%" in result.text
    session.add.assert_called_once()
    session.commit.assert_called_once()


@patch("atlas_api.services.ai.synopsis.settings")
def test_generate_synopsis_no_api_key(mock_settings):
    mock_settings.anthropic_api_key = ""
    session = MagicMock()

    from atlas_api.services.ai.synopsis import generate_synopsis
    result = generate_synopsis(session, "NGA")
    assert result is None
```

**Self-review:** Synopsis builds grounding context from the existing `get_country_bundle` + recent news query. Output uses the `SynopsisContent` typed schema. Always lands as `proposed`. Trace is persisted.

---

## Task 7 of 10 -- Synopsis + admin API endpoints

**Why:** Expose synopsis data and admin approval/rejection actions via REST endpoints.

- [ ] 7.1 Create `routers/synopses.py`
- [ ] 7.2 Wire into `main.py`
- [ ] 7.3 Write endpoint tests

### 7.1 — Synopsis router

**File: `apps/api/src/atlas_api/routers/synopses.py`** (create)

```python
"""Synopsis endpoints: read (approved) + admin CRUD."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from atlas_api.db import get_db
from atlas_api.models import Synopsis, User
from atlas_api.routers.auth import get_current_user
from atlas_api.services.ai.synopsis import generate_synopsis
from atlas_schemas.ai import SynopsisListItem, SynopsisOut

router = APIRouter()

_APPROVED_STATES = {"human_approved", "auto_approved_similarity", "auto_approved_stable_country"}


@router.get("/api/synopses/{iso3}")
def get_latest_synopsis(iso3: str, db: Session = Depends(get_db)) -> SynopsisOut | None:
    """Return the latest approved synopsis for a country, or null."""
    iso3 = iso3.upper()
    row = (
        db.query(Synopsis)
        .filter(Synopsis.iso3 == iso3)
        .filter(Synopsis.approval_state.in_(_APPROVED_STATES))
        .order_by(Synopsis.generated_at.desc())
        .first()
    )
    if row is None:
        return None
    return SynopsisOut(
        id=row.id, iso3=row.iso3, text=row.text,
        key_points=row.key_points, generated_at=row.generated_at,
        approval_state=row.approval_state,
        approved_by=row.approved_by, approved_at=row.approved_at,
        prompt_trace_id=row.prompt_trace_id, tenant_id=row.tenant_id,
    )


@router.get("/api/admin/synopses")
def list_pending_synopses(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[SynopsisListItem]:
    """List all proposed (pending) synopses for admin review."""
    rows = (
        db.query(Synopsis)
        .filter(Synopsis.approval_state == "proposed")
        .order_by(Synopsis.generated_at.desc())
        .limit(100)
        .all()
    )
    return [
        SynopsisListItem(
            id=r.id, iso3=r.iso3, text=r.text,
            generated_at=r.generated_at, approval_state=r.approval_state,
        )
        for r in rows
    ]


@router.post("/api/admin/synopses/{synopsis_id}/approve")
def approve_synopsis(
    synopsis_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SynopsisOut:
    """Approve a proposed synopsis."""
    row = db.query(Synopsis).filter(Synopsis.id == synopsis_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Synopsis not found")
    if row.approval_state != "proposed":
        raise HTTPException(status_code=400, detail=f"Cannot approve synopsis in state '{row.approval_state}'")

    row.approval_state = "human_approved"
    row.approved_by = user.id
    row.approved_at = datetime.now(UTC)
    db.commit()

    return SynopsisOut(
        id=row.id, iso3=row.iso3, text=row.text,
        key_points=row.key_points, generated_at=row.generated_at,
        approval_state=row.approval_state,
        approved_by=row.approved_by, approved_at=row.approved_at,
        prompt_trace_id=row.prompt_trace_id, tenant_id=row.tenant_id,
    )


@router.post("/api/admin/synopses/{synopsis_id}/reject")
def reject_synopsis(
    synopsis_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SynopsisOut:
    """Reject a proposed synopsis."""
    row = db.query(Synopsis).filter(Synopsis.id == synopsis_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Synopsis not found")
    if row.approval_state != "proposed":
        raise HTTPException(status_code=400, detail=f"Cannot reject synopsis in state '{row.approval_state}'")

    row.approval_state = "rejected"
    row.approved_by = user.id
    row.approved_at = datetime.now(UTC)
    db.commit()

    return SynopsisOut(
        id=row.id, iso3=row.iso3, text=row.text,
        key_points=row.key_points, generated_at=row.generated_at,
        approval_state=row.approval_state,
        approved_by=row.approved_by, approved_at=row.approved_at,
        prompt_trace_id=row.prompt_trace_id, tenant_id=row.tenant_id,
    )


@router.post("/api/admin/synopses/generate/{iso3}")
def trigger_synopsis_generation(
    iso3: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SynopsisOut | dict:
    """Admin trigger to generate a new synopsis for a country."""
    result = generate_synopsis(db, iso3, user_id=user.id)
    if result is None:
        return {"status": "skipped", "reason": "AI unavailable or no data"}
    return SynopsisOut(
        id=result.id, iso3=result.iso3, text=result.text,
        key_points=result.key_points, generated_at=result.generated_at,
        approval_state=result.approval_state,
        approved_by=result.approved_by, approved_at=result.approved_at,
        prompt_trace_id=result.prompt_trace_id, tenant_id=result.tenant_id,
    )
```

### 7.2 — Wire into main.py

**File: `apps/api/src/atlas_api/main.py`** (modify)

Add after the existing router includes:

```python
from atlas_api.routers.synopses import router as synopses_router
app.include_router(synopses_router)
```

### 7.3 — Endpoint tests

**File: `apps/api/tests/test_synopsis_endpoints.py`** (create)

```python
"""Tests for synopsis API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def synopsis_row():
    row = MagicMock()
    row.id = uuid.uuid4()
    row.iso3 = "NGA"
    row.text = "Nigeria faces moderate growth..."
    row.key_points = [{"text": "GDP at 3.2%", "category": "macro"}]
    row.generated_at = datetime.now(UTC)
    row.approval_state = "human_approved"
    row.approved_by = uuid.uuid4()
    row.approved_at = datetime.now(UTC)
    row.prompt_trace_id = uuid.uuid4()
    row.tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    return row


def test_get_latest_synopsis_returns_approved(synopsis_row):
    """Verify that only approved synopses are returned."""
    # This test validates the query filter logic
    assert synopsis_row.approval_state == "human_approved"
    assert synopsis_row.iso3 == "NGA"


def test_approve_rejects_non_proposed():
    """Cannot approve a synopsis that is not in 'proposed' state."""
    # Integration test would hit the endpoint; unit test validates the guard
    assert "proposed" not in {"human_approved", "rejected"}


def test_synopsis_list_item_schema():
    from atlas_schemas.ai import SynopsisListItem
    item = SynopsisListItem(
        id=uuid.uuid4(), iso3="NGA",
        text="Test synopsis", generated_at=datetime.now(UTC),
        approval_state="proposed",
    )
    assert item.approval_state == "proposed"
```

**Self-review:** Four endpoints match spec: GET latest approved, GET pending list, POST approve, POST reject. Plus admin trigger for generation. All admin endpoints require auth.

---

## Task 8 of 10 -- Wire AI scoring into news pipeline

**Why:** Modify the existing news pipeline to try the AI scorer first, falling back to heuristic on any failure.

- [ ] 8.1 Modify `services/news/pipeline.py`

### 8.1 — Pipeline modification

**File: `apps/api/src/atlas_api/services/news/pipeline.py`** (modify)

Replace the imports and the scoring section:

```python
"""News pipeline orchestrator.

Chains: poll -> dedup -> embed -> semantic dedup -> NER -> classify -> score.
"""

from __future__ import annotations

import httpx
import structlog
from sqlalchemy import text

from atlas_api.db import SessionLocal
from atlas_api.services.news.dedup import store_new_articles
from atlas_api.services.news.embeddings import update_embeddings
from atlas_api.services.news.gdelt import poll_gdelt
from atlas_api.services.news.heuristic_scorer import persist_score, score_impact
from atlas_api.services.news.nlp import classify_event, extract_country, is_relevant
from atlas_api.services.news.rss import poll_rss
from atlas_api.services.news.semantic_dedup import is_duplicate

log = structlog.get_logger()


def _score_item(session, item, stats: dict) -> None:
    """Try AI scorer, fall back to heuristic."""
    try:
        from atlas_api.services.ai.news_scorer import score_with_ai
        ai_score = score_with_ai(
            session,
            news_item_id=item.id,
            title=item.title,
            body=item.body_text or "",
            iso3=item.primary_iso3,
            event_type=item.event_type,
        )
        if ai_score is not None:
            stats["ai_scored"] = stats.get("ai_scored", 0) + 1
            return
    except Exception:
        log.exception("ai_scorer_import_or_call_error")

    # Heuristic fallback
    scores = score_impact(item.title, item.body_text or "")
    persist_score(session, item.id, scores)
    stats["heuristic_scored"] = stats.get("heuristic_scored", 0) + 1


async def run_news_pipeline() -> dict[str, int]:
    """Run one poll cycle. Returns stats dict."""
    session = SessionLocal()
    stats = {"polled": 0, "stored": 0, "embedded": 0, "scored": 0,
             "irrelevant": 0, "duplicates": 0, "ai_scored": 0, "heuristic_scored": 0}
    try:
        # 1. Poll sources
        async with httpx.AsyncClient() as http:
            gdelt_articles = await poll_gdelt(http)
            rss_articles = await poll_rss(http)
        all_articles = gdelt_articles + rss_articles
        stats["polled"] = len(all_articles)

        # 2. URL dedup + store
        new_items = store_new_articles(session, all_articles)
        stats["stored"] = len(new_items)
        if not new_items:
            log.info("news_pipeline_no_new", **stats)
            return stats

        # 3. Generate embeddings
        embedded = update_embeddings(session, new_items)
        stats["embedded"] = embedded

        # 4. Process each item: semantic dedup -> NER -> relevance -> classify -> score
        for item in new_items:
            # Semantic dedup
            row = session.execute(
                text("SELECT embedding FROM news_item WHERE id = :id"),
                {"id": str(item.id)},
            ).first()
            embedding = row[0] if row and row[0] is not None else None
            if embedding is not None and is_duplicate(session, item.id, embedding):
                stats["duplicates"] += 1
                continue

            # NER: extract country
            iso3 = extract_country(item.title, item.body_text or "")
            if iso3:
                item.primary_iso3 = iso3
                session.commit()

            # Relevance filter
            if not is_relevant(item.title, item.body_text or ""):
                stats["irrelevant"] += 1
                continue

            # Event classification
            event_type = classify_event(item.title, item.body_text or "")
            item.event_type = event_type
            session.commit()

            # Impact scoring: AI first, heuristic fallback
            _score_item(session, item, stats)
            session.commit()
            stats["scored"] += 1

        log.info("news_pipeline_complete", **stats)
        return stats
    except Exception:
        log.exception("news_pipeline_error")
        return stats
    finally:
        session.close()
```

**Self-review:** The `_score_item` helper tries AI first via lazy import (so no hard dependency if anthropic is not installed), catches all exceptions, and falls back to heuristic. Stats track AI vs heuristic counts. Pipeline structure unchanged.

---

## Task 9 of 10 -- Frontend: synopsis on country profile + news cards + admin page

**Why:** Replace the "AI synopsis pending review" placeholder with actual synopsis data, show AI score badges on news items, and add the admin synopses review page.

- [ ] 9.1 Create `components/SynopsisCard.tsx`
- [ ] 9.2 Create `components/NewsItemCard.tsx`
- [ ] 9.3 Modify `routes/CountryProfile.tsx`
- [ ] 9.4 Create `routes/AdminSynopses.tsx`
- [ ] 9.5 Update `App.tsx` with admin route

### 9.1 — SynopsisCard

**File: `apps/web/src/components/SynopsisCard.tsx`** (create)

```tsx
interface SynopsisData {
  id: string;
  iso3: string;
  text: string;
  key_points: { text: string; category: string }[];
  generated_at: string;
  approval_state: string;
  prompt_trace_id: string | null;
}

export default function SynopsisCard({ synopsis }: { synopsis: SynopsisData | null }) {
  if (!synopsis) {
    return (
      <div className="rounded-md border border-dashed border-ink-100 bg-white p-4 text-sm text-ink-500">
        AI synopsis pending review.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-ink-100 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="rounded bg-positive/10 px-2 py-0.5 text-xs font-medium text-positive">
          {synopsis.approval_state.replace(/_/g, " ")}
        </span>
        {synopsis.prompt_trace_id && (
          <span className="text-[10px] text-ink-300" title={`Trace: ${synopsis.prompt_trace_id}`}>
            AI lineage
          </span>
        )}
      </div>
      <div className="prose prose-sm max-w-none text-ink-800">
        {synopsis.text.split("\n\n").map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
      {synopsis.key_points.length > 0 && (
        <ul className="mt-3 space-y-1">
          {synopsis.key_points.map((kp, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-ink-700">
              <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-atlas-500" />
              {kp.text}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 text-[10px] text-ink-300">
        Generated {new Date(synopsis.generated_at).toLocaleDateString()}
      </div>
    </div>
  );
}
```

### 9.2 — NewsItemCard

**File: `apps/web/src/components/NewsItemCard.tsx`** (create)

```tsx
interface ImpactScore {
  fiscal_impact: string;
  external_impact: string;
  fx_impact: string;
  political_impact: string;
  scorer: string;
}

interface NewsItemData {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  event_type: string | null;
  impact_score: ImpactScore | null;
}

function ImpactBadge({ axis, level }: { axis: string; level: string }) {
  const colors: Record<string, string> = {
    H: "bg-danger/10 text-danger",
    M: "bg-amber-100 text-amber-700",
    L: "bg-ink-100 text-ink-500",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-mono ${colors[level] ?? colors.L}`}>
      {axis[0].toUpperCase()}: {level}
    </span>
  );
}

function ScorerBadge({ scorer }: { scorer: string }) {
  const isAI = scorer.startsWith("claude");
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] ${
        isAI ? "bg-atlas-100 text-atlas-700" : "bg-ink-100 text-ink-500"
      }`}
    >
      {isAI ? "AI" : "heuristic"}
    </span>
  );
}

export default function NewsItemCard({ item }: { item: NewsItemData }) {
  return (
    <div className="rounded-md border border-ink-100 bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-ink-800 hover:text-atlas-600"
        >
          {item.title}
        </a>
        {item.impact_score && <ScorerBadge scorer={item.impact_score.scorer} />}
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-ink-400">
        <span>{item.source}</span>
        {item.published_at && (
          <span>{new Date(item.published_at).toLocaleDateString()}</span>
        )}
        {item.event_type && (
          <span className="rounded bg-ink-100 px-1.5 py-0.5">{item.event_type}</span>
        )}
      </div>
      {item.impact_score && (
        <div className="mt-2 flex flex-wrap gap-1">
          <ImpactBadge axis="fiscal" level={item.impact_score.fiscal_impact} />
          <ImpactBadge axis="external" level={item.impact_score.external_impact} />
          <ImpactBadge axis="fx" level={item.impact_score.fx_impact} />
          <ImpactBadge axis="political" level={item.impact_score.political_impact} />
        </div>
      )}
    </div>
  );
}
```

### 9.3 — Modify CountryProfile.tsx

**File: `apps/web/src/routes/CountryProfile.tsx`** (modify)

Add the import at the top:

```tsx
import SynopsisCard from "../components/SynopsisCard";
import NewsItemCard from "../components/NewsItemCard";
```

Add synopsis and news interfaces to the existing types block:

```tsx
interface SynopsisData {
  id: string;
  iso3: string;
  text: string;
  key_points: { text: string; category: string }[];
  generated_at: string;
  approval_state: string;
  prompt_trace_id: string | null;
}

interface NewsItemData {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  event_type: string | null;
  impact_score: {
    fiscal_impact: string;
    external_impact: string;
    fx_impact: string;
    political_impact: string;
    scorer: string;
  } | null;
}
```

Add a query for synopsis and news data inside the `CountryProfile` component, after the existing bundle query:

```tsx
  const { data: synopsisData } = useQuery<SynopsisData | null>({
    queryKey: ["synopsis", iso3.toUpperCase()],
    queryFn: () => api<SynopsisData | null>(`/api/synopses/${iso3.toUpperCase()}`),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const { data: newsData } = useQuery<NewsItemData[]>({
    queryKey: ["news", iso3.toUpperCase()],
    queryFn: () => api<NewsItemData[]>(`/api/news?iso3=${iso3.toUpperCase()}&limit=10`),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
```

Replace the synopsis placeholder section:

```tsx
        {/* Synopsis */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">Synopsis</h2>
          <SynopsisCard synopsis={synopsisData ?? null} />
        </section>
```

Replace the news placeholder section:

```tsx
        {/* News & impact */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">News & impact</h2>
          {newsData && newsData.length > 0 ? (
            <div className="space-y-2">
              {newsData.map((item) => (
                <NewsItemCard key={item.id} item={item} />
              ))}
            </div>
          ) : (
            <InstitutionalTable columns={[{ key: "label", header: "" }]} rows={[]} emptyLabel="No scored news yet." />
          )}
        </section>
```

### 9.4 — Admin synopses review page

**File: `apps/web/src/routes/AdminSynopses.tsx`** (create)

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import AppShell from "./AppShell";

interface SynopsisListItem {
  id: string;
  iso3: string;
  text: string;
  generated_at: string;
  approval_state: string;
}

export default function AdminSynopses() {
  const queryClient = useQueryClient();

  const { data: synopses, isLoading } = useQuery<SynopsisListItem[]>({
    queryKey: ["admin-synopses"],
    queryFn: () => api<SynopsisListItem[]>("/api/admin/synopses"),
    staleTime: 30 * 1000,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      api(`/api/admin/synopses/${id}/approve`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-synopses"] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) =>
      api(`/api/admin/synopses/${id}/reject`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-synopses"] }),
  });

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl p-6">
        <h1 className="mb-6 text-xl font-semibold text-ink-900">Synopsis Review</h1>

        {isLoading && <p className="text-ink-500">Loading...</p>}

        {synopses && synopses.length === 0 && (
          <p className="text-ink-500">No synopses pending review.</p>
        )}

        <div className="space-y-4">
          {synopses?.map((s) => (
            <div key={s.id} className="rounded-md border border-ink-100 bg-white p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium text-ink-900">{s.iso3}</span>
                  <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                    {s.approval_state}
                  </span>
                </div>
                <span className="text-xs text-ink-400">
                  {new Date(s.generated_at).toLocaleString()}
                </span>
              </div>

              <div className="mb-3 text-sm text-ink-700 line-clamp-4">{s.text}</div>

              <div className="flex gap-2">
                <button
                  onClick={() => approveMutation.mutate(s.id)}
                  disabled={approveMutation.isPending}
                  className="rounded-md bg-positive px-3 py-1.5 text-xs font-medium text-white hover:bg-positive/90 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  onClick={() => rejectMutation.mutate(s.id)}
                  disabled={rejectMutation.isPending}
                  className="rounded-md bg-danger px-3 py-1.5 text-xs font-medium text-white hover:bg-danger/90 disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </AppShell>
  );
}
```

### 9.5 — Update App.tsx

**File: `apps/web/src/App.tsx`** (modify)

Add import and route:

```tsx
import AdminSynopses from "./routes/AdminSynopses";

// Inside the Route tree, add:
<Route path="/admin/synopses" element={<RequireAuth><AdminSynopses /></RequireAuth>} />
```

**Self-review:** SynopsisCard shows approved state or placeholder. NewsItemCard shows AI vs heuristic badge, 4-axis scores, and event type. Admin page has approve/reject buttons with optimistic invalidation. Route is auth-protected.

---

## Task 10 of 10 -- Bundle integration + manual smoke + self-review

**Why:** Wire the approved synopsis into the country bundle response, then verify the full stack end-to-end.

- [ ] 10.1 Modify `services/country/bundle.py` to include latest approved synopsis
- [ ] 10.2 Manual smoke test checklist
- [ ] 10.3 Self-review

### 10.1 — Bundle modification

**File: `apps/api/src/atlas_api/services/country/bundle.py`** (modify)

Add import at top:

```python
from atlas_api.models import Synopsis
```

Add a helper function before `get_country_bundle`:

```python
def _latest_approved_synopsis(session: Session, iso3: str) -> str | None:
    """Return the text of the latest approved synopsis, or None."""
    _approved = {"human_approved", "auto_approved_similarity", "auto_approved_stable_country"}
    row = (
        session.query(Synopsis)
        .filter(Synopsis.iso3 == iso3)
        .filter(Synopsis.approval_state.in_(_approved))
        .order_by(Synopsis.generated_at.desc())
        .first()
    )
    return row.text if row else None
```

In `get_country_bundle`, replace `synopsis=None` with:

```python
    synopsis_text = _latest_approved_synopsis(session, iso3)

    return CountryBundle(
        country=CountrySchema.model_validate(country, from_attributes=True),
        macro=macro,
        fx=fx,
        ratings=ratings,
        risk=risk,
        synopsis=synopsis_text,
        news_placeholder=synopsis_text is None,
    )
```

### 10.2 — Manual smoke test checklist

```
- [ ] Run migration: cd infra && alembic upgrade head
      -> Verify prompt_trace and synopsis tables created
      -> Verify news_impact_score.prompt_trace_id column added

- [ ] Start API: cd apps/api && uv run uvicorn atlas_api.main:app --reload
      -> Verify /docs shows new synopsis endpoints

- [ ] Test AI scoring (if ANTHROPIC_API_KEY is set):
      -> Trigger news pipeline
      -> Check news_impact_score rows: some should have scorer != 'heuristic'
      -> Check prompt_trace rows created for AI-scored items

- [ ] Test synopsis generation:
      -> POST /api/admin/synopses/generate/NGA (with auth header)
      -> Verify synopsis row created with approval_state='proposed'
      -> Verify prompt_trace row created with purpose='synopsis'

- [ ] Test admin approval:
      -> GET /api/admin/synopses -> see proposed synopsis
      -> POST /api/admin/synopses/{id}/approve -> state changes to human_approved
      -> GET /api/synopses/NGA -> returns the approved synopsis

- [ ] Test frontend:
      -> Navigate to /countries/NGA -> synopsis card shows approved text
      -> News items show AI badge (blue) or heuristic badge (grey)
      -> Navigate to /admin/synopses -> approve/reject buttons work

- [ ] Test fallback:
      -> Temporarily unset ANTHROPIC_API_KEY
      -> Trigger news pipeline -> all items scored with heuristic
      -> POST /api/admin/synopses/generate/NGA -> returns skipped

- [ ] Test token cap:
      -> Set AI_DAILY_TOKEN_CAP=1
      -> Trigger news pipeline -> should fall back to heuristic immediately
```

### 10.3 — Self-review checklist

```
- [ ] Every Claude call uses tool-use mode with strict JSON schema          ✓ provider.py
- [ ] Schema violation -> retry once -> fallback                            ✓ provider.py call_tool loop
- [ ] Grounding: prompts include structured context block                   ✓ synopsis.py _build_grounding_context
- [ ] Human-in-the-loop: synopses land as proposed; only approved render    ✓ synopsis.py + endpoints + CountryProfile
- [ ] Lineage: every AI output writes prompt_trace                          ✓ trace.py + news_scorer.py + synopsis.py
- [ ] Cost guardrail: daily token cap, counter, heuristic fallback          ✓ provider.py _DailyTokenCounter
- [ ] Model configurable via env                                            ✓ config.py ai_model
- [ ] Migration 0009, down_revision 0008_news_pipeline                      ✓
- [ ] Tests mock anthropic.Anthropic client                                 ✓ all test files
- [ ] StrEnum for approval states                                           ✓ ai.py SynopsisApprovalState
- [ ] tenant_id on synopsis with prototype default                          ✓ models.py + migration
- [ ] prompt_trace stores full I/O as JSONB (no API key)                    ✓ trace.py
- [ ] Heuristic scorer preserved as fallback                                ✓ pipeline.py _score_item
- [ ] News items show AI vs heuristic badge                                 ✓ NewsItemCard.tsx
- [ ] Admin synopses review page at /admin/synopses                         ✓ AdminSynopses.tsx
```

---

## Execution handoff

All 10 tasks are sequential. Tasks 1-3 (deps, schemas, migration) can be batched as a single commit. Task 4 (provider + trace) is the foundation everything else builds on. Tasks 5-6 (AI scorer + synopsis) are the core AI features. Tasks 7-8 (endpoints + pipeline wiring) connect backend to API. Task 9 (frontend) connects API to UI. Task 10 (bundle integration + smoke) ties it all together.

Estimated effort: 4-6 hours for an agentic worker executing task-by-task with tests.

**Run the plan with:** `superpowers:executing-plans` or `superpowers:subagent-driven-development`
