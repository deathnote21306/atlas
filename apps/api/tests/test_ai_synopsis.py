"""Tests for synopsis generation with mocked Claude."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

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

    # Verify prompt trace was called with purpose="synopsis"
    mock_trace.assert_called_once()
    trace_call_kwargs = mock_trace.call_args
    assert trace_call_kwargs.kwargs["purpose"] == "synopsis"


@patch("atlas_api.services.ai.synopsis.settings")
def test_generate_synopsis_no_api_key(mock_settings):
    mock_settings.anthropic_api_key = ""
    session = MagicMock()

    from atlas_api.services.ai.synopsis import generate_synopsis
    result = generate_synopsis(session, "NGA")
    assert result is None


@patch("atlas_api.services.ai.synopsis.call_tool")
@patch("atlas_api.services.ai.synopsis.settings")
@patch("atlas_api.services.ai.synopsis._build_grounding_context")
def test_generate_synopsis_ai_failure(mock_context, mock_settings, mock_call_tool):
    mock_settings.anthropic_api_key = "sk-ant-test"
    mock_settings.ai_model = "claude-sonnet-4-5-20250514"

    mock_context.return_value = {"country": {"iso3": "NGA"}, "macro": [], "ratings": {},
                                  "risk_composite": 50, "recent_news": []}

    mock_call_tool.return_value = (None, {"error": "api_error", "model": "test",
                                          "tokens_in": 0, "tokens_out": 0, "prompt_hash": "x"})

    session = MagicMock()

    from atlas_api.services.ai.synopsis import generate_synopsis
    result = generate_synopsis(session, "NGA")
    assert result is None
    session.add.assert_not_called()
