"""CLI: python -m atlas_api.ingestion.cli run [--source all|worldbank|imf|fx|ratings]"""

import argparse
import asyncio
import sys

from atlas_api.ingestion.fx import ExchangeRateHostIngester
from atlas_api.ingestion.imf import ImfWeoIngester
from atlas_api.ingestion.orchestrator import run_nightly
from atlas_api.ingestion.ratings import RatingsJsonLoader
from atlas_api.ingestion.worldbank import WorldBankIngester

FACTORIES = {
    "worldbank": WorldBankIngester,
    "imf": ImfWeoIngester,
    "fx": ExchangeRateHostIngester,
    "ratings": RatingsJsonLoader,
}


def main() -> int:
    parser = argparse.ArgumentParser(prog="atlas-ingestion")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run an ingestion pass")
    run.add_argument("--source", default="all", choices=["all", *FACTORIES.keys()])

    args = parser.parse_args()
    if args.cmd == "run":
        factories = None if args.source == "all" else [FACTORIES[args.source]]
        report = asyncio.run(run_nightly(factories=factories))
        print(report.model_dump_json(indent=2))
        return 0 if report.ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
