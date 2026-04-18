"""Tests for the AI provider — all calls mocked, never hits real API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from pydantic import BaseModel

from atlas_api.services.ai.provider import (
    _DailyTokenCounter,
    call_tool,
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


@patch("atlas_api.services.ai.provider.settings")
@patch("atlas_api.services.ai.provider._get_client")
def test_call_tool_retry_on_validation_error(mock_client_fn, mock_settings):
    """First call returns malformed output, second returns valid -> succeeds."""
    mock_settings.ai_model = "claude-sonnet-4-5-20250514"
    mock_settings.ai_daily_token_cap = 200_000
    mock_settings.anthropic_api_key = "sk-ant-test"

    # Reset counter
    token_counter._total = 0
    token_counter._date = ""

    # Malformed (missing required fields)
    bad_response = _make_mock_response("score_news", {"fiscal_impact": "H"})
    # Valid
    good_input = {
        "fiscal_impact": "H", "external_impact": "M",
        "fx_impact": "L", "political_impact": "M",
        "rationale": {"fiscal": "d", "external": "t", "fx": "s", "political": "e"},
    }
    good_response = _make_mock_response("score_news", good_input)

    client = MagicMock()
    client.messages.create.side_effect = [bad_response, good_response]
    mock_client_fn.return_value = client

    result, meta = call_tool(
        messages=[{"role": "user", "content": "test"}],
        system="test",
        tool_name="score_news",
        tool_description="test",
        result_model=MockScoreResult,
    )

    assert result is not None
    assert result.fiscal_impact == "H"
    assert client.messages.create.call_count == 2


@patch("atlas_api.services.ai.provider.settings")
@patch("atlas_api.services.ai.provider._get_client")
def test_call_tool_timeout_returns_none(mock_client_fn, mock_settings):
    """When the Claude API times out, call_tool returns (None, meta) with timeout error."""
    mock_settings.ai_model = "claude-sonnet-4-5-20250514"
    mock_settings.ai_daily_token_cap = 200_000
    mock_settings.anthropic_api_key = "sk-ant-test"

    # Reset counter
    token_counter._total = 0
    token_counter._date = ""

    client = MagicMock()
    client.messages.create.side_effect = httpx.ReadTimeout("Request timed out")
    mock_client_fn.return_value = client

    result, meta = call_tool(
        messages=[{"role": "user", "content": "test"}],
        system="test",
        tool_name="score_news",
        tool_description="test",
        result_model=MockScoreResult,
    )

    assert result is None
    assert "timeout" in meta["error"]
    # Should have retried once (2 total attempts)
    assert client.messages.create.call_count == 2
