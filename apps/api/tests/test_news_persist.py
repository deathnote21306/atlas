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
    # MagicMock auto-creates attributes, so start this at None to detect a real write.
    item.original_title = None
    return item


def _meta() -> dict:
    return {
        "model": "claude-sonnet-4-5",
        "prompt_hash": "p",
        "input_hash": "i",
        "tokens_in": 300,
        "tokens_out": 90,
        "raw_response": {},
    }


@patch("atlas_api.services.news.persist.persist_score")
@patch("atlas_api.services.news.persist.persist_trace")
def test_apply_grade_keeps_and_writes_everything(mock_trace, mock_score):
    trace = MagicMock()
    trace.id = uuid.uuid4()
    mock_trace.return_value = trace

    session = MagicMock()
    item = _item()

    apply_grade(session, item, _result(), _meta(), keep=True)

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
    # Provenance must not claim the heuristic produced this.
    assert mock_score.call_args.kwargs["scorer"] == "ai_grader"
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

    apply_grade(session, item, _result(relevant=False, relevance_score=5), _meta(), keep=False)

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

    apply_grade(session, item, _result(source_lang="en"), _meta(), keep=True)

    assert item.original_title is None
    assert item.title == "IMF completes Ghana review"


def test_mark_deferred_leaves_item_unserved():
    session = MagicMock()
    item = _item()
    mark_deferred(session, item)
    assert item.relevant is False
    assert item.ai_graded is False
