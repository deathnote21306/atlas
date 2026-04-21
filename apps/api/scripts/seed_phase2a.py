"""Seed Phase 2a fields (key_risks, key_opportunities, risk_decomposition, macro_annotations)."""

import json
from pathlib import Path

from atlas_api.db import SessionLocal
from atlas_api.models import Country

SEED_PATH = Path(__file__).resolve().parents[3] / "infra" / "seed" / "countries_phase2a.json"


def main() -> None:
    data = json.loads(SEED_PATH.read_text())
    with SessionLocal() as s:
        for iso3, fields in data.items():
            country = s.get(Country, iso3)
            if country is None:
                print(f"skip {iso3}: not found")
                continue
            country.key_risks = fields.get("key_risks")
            country.key_opportunities = fields.get("key_opportunities")
            country.risk_decomposition = fields.get("risk_decomposition")
            country.macro_annotations = fields.get("macro_annotations")
        s.commit()
        print(f"updated {len(data)} countries with Phase 2a fields")


if __name__ == "__main__":
    main()
