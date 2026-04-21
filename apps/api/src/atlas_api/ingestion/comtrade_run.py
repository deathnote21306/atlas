"""CLI for Comtrade trade data ingestion.

Usage:
    python -m atlas_api.ingestion.comtrade_run --countries all --years 2020,2021,2022,2023,2024
    python -m atlas_api.ingestion.comtrade_run --countries ETH --years 2024
"""

import argparse
import json

from atlas_api.db import SessionLocal
from atlas_api.ingestion.comtrade import COMTRADE_REPORTER_CODES, backfill


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Comtrade trade data ingestion")
    parser.add_argument(
        "--countries", type=str, default="all", help="Comma-separated ISO3 codes or 'all'"
    )
    parser.add_argument("--years", type=str, default="2024", help="Comma-separated years")
    args = parser.parse_args()

    countries = (
        list(COMTRADE_REPORTER_CODES.keys())
        if args.countries == "all"
        else args.countries.upper().split(",")
    )
    years = [int(y) for y in args.years.split(",")]

    est = len(countries) * len(years) * 4
    print(f"Backfill: {len(countries)} countries x {len(years)} years = ~{est} req")

    with SessionLocal() as session:
        stats = backfill(session, countries=countries, years=years)

    print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    main()
