"""CLI for risk decomposition recomputation.

Usage:
    python -m atlas_api.services.risk.recompute [--country ISO3]
"""

import argparse
import json

from atlas_api.db import SessionLocal
from atlas_api.services.risk.compute_risk_decomposition import recompute_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute risk decomposition")
    parser.add_argument("--country", type=str, help="Single country ISO3")
    args = parser.parse_args()

    countries = [args.country.upper()] if args.country else None

    with SessionLocal() as session:
        stats = recompute_all(session, countries=countries)

    print(json.dumps(stats, indent=2, default=str))


if __name__ == "__main__":
    main()
