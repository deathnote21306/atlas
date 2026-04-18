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
