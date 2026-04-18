import uuid
from datetime import UTC, datetime

from atlas_api.models import NewsItem
from atlas_api.services.news.heuristic_scorer import persist_score, score_impact


def test_fiscal_high_for_debt_article():
    scores = score_impact(
        "Ghana debt restructuring IMF bailout",
        "The fiscal deficit widens as bond yields rise."
        " Budget spending under review. Revenue shortfall expected.",
    )
    assert scores["fiscal_impact"] == "H"


def test_political_high_for_election():
    scores = score_impact(
        "Kenya election results spark protests",
        "The opposition challenges the government. Parliament debates constitution reform.",
    )
    assert scores["political_impact"] == "H"


def test_fx_medium_for_currency_article():
    scores = score_impact(
        "Naira depreciation accelerates",
        "The central bank floats the currency. Dollar reserves under pressure.",
    )
    assert scores["fx_impact"] in ("M", "H")


def test_low_for_irrelevant():
    scores = score_impact("Local weather report", "Sunshine expected tomorrow.")
    assert scores["fiscal_impact"] == "L"
    assert scores["external_impact"] == "L"
    assert scores["fx_impact"] == "L"
    assert scores["political_impact"] == "L"


def test_persist_score_creates_row(session):
    # Need a news_item first
    from atlas_api.services.news.dedup import url_hash
    item = NewsItem(
        id=uuid.uuid4(), url="https://test.com/article",
        url_hash=url_hash("https://test.com/article"),
        title="Test", source="test",
        published_at=datetime.now(UTC), body_text="Test body",
        ingested_at=datetime.now(UTC),
    )
    session.add(item)
    session.commit()

    scores = score_impact("Debt restructuring in Ghana", "IMF fiscal bond deficit budget")
    row = persist_score(session, item.id, scores)
    assert row.scorer == "heuristic"
    assert row.fiscal_impact in ("L", "M", "H")
