"""The PDF report must show the same risk score the rest of the product shows.

Regression guard: the report previously read a second, legacy risk engine via the
country bundle, so an exported brief disagreed with the country page for the same
country on the same day (CIV showed 60 on screen and 37 in the PDF).
"""

from __future__ import annotations

from atlas_api.services.reporting.service import _risk_context_from_decomposition


def _decomposition(**overrides):
    base = {
        "composite_score": 60,
        "composite_label": "Elevated Risk",
        "methodology_version": "v2.1",
        "dimensions": [
            {"key": "fiscal", "label": "Fiscal", "score": 93, "weight": 25},
            {"key": "external", "label": "External", "score": 100, "weight": 20},
            {"key": "fx", "label": "FX", "score": 11, "weight": 20},
            {"key": "growth", "label": "Growth", "score": 46, "weight": 15},
            {"key": "political", "label": "Political", "score": 50, "weight": 10},
            {"key": "liquidity", "label": "Liquidity", "score": 70, "weight": 10},
        ],
    }
    base.update(overrides)
    return base


def test_uses_the_stored_composite_score():
    ctx = _risk_context_from_decomposition(_decomposition())
    assert ctx is not None
    assert ctx["risk_score"] == "60", "must print the same score the app shows"
    assert ctx["risk_label"] == "Elevated Risk", "must reuse the app's own wording"


def test_carries_the_apps_six_dimensions_not_the_legacy_ones():
    ctx = _risk_context_from_decomposition(_decomposition())
    labels = [d["label"] for d in ctx["dimensions"]]
    assert labels == ["Fiscal", "External", "FX", "Growth", "Political", "Liquidity"]
    for legacy in ("Debt Burden", "Fiscal Flexibility", "Inflation Pressure"):
        assert legacy not in labels


def test_dimension_scores_are_already_0_to_100():
    """Engine B scores are 0-100, so the bar width is the score itself, not score x 10."""
    ctx = _risk_context_from_decomposition(_decomposition())
    fiscal = ctx["dimensions"][0]
    assert fiscal["score"] == "93"
    assert fiscal["pct"] == 93


def test_severity_class_tracks_the_band():
    cases = [
        (90, "Severe Risk", "critical"),
        (72, "High Risk", "high"),
        (60, "Elevated Risk", "high"),
        (35, "Moderate Risk", "medium"),
        (10, "Low Risk", "low"),
    ]
    for score, label, expected in cases:
        ctx = _risk_context_from_decomposition(
            _decomposition(composite_score=score, composite_label=label)
        )
        assert ctx["risk_level_cls"] == expected, f"{label} should map to {expected}"


def test_returns_none_when_the_country_has_no_decomposition_yet():
    assert _risk_context_from_decomposition(None) is None
    assert _risk_context_from_decomposition({}) is None
    assert _risk_context_from_decomposition({"dimensions": []}) is None
