import uuid
from datetime import UTC, date, datetime

from atlas_api.models import (
    Country,
    DataVintage,
    FxRate,
    MacroIndicatorVintage,
    RatingHistory,
)
from atlas_api.services.country.bundle import get_country_bundle


def _seed_gha(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v


def test_bundle_missing_everything_returns_country_only(session):
    _seed_gha(session)
    b = get_country_bundle(session, "GHA")
    assert b is not None
    assert b.country.iso3 == "GHA"
    assert len(b.macro) == 12
    assert all(t.value is None for t in b.macro)
    assert b.fx is None
    assert b.ratings.latest_per_agency == {}
    assert b.ratings.composite_score is None
    assert b.risk.composite == 58.3
    assert b.synopsis is None
    assert b.news_placeholder is True


def test_bundle_unknown_country_returns_none(session):
    assert get_country_bundle(session, "ZZZ") is None


def test_bundle_populates_macro_and_fx(session):
    v = _seed_gha(session)
    session.add_all([
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="PUBLIC_DEBT_PCT_GDP",
            period="2024", value=83.0, source="worldbank",
            source_date=date(2024, 12, 31), vintage_id=v.id,
        ),
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="INFLATION_PCT",
            period="2024", value=22.0, source="worldbank",
            source_date=date(2024, 12, 31), vintage_id=v.id,
        ),
        FxRate(
            id=uuid.uuid4(), iso3="GHA", ccy="GHS", usd_per_ccy=1 / 15.0,
            observation_date=date(2026, 4, 16), source="open.er-api.com",
        ),
    ])
    session.commit()

    b = get_country_bundle(session, "GHA")
    assert b is not None
    debt = next(t for t in b.macro if t.indicator.value == "PUBLIC_DEBT_PCT_GDP")
    assert debt.value == 83.0
    assert debt.period == "2024"
    assert debt.source == "worldbank"
    inflation = next(t for t in b.macro if t.indicator.value == "INFLATION_PCT")
    assert inflation.value == 22.0
    assert b.fx is not None
    assert b.fx.latest.ccy == "GHS"


def test_bundle_populates_ratings(session):
    _seed_gha(session)
    session.add_all([
        RatingHistory(
            id=uuid.uuid4(), iso3="GHA", agency="S&P", rating="CCC+",
            outlook="stable", action="upgrade", action_date=date(2024, 5, 1),
        ),
        RatingHistory(
            id=uuid.uuid4(), iso3="GHA", agency="Moodys", rating="Caa3",
            outlook="stable", action="affirm", action_date=date(2024, 6, 1),
        ),
    ])
    session.commit()

    b = get_country_bundle(session, "GHA")
    assert b is not None
    assert set(b.ratings.latest_per_agency.keys()) == {"S&P", "Moodys"}
    assert b.ratings.latest_per_agency["S&P"].rating == "CCC+"
    assert b.ratings.composite_score is not None
    assert len(b.ratings.history) == 2


def test_bundle_includes_debt_profile_when_seeded(session):
    _seed_gha(session)
    country = session.get(Country, "GHA")
    country.debt_profile = {
        "vintage": "2024-Q3",
        "source": "IMF DSA",
        "headline": {
            "debt_gdp_pct": 76.4,
            "external_debt_gni_pct": 52.1,
            "debt_service_exports_pct": 23.7,
        },
        "composition": {
            "domestic_pct": 42,
            "external_pct": 58,
            "currency": {"usd": 38, "eur": 12, "local": 42, "other": 8},
            "fixed_pct": 65,
            "variable_pct": 35,
        },
        "maturity": {
            "lt1yr_pct": 18,
            "yr1_3_pct": 27,
            "yr3_5_pct": 21,
            "gt5yr_pct": 34,
            "wall_year": 2026,
        },
        "flags": {
            "high_fx_exposure": True,
            "near_term_maturity_wall": True,
            "market_access_restricted": True,
            "restructuring_overhang": True,
        },
        "ai_commentary": None,
    }
    session.commit()

    b = get_country_bundle(session, "GHA")
    assert b is not None
    assert b.debt_profile is not None
    assert b.debt_profile["headline"]["debt_gdp_pct"] == 76.4
    assert b.debt_profile["flags"]["high_fx_exposure"] is True
    assert b.debt_profile["ai_commentary"] is None


def test_bundle_debt_profile_null_when_not_seeded(session):
    _seed_gha(session)
    b = get_country_bundle(session, "GHA")
    assert b is not None
    assert b.debt_profile is None
