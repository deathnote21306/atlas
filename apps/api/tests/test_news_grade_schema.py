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
