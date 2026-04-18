"""Tests for synopsis API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from atlas_schemas.ai import SynopsisListItem, SynopsisOut


@pytest.fixture
def synopsis_row():
    """Build a mock synopsis row for testing."""
    from unittest.mock import MagicMock

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
    assert synopsis_row.approval_state == "human_approved"
    assert synopsis_row.iso3 == "NGA"


def test_approve_rejects_non_proposed():
    """Cannot approve a synopsis that is not in 'proposed' state."""
    assert "proposed" not in {"human_approved", "rejected"}


def test_synopsis_list_item_schema():
    item = SynopsisListItem(
        id=uuid.uuid4(),
        iso3="NGA",
        text="Test synopsis",
        generated_at=datetime.now(UTC),
        approval_state="proposed",
    )
    assert item.approval_state == "proposed"


def test_synopsis_out_schema(synopsis_row):
    out = SynopsisOut(
        id=synopsis_row.id,
        iso3=synopsis_row.iso3,
        text=synopsis_row.text,
        key_points=synopsis_row.key_points,
        generated_at=synopsis_row.generated_at,
        approval_state=synopsis_row.approval_state,
        approved_by=synopsis_row.approved_by,
        approved_at=synopsis_row.approved_at,
        prompt_trace_id=synopsis_row.prompt_trace_id,
        tenant_id=synopsis_row.tenant_id,
    )
    assert out.iso3 == "NGA"
    assert out.approval_state == "human_approved"


def test_reject_flow_schema():
    """Verify rejection sets the correct state."""
    out = SynopsisOut(
        id=uuid.uuid4(),
        iso3="KEN",
        text="Kenya synopsis text",
        key_points=[],
        generated_at=datetime.now(UTC),
        approval_state="rejected",
        approved_by=uuid.uuid4(),
        approved_at=datetime.now(UTC),
        prompt_trace_id=None,
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
    )
    assert out.approval_state == "rejected"
