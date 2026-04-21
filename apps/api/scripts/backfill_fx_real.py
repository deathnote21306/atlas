"""Replace synthetic FX history with real data from Yahoo Finance (yfinance).

Source: Yahoo Finance via yfinance — free, no API key, covers all 10 currencies.
Replaces all seed_approximation rows with real observed data.
"""

import uuid
from datetime import UTC, datetime

import yfinance as yf
from sqlalchemy import delete, select, func
from sqlalchemy.dialects.postgresql import insert

import sys
sys.path.insert(0, "packages/schemas/src")
sys.path.insert(0, "apps/api/src")

from atlas_api.db import SessionLocal
from atlas_api.models import FxRate
from atlas_api.services.country.indicators import ISO3_TO_CCY

YAHOO_TICKERS = {
    "ETH": "ETBUSD=X",
    "GHA": "GHSUSD=X",
    "KEN": "KESUSD=X",
    "NGA": "NGNUSD=X",
    "EGY": "EGPUSD=X",
    "MAR": "MADUSD=X",
    "ZAF": "ZARUSD=X",
    "RWA": "RWFUSD=X",
    "CIV": "XOFUSD=X",
    "SEN": "XOFUSD=X",
}


def main() -> None:
    now = datetime.now(UTC)

    with SessionLocal() as s:
        # Step 1: Delete all synthetic rows
        deleted = s.execute(
            delete(FxRate).where(FxRate.source == "seed_approximation")
        ).rowcount
        print(f"Deleted {deleted} synthetic rows")
        s.commit()

        # Step 2: Fetch real data from yfinance
        inserted = 0
        for iso3, ticker in YAHOO_TICKERS.items():
            ccy = ISO3_TO_CCY[iso3]
            print(f"Fetching {iso3} ({ticker})...", end=" ")

            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="1y")

                if len(hist) == 0:
                    print(f"NO DATA")
                    continue

                count = 0
                for idx, row in hist.iterrows():
                    obs_date = idx.date()
                    close = float(row["Close"])
                    if close <= 0:
                        continue

                    # yfinance returns CCY/USD (e.g. ETB per 1 USD inverted)
                    # Ticker ETBUSD=X returns USD per 1 ETB
                    usd_per_ccy = close

                    stmt = insert(FxRate).values(
                        id=uuid.uuid4(),
                        iso3=iso3,
                        ccy=ccy,
                        usd_per_ccy=usd_per_ccy,
                        observation_date=obs_date,
                        source="yfinance",
                        ingested_at=now,
                    ).on_conflict_do_update(
                        constraint="uq_fx_daily",
                        set_={"usd_per_ccy": usd_per_ccy, "source": "yfinance", "ingested_at": now},
                    )
                    s.execute(stmt)
                    count += 1

                print(f"{count} rows")
                inserted += count
            except Exception as e:
                print(f"ERROR: {e}")

        s.commit()
        print(f"\nTotal inserted/updated: {inserted}")

        # Step 3: Verify — no synthetic data remains
        source_counts = s.execute(
            select(FxRate.source, func.count()).group_by(FxRate.source)
        ).all()
        print("\nSource breakdown:")
        for src, cnt in source_counts:
            print(f"  {src}: {cnt}")

        # Per-country coverage
        print("\nPer-country coverage:")
        rows = s.execute(
            select(FxRate.iso3, func.count(), func.min(FxRate.observation_date), func.max(FxRate.observation_date))
            .group_by(FxRate.iso3)
            .order_by(FxRate.iso3)
        ).all()
        for iso, cnt, mn, mx in rows:
            print(f"  {iso}: {cnt} days ({mn} to {mx})")


if __name__ == "__main__":
    main()
