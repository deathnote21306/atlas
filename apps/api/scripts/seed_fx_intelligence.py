"""Seed FX Intelligence fields for all 10 countries + compute change ladder from existing FxRate data."""  # noqa: E501

from datetime import UTC, date, datetime, timedelta

from atlas_api.db import SessionLocal
from atlas_api.models import Country, FxRate
from sqlalchemy import select

FX_INTEL = {
    "ETH": {
        "primary_currency": "ETB",
        "fx_implied_vol_pct": None,
        "fx_implied_vol_note": "illiquid",
        "fx_parallel_premium": 35.2,
        "fx_reer_deviation_pct": -42.5,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": date(2025, 12, 9),
    },
    "GHA": {
        "primary_currency": "GHS",
        "fx_implied_vol_pct": 18.5,
        "fx_implied_vol_note": None,
        "fx_parallel_premium": 7.2,
        "fx_reer_deviation_pct": -15.3,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": date(2026, 3, 15),
    },
    "KEN": {
        "primary_currency": "KES",
        "fx_implied_vol_pct": 12.8,
        "fx_implied_vol_note": None,
        "fx_parallel_premium": 1.5,
        "fx_reer_deviation_pct": -8.2,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": date(2026, 2, 20),
    },
    "NGA": {
        "primary_currency": "NGN",
        "fx_implied_vol_pct": None,
        "fx_implied_vol_note": "OTC",
        "fx_parallel_premium": 8.5,
        "fx_reer_deviation_pct": 2.1,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": date(2026, 4, 5),
    },
    "CIV": {
        "primary_currency": "XOF",
        "fx_implied_vol_pct": None,
        "fx_implied_vol_note": "illiquid",
        "fx_parallel_premium": 0.0,
        "fx_reer_deviation_pct": 3.2,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": None,
    },
    "SEN": {
        "primary_currency": "XOF",
        "fx_implied_vol_pct": None,
        "fx_implied_vol_note": "illiquid",
        "fx_parallel_premium": 0.0,
        "fx_reer_deviation_pct": 1.8,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": None,
    },
    "RWA": {
        "primary_currency": "RWF",
        "fx_implied_vol_pct": None,
        "fx_implied_vol_note": "illiquid",
        "fx_parallel_premium": 2.1,
        "fx_reer_deviation_pct": -5.4,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": None,
    },
    "ZAF": {
        "primary_currency": "ZAR",
        "fx_implied_vol_pct": 14.2,
        "fx_implied_vol_note": None,
        "fx_parallel_premium": 0.0,
        "fx_reer_deviation_pct": -12.8,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": None,
    },
    "MAR": {
        "primary_currency": "MAD",
        "fx_implied_vol_pct": 5.5,
        "fx_implied_vol_note": None,
        "fx_parallel_premium": 0.0,
        "fx_reer_deviation_pct": 4.1,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": None,
    },
    "EGY": {
        "primary_currency": "EGP",
        "fx_implied_vol_pct": None,
        "fx_implied_vol_note": "OTC",
        "fx_parallel_premium": 3.8,
        "fx_reer_deviation_pct": -28.5,
        "fx_reer_as_of": datetime(2026, 3, 31, tzinfo=UTC),
        "fx_last_bc_intervention": date(2026, 3, 28),
    },
}


def compute_change_ladder(session, iso3: str) -> dict:
    """Compute FX change ladder from existing FxRate records."""
    latest = session.execute(
        select(FxRate).where(FxRate.iso3 == iso3).order_by(FxRate.observation_date.desc()).limit(1)
    ).scalar_one_or_none()

    if latest is None:
        return {}

    base_date = latest.observation_date
    base_val = float(latest.usd_per_ccy)
    if base_val == 0:
        return {}

    # USD/CCY = 1/usd_per_ccy, so change in USD/CCY
    spot_usd_per_local = 1.0 / base_val

    result = {"fx_change_as_of": datetime.now(UTC)}
    windows = [
        ("fx_change_1d_pct", 1),
        ("fx_change_1w_pct", 7),
        ("fx_change_1m_pct", 30),
        ("fx_change_3m_pct", 90),
    ]

    for field, days in windows:
        target_date = base_date - timedelta(days=days)
        prev = session.execute(
            select(FxRate)
            .where(FxRate.iso3 == iso3, FxRate.observation_date <= target_date)
            .order_by(FxRate.observation_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if prev and float(prev.usd_per_ccy) != 0:
            prev_spot = 1.0 / float(prev.usd_per_ccy)
            pct = ((spot_usd_per_local - prev_spot) / prev_spot) * 100
            result[field] = round(pct, 4)
        else:
            result[field] = None

    return result


def main() -> None:
    with SessionLocal() as s:
        for iso3, fields in FX_INTEL.items():
            country = s.get(Country, iso3)
            if country is None:
                print(f"skip {iso3}: not found")
                continue

            country.primary_currency = fields["primary_currency"]
            country.fx_implied_vol_pct = fields["fx_implied_vol_pct"]
            country.fx_implied_vol_note = fields["fx_implied_vol_note"]
            country.fx_parallel_premium = fields["fx_parallel_premium"]
            country.fx_reer_deviation_pct = fields["fx_reer_deviation_pct"]
            country.fx_reer_as_of = fields["fx_reer_as_of"]
            country.fx_last_bc_intervention = fields["fx_last_bc_intervention"]

            ladder = compute_change_ladder(s, iso3)
            for k, v in ladder.items():
                setattr(country, k, v)

            print(f"{iso3}: seeded FX intelligence, ladder={bool(ladder)}")

        s.commit()
        print("Done")


if __name__ == "__main__":
    main()
