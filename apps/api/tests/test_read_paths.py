import uuid
from datetime import UTC, date, datetime

from atlas_api.models import Country, DataVintage, FxRate, MacroIndicatorVintage, RatingHistory
from atlas_api.services.country.queries import (
    compute_fx_deltas,
    get_as_of,
    get_latest,
    get_latest_fx,
    get_rating_history,
)


def _country(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    session.commit()


def _vintage(session, source: str = "test") -> DataVintage:
    v = DataVintage(id=uuid.uuid4(), source=source, created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v


def test_get_latest_returns_most_recent_period(session):
    _country(session)
    v = _vintage(session)
    session.add_all([
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="INFLATION_PCT", period="2023",
            value=31.5, source="worldbank", source_date=date(2023, 12, 31),
            vintage_id=v.id,
        ),
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="INFLATION_PCT", period="2024",
            value=22.4, source="worldbank", source_date=date(2024, 12, 31),
            vintage_id=v.id,
        ),
    ])
    session.commit()
    row = get_latest(session, "GHA", "INFLATION_PCT")
    assert row is not None
    assert row.period == "2024"
    assert float(row.value) == 22.4


def test_get_as_of_uses_specific_vintage(session):
    _country(session)
    v_old = _vintage(session, "old")
    v_new = _vintage(session, "new")
    session.add_all([
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="GDP_USD", period="2024",
            value=80.0, source="worldbank", source_date=date(2024, 12, 31),
            vintage_id=v_old.id,
        ),
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="GDP_USD", period="2024",
            value=82.3, source="imf_weo", source_date=date(2024, 12, 31),
            vintage_id=v_new.id,
        ),
    ])
    session.commit()
    old = get_as_of(session, "GHA", "GDP_USD", v_old.id)
    new = get_as_of(session, "GHA", "GDP_USD", v_new.id)
    assert float(old.value) == 80.0
    assert float(new.value) == 82.3


def test_fx_deltas(session):
    _country(session)
    today = date(2026, 4, 16)
    rows = [
        (today, 15.00),
        (date(2026, 4, 15), 15.10),
        (date(2026, 4, 9), 14.80),
        (date(2026, 3, 17), 14.50),
        (date(2026, 1, 1), 14.00),
    ]
    for d, rate in rows:
        session.add(FxRate(
            id=uuid.uuid4(), iso3="GHA", ccy="GHS", usd_per_ccy=rate,
            observation_date=d, source="exchangerate.host",
        ))
    session.commit()

    latest = get_latest_fx(session, "GHA")
    assert latest is not None
    assert latest.observation_date == today

    deltas = compute_fx_deltas(session, "GHA")
    assert round(deltas["delta_1d_pct"], 4) == round((15.00 - 15.10) / 15.10 * 100, 4)
    assert round(deltas["delta_7d_pct"], 4) == round((15.00 - 14.80) / 14.80 * 100, 4)
    assert round(deltas["delta_30d_pct"], 4) == round((15.00 - 14.50) / 14.50 * 100, 4)
    assert round(deltas["delta_ytd_pct"], 4) == round((15.00 - 14.00) / 14.00 * 100, 4)


def test_rating_history_filtered(session):
    _country(session)
    session.add_all([
        RatingHistory(
            id=uuid.uuid4(), iso3="GHA", agency="S&P", rating="SD",
            outlook=None, action="default", action_date=date(2022, 12, 21),
        ),
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

    all_hist = get_rating_history(session, "GHA")
    assert len(all_hist) == 3
    assert all_hist[0].action_date == date(2024, 6, 1)
    sp_only = get_rating_history(session, "GHA", agency="S&P")
    assert len(sp_only) == 2
