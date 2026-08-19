"""Pre-filter must cut only obvious junk and must never eat macro news."""

from __future__ import annotations

from atlas_api.services.news.prefilter import (
    TRACKED_ISO3,
    is_obvious_junk,
    split_by_budget,
)

JUNK = [
    ("Ghana beats Nigeria 2-1 in AFCON quarter final", "Full time report from the stadium."),
    ("Nollywood star announces new album release", "The singer spoke to reporters."),
    ("Obituary: veteran actor dies aged 81", "Family announced the funeral service."),
]

MACRO = [
    ("Ghana secures IMF disbursement", "The board approved the third review tranche."),
    ("Kenya shilling hits record low against dollar", "Reserves cover four months of imports."),
    ("Senegal debt restructuring talks open", "Bondholders met government officials."),
    ("Egypt election result raises reform questions", "Investors weigh policy continuity."),
]


def test_junk_is_cut():
    for title, body in JUNK:
        assert is_obvious_junk(title, body) is True, f"should be junk: {title}"


def test_macro_is_never_cut():
    for title, body in MACRO:
        assert is_obvious_junk(title, body) is False, f"must not be junk: {title}"


def test_tracked_countries_are_the_ten():
    expected = frozenset({"CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY"})
    assert TRACKED_ISO3 == expected


def test_budget_split():
    to_grade, deferred = split_by_budget(list(range(10)), 4)
    assert to_grade == [0, 1, 2, 3]
    assert deferred == [4, 5, 6, 7, 8, 9]


def test_budget_split_when_under_limit():
    to_grade, deferred = split_by_budget([1, 2], 10)
    assert to_grade == [1, 2]
    assert deferred == []
