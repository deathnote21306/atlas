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
        {
            "model": "claude-sonnet-4-5",
            "tokens_in": 400,
            "tokens_out": 120,
            "prompt_hash": "h",
            "raw_response": graded.model_dump(),
            "error": None,
        },
    )

    result, meta = grade_article(
        title="Moody's upgrades Kenya",
        body="Kenya was raised to B3.",
        source="reuters.com",
        candidate_iso3="KEN",
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
