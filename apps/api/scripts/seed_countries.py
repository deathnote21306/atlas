"""Idempotent seed of the 10 prototype countries from infra/seed/countries.json."""

import json
from pathlib import Path

from atlas_api.db import SessionLocal
from atlas_api.models import Country
from sqlalchemy.dialects.postgresql import insert

SEED_PATH = Path(__file__).resolve().parents[3] / "infra" / "seed" / "countries.json"


def main() -> None:
    records = json.loads(SEED_PATH.read_text())
    with SessionLocal() as s:
        for r in records:
            stmt = insert(Country).values(**r).on_conflict_do_update(
                index_elements=["iso3"],
                set_={k: r[k] for k in r if k != "iso3"},
            )
            s.execute(stmt)
        s.commit()
        print(f"upserted {len(records)} countries")


if __name__ == "__main__":
    main()
