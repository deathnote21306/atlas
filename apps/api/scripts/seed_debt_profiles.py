"""Upsert debt_profile JSONB into Country rows from infra/seed/debt_profiles.json."""

import json
from pathlib import Path

from atlas_api.db import SessionLocal
from atlas_api.models import Country

SEED_PATH = Path(__file__).resolve().parents[3] / "infra" / "seed" / "debt_profiles.json"


def main() -> None:
    data = json.loads(SEED_PATH.read_text())
    with SessionLocal() as s:
        updated = 0
        for iso3, profile in data.items():
            country = s.get(Country, iso3.upper())
            if country is None:
                print(f"skip {iso3}: not found in database")
                continue
            country.debt_profile = profile
            updated += 1
        s.commit()
        print(f"updated {updated} countries with debt_profile data")


if __name__ == "__main__":
    main()
