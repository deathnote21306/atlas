"""Tests for AI news scorer with mocked Anthropic client."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

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
