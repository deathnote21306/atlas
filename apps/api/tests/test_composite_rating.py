import pytest
from atlas_api.services.country.composite_rating import (
    AGENCY_WEIGHTS,
    composite_score,
    rating_to_score,
)


# Sample agency-native ratings mapped to 22-step numeric scale (0 = AAA, 21 = D).
# Golden tests lock the ladder.
@pytest.mark.parametrize(
    "agency,rating,expected",
    [
        ("S&P", "AAA", 0),
        ("S&P", "AA+", 1),
        ("S&P", "AA", 2),
        ("S&P", "A", 5),
        ("S&P", "BBB", 8),
        ("S&P", "BB", 11),
        ("S&P", "B", 14),
        ("S&P", "CCC", 17),
        ("S&P", "SD", 21),
        ("S&P", "D", 21),
        ("Moodys", "Aaa", 0),
        ("Moodys", "Aa1", 1),
        ("Moodys", "Baa3", 10),
        ("Moodys", "Caa1", 17),
        ("Moodys", "Ca", 20),
        ("Moodys", "C", 21),
        ("Fitch", "AAA", 0),
        ("Fitch", "BB-", 12),
        ("Fitch", "RD", 21),
    ],
)
def test_rating_to_score(agency: str, rating: str, expected: int):
    assert rating_to_score(agency, rating) == expected


def test_composite_all_three_present():
    # S&P = B (14), Moodys = Caa1 (17), Fitch = B- (15)
    # weights: 0.4*14 + 0.35*17 + 0.25*15 = 5.6 + 5.95 + 3.75 = 15.30
    assert composite_score({"S&P": "B", "Moodys": "Caa1", "Fitch": "B-"}) == pytest.approx(15.30)


def test_composite_missing_fitch_rescales():
    # S&P = B (14), Moodys = Caa1 (17); weights rescaled to 0.4/0.75 and 0.35/0.75
    # = (0.5333 * 14) + (0.4667 * 17) = 7.467 + 7.933 = 15.400
    assert composite_score({"S&P": "B", "Moodys": "Caa1"}) == pytest.approx(15.40, rel=1e-3)


def test_composite_single_agency_returns_that_score():
    assert composite_score({"S&P": "B+"}) == pytest.approx(13.0)


def test_composite_empty_returns_none():
    assert composite_score({}) is None


def test_agency_weights_sum_to_one():
    assert sum(AGENCY_WEIGHTS.values()) == pytest.approx(1.0)


def test_unknown_rating_raises():
    with pytest.raises(ValueError):
        rating_to_score("S&P", "Zzz")


def test_unknown_agency_raises():
    with pytest.raises(ValueError):
        rating_to_score("OtherAgency", "AAA")
