"""AI integration schemas -- synopsis, prompt trace, scoring contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# -- Enums ------------------------------------------------------------------


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


# -- Prompt Trace -----------------------------------------------------------


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


# -- Synopsis ---------------------------------------------------------------


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


# -- AI Scoring -------------------------------------------------------------


class AIScoreResult(BaseModel):
    """The typed output schema Claude must return for news impact scoring."""

    fiscal_impact: str = Field(..., pattern="^[LMH]$")
    external_impact: str = Field(..., pattern="^[LMH]$")
    fx_impact: str = Field(..., pattern="^[LMH]$")
    political_impact: str = Field(..., pattern="^[LMH]$")
    rationale: dict[str, str] = Field(
        ...,
        description="Per-axis rationale: {fiscal: ..., external: ..., fx: ..., political: ...}",
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
