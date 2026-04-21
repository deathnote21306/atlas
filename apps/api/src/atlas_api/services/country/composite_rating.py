"""Composite sovereign rating per spec §6.4.

Maps agency-native rating strings onto a shared 22-step numeric scale
(0 = AAA, 21 = default) then weights by agency. Missing agencies are
handled by rescaling the remaining weights to sum to 1.
"""

AGENCY_WEIGHTS: dict[str, float] = {"S&P": 0.40, "Moodys": 0.35, "Fitch": 0.25}


# 22-step investment-to-default ladder shared by S&P and Fitch.
# Each agency-native string maps to one step; D/RD/DD/DDD alias to 21.
_SP_FITCH = [
    "AAA",                         # 0
    "AA+", "AA", "AA-",            # 1, 2, 3
    "A+", "A", "A-",               # 4, 5, 6
    "BBB+", "BBB", "BBB-",         # 7, 8, 9
    "BB+", "BB", "BB-",            # 10, 11, 12
    "B+", "B", "B-",               # 13, 14, 15
    "CCC+", "CCC", "CCC-",         # 16, 17, 18
    "CC",                          # 19
    "C",                           # 20
    "SD",                          # 21 (also D / RD / DD / DDD)
]

_SP_FITCH_ALIASES = {
    "D": 21, "RD": 21, "DD": 21, "DDD": 21,
}

_SP_INDEX = {r: i for i, r in enumerate(_SP_FITCH)}
_SP_INDEX.update(_SP_FITCH_ALIASES)


# Moodys has 21 native rating names mapped onto the 22-step grid.
# A reserved slot at index 7 sits between A3 and Baa1 so that the
# Baa/Ba/B/Caa notches align with the market-convention numeric scale.
_MOODYS_INDEX: dict[str, int] = {
    "Aaa": 0,
    "Aa1": 1, "Aa2": 2, "Aa3": 3,
    "A1": 4, "A2": 5, "A3": 6,
    # index 7: reserved — no Moodys rating occupies this notch
    "Baa1": 8, "Baa2": 9, "Baa3": 10,
    "Ba1": 11, "Ba2": 12, "Ba3": 13,
    "B1": 14, "B2": 15, "B3": 16,
    "Caa1": 17, "Caa2": 18, "Caa3": 19,
    "Ca": 20,
    "C": 21,
}


def rating_to_score(agency: str, rating: str) -> int:
    if agency in ("S&P", "Fitch"):
        if rating not in _SP_INDEX:
            raise ValueError(f"unknown {agency} rating: {rating!r}")
        return _SP_INDEX[rating]
    if agency == "Moodys":
        if rating not in _MOODYS_INDEX:
            raise ValueError(f"unknown Moodys rating: {rating!r}")
        return _MOODYS_INDEX[rating]
    raise ValueError(f"unknown agency: {agency!r}")


_UNRATED = {"NR", "WD", "WR", "N/A", ""}


def composite_score(ratings: dict[str, str]) -> float | None:
    """ratings = {"S&P": "B", "Moodys": "Caa1", "Fitch": "B-"} → weighted score on 22-step scale.

    Missing agencies or NR/WD ratings: rescale remaining weights so they sum to 1.
    Empty input: None.
    """
    if not ratings:
        return None
    scored = {a: r for a, r in ratings.items() if a in AGENCY_WEIGHTS and r not in _UNRATED}
    if not scored:
        return None
    present_weight = sum(AGENCY_WEIGHTS[a] for a in scored)
    total = 0.0
    for agency, rating in scored.items():
        w = AGENCY_WEIGHTS[agency] / present_weight
        total += w * rating_to_score(agency, rating)
    return round(total, 4)
