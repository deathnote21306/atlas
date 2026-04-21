"""CLI for one-shot REER ingestion.

Usage:
    python -m atlas_api.ingestion.reer_run [--country ISO3] [--force]
"""

import argparse
import json
import sys

from atlas_api.db import SessionLocal
from atlas_api.ingestion.reer import run_reer_ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run REER ingestion")
    parser.add_argument("--country", type=str, help="Single country ISO3 code")
    parser.add_argument("--force", action="store_true", help="Fetch full 24-month history")
    args = parser.parse_args()

    countries = [args.country.upper()] if args.country else None

    with SessionLocal() as session:
        stats = run_reer_ingest(session, countries=countries, force=args.force)

    print(json.dumps(stats, indent=2, default=str))

    imf = stats["countries_imf_ifs"]
    bis = stats["countries_bis_fallback"]
    seed = stats["countries_seed_only"]
    err = stats["countries_error"]
    print(f"\nSummary: {imf} IFS, {bis} BIS, {seed} seed-only, {err} errors")


if __name__ == "__main__":
    main()
