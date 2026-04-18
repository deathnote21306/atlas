"""Heuristic 4-axis impact scorer. Keyword-weighted, no AI needed.
Produces L/M/H scores for fiscal, external, fx, and political impact axes.
Used as fallback when Claude is unavailable (Plan 5b), and as the default scorer in Plan 5a.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from atlas_api.models import NewsImpactScore

FISCAL_KEYWORDS = {
    "debt", "deficit", "budget", "fiscal", "spending", "tax",
    "revenue", "bond", "eurobond", "restructuring", "imf", "bailout",
}
EXTERNAL_KEYWORDS = {
    "trade", "export", "import", "current account", "fdi",
    "investment", "aid", "remittance", "tariff", "sanction",
}
FX_KEYWORDS = {
    "currency", "exchange rate", "depreciation", "devaluation",
    "dollar", "forex", "reserve", "peg", "float",
    "naira", "cedi", "rand", "shilling",
}
POLITICAL_KEYWORDS = {
    "election", "government", "president", "parliament", "coup",
    "protest", "reform", "constitution", "opposition", "military",
}


def _score_axis(text: str, keywords: set[str]) -> str:
    lower = text.lower()
    matches = sum(1 for kw in keywords if kw in lower)
    if matches >= 4:
        return "H"
    if matches >= 2:
        return "M"
    return "L"


def score_impact(title: str, body: str) -> dict[str, Any]:
    combined = title + " " + body
    return {
        "fiscal_impact": _score_axis(combined, FISCAL_KEYWORDS),
        "external_impact": _score_axis(combined, EXTERNAL_KEYWORDS),
        "fx_impact": _score_axis(combined, FX_KEYWORDS),
        "political_impact": _score_axis(combined, POLITICAL_KEYWORDS),
        "rationale": {
            "fiscal": "keyword matches in fiscal axis",
            "external": "keyword matches in external axis",
            "fx": "keyword matches in fx axis",
            "political": "keyword matches in political axis",
        },
    }


def persist_score(
    session: Session, news_item_id: uuid.UUID, score_dict: dict[str, Any]
) -> NewsImpactScore:
    row = NewsImpactScore(
        id=uuid.uuid4(),
        news_item_id=news_item_id,
        fiscal_impact=score_dict["fiscal_impact"],
        external_impact=score_dict["external_impact"],
        fx_impact=score_dict["fx_impact"],
        political_impact=score_dict["political_impact"],
        rationale=score_dict["rationale"],
        scorer="heuristic",
        scored_at=datetime.now(UTC),
    )
    session.add(row)
    session.commit()
    return row
