"""Backfill 12 months of daily FX rates from frankfurter.app (ECB-based, free, no key).

Source: frankfurter.app — provides historical EUR-based rates. We convert to USD-based.
This is a one-time backfill; daily ingestion continues from open.er-api.com.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy.dialects.postgresql import insert

import sys
sys.path.insert(0, "packages/schemas/src")
sys.path.insert(0, "apps/api/src")

from atlas_api.db import SessionLocal
from atlas_api.models import FxRate
from atlas_api.services.country.indicators import ISO3_TO_CCY


def main() -> None:
    end_date = date.today()
    start_date = end_date - timedelta(days=365)

    # Map ISO3 -> currency code
    currencies = list(set(ISO3_TO_CCY.values()))
    symbols = ",".join(currencies + ["USD"])

    print(f"Fetching {start_date} to {end_date} for {len(currencies)} currencies from frankfurter.app...")

    resp = httpx.get(
        f"https://api.frankfurter.dev/v1/{start_date.isoformat()}..{end_date.isoformat()}",
        params={"to": symbols, "from": "EUR"},
        timeout=60,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    rates_by_date = data.get("rates", {})

    print(f"Received {len(rates_by_date)} days of data")

    now = datetime.now(UTC)
    iso3_to_ccy = ISO3_TO_CCY

    with SessionLocal() as s:
        inserted = 0
        for date_str, day_rates in sorted(rates_by_date.items()):
            obs_date = date.fromisoformat(date_str)
            usd_per_eur = day_rates.get("USD")
            if usd_per_eur is None or usd_per_eur == 0:
                continue

            for iso3, ccy in iso3_to_ccy.items():
                ccy_per_eur = day_rates.get(ccy)
                if ccy_per_eur is None or ccy_per_eur == 0:
                    continue

                # Convert: USD/CCY = CCY_per_EUR / USD_per_EUR
                ccy_per_usd = ccy_per_eur / usd_per_eur
                usd_per_ccy = 1.0 / ccy_per_usd

                stmt = insert(FxRate).values(
                    id=uuid.uuid4(),
                    iso3=iso3,
                    ccy=ccy,
                    usd_per_ccy=usd_per_ccy,
                    observation_date=obs_date,
                    source="frankfurter.app",
                    ingested_at=now,
                ).on_conflict_do_nothing(constraint="uq_fx_daily")

                result = s.execute(stmt)
                if result.rowcount > 0:
                    inserted += 1

        s.commit()
        print(f"Inserted {inserted} FX observations")

        # Verify
        from sqlalchemy import select, func
        rows = s.execute(
            select(FxRate.iso3, func.count(), func.min(FxRate.observation_date), func.max(FxRate.observation_date))
            .group_by(FxRate.iso3)
        ).all()
        print("\nFX history per country:")
        for iso, cnt, mn, mx in rows:
            print(f"  {iso}: {cnt} days ({mn} to {mx})")


if __name__ == "__main__":
    main()
