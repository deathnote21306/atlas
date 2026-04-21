"""Seed fallback trade data for all 10 countries (2024)."""

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert

import sys
sys.path.insert(0, "packages/schemas/src")
sys.path.insert(0, "apps/api/src")

from atlas_api.db import SessionLocal
from atlas_api.models import Country, TradeAnnual

TRADE_DATA = {
    "ETH": {
        "exports_total": 4250000000,
        "imports_total": 18300000000,
        "exports": [
            ("09", "Coffee, tea, maté and spices", 1487500000),
            ("12", "Oil seeds and oleaginous fruits", 765000000),
            ("71", "Precious metals and stones", 637500000),
            ("13", "Lac; gums, resins", 425000000),
            ("08", "Edible fruit and nuts", 340000000),
        ],
        "import_sources": [
            ("CHN", "China", 3660000000),
            ("IND", "India", 2745000000),
            ("ARE", "UAE", 1830000000),
            ("USA", "United States", 915000000),
            ("DEU", "Germany", 732000000),
        ],
        "export_partners": [
            ("CHN", "China", 510000000),
            ("IND", "India", 425000000),
            ("ARE", "UAE", 850000000),
            ("USA", "United States", 510000000),
            ("DEU", "Germany", 170000000),
        ],
    },
    "NGA": {
        "exports_total": 52000000000,
        "imports_total": 45000000000,
        "exports": [
            ("27", "Mineral fuels, oils", 44200000000),
            ("18", "Cocoa and preparations", 2080000000),
            ("40", "Rubber and articles", 1560000000),
            ("08", "Edible fruit and nuts", 520000000),
            ("71", "Precious metals and stones", 520000000),
        ],
        "import_sources": [
            ("CHN", "China", 13500000000),
            ("IND", "India", 5400000000),
            ("USA", "United States", 4500000000),
            ("NLD", "Netherlands", 3150000000),
            ("BEL", "Belgium", 2250000000),
        ],
        "export_partners": [
            ("IND", "India", 10400000000),
            ("ESP", "Spain", 7280000000),
            ("NLD", "Netherlands", 5200000000),
            ("USA", "United States", 3640000000),
            ("FRA", "France", 2600000000),
        ],
    },
    "GHA": {
        "exports_total": 17000000000,
        "imports_total": 15000000000,
        "exports": [
            ("71", "Precious metals and stones", 7650000000),
            ("18", "Cocoa and preparations", 4250000000),
            ("27", "Mineral fuels, oils", 2550000000),
            ("15", "Animal or vegetable fats", 340000000),
            ("08", "Edible fruit and nuts", 255000000),
        ],
        "import_sources": [
            ("CHN", "China", 4050000000),
            ("USA", "United States", 1500000000),
            ("GBR", "United Kingdom", 1200000000),
            ("IND", "India", 1050000000),
            ("NLD", "Netherlands", 900000000),
        ],
        "export_partners": [
            ("CHE", "Switzerland", 3400000000),
            ("IND", "India", 2550000000),
            ("CHN", "China", 1700000000),
            ("ARE", "UAE", 1360000000),
            ("ZAF", "South Africa", 850000000),
        ],
    },
    "KEN": {
        "exports_total": 7500000000,
        "imports_total": 19000000000,
        "exports": [
            ("09", "Coffee, tea, maté and spices", 1875000000),
            ("06", "Live trees and cut flowers", 1125000000),
            ("07", "Edible vegetables", 750000000),
            ("27", "Mineral fuels, oils", 525000000),
            ("62", "Articles of apparel (not knitted)", 375000000),
        ],
        "import_sources": [
            ("CHN", "China", 5700000000),
            ("IND", "India", 2850000000),
            ("ARE", "UAE", 1900000000),
            ("SAU", "Saudi Arabia", 1330000000),
            ("JPN", "Japan", 950000000),
        ],
        "export_partners": [
            ("UGA", "Uganda", 1125000000),
            ("USA", "United States", 750000000),
            ("NLD", "Netherlands", 675000000),
            ("GBR", "United Kingdom", 600000000),
            ("PAK", "Pakistan", 525000000),
        ],
    },
    "EGY": {
        "exports_total": 35000000000,
        "imports_total": 72000000000,
        "exports": [
            ("27", "Mineral fuels, oils", 10500000000),
            ("31", "Fertilizers", 3500000000),
            ("72", "Iron and steel", 2800000000),
            ("61", "Articles of apparel (knitted)", 2100000000),
            ("07", "Edible vegetables", 1750000000),
        ],
        "import_sources": [
            ("CHN", "China", 14400000000),
            ("SAU", "Saudi Arabia", 7200000000),
            ("USA", "United States", 5760000000),
            ("DEU", "Germany", 4320000000),
            ("RUS", "Russia", 3600000000),
        ],
        "export_partners": [
            ("TUR", "Turkey", 4900000000),
            ("ITA", "Italy", 3500000000),
            ("USA", "United States", 2800000000),
            ("SAU", "Saudi Arabia", 2450000000),
            ("IND", "India", 2100000000),
        ],
    },
    "ZAF": {
        "exports_total": 110000000000,
        "imports_total": 95000000000,
        "exports": [
            ("71", "Precious metals and stones", 22000000000),
            ("87", "Vehicles (not railway)", 13200000000),
            ("26", "Ores, slag and ash", 11000000000),
            ("72", "Iron and steel", 8800000000),
            ("27", "Mineral fuels, oils", 7700000000),
        ],
        "import_sources": [
            ("CHN", "China", 19000000000),
            ("DEU", "Germany", 9500000000),
            ("USA", "United States", 5700000000),
            ("IND", "India", 4750000000),
            ("SAU", "Saudi Arabia", 4750000000),
        ],
        "export_partners": [
            ("CHN", "China", 16500000000),
            ("USA", "United States", 8800000000),
            ("DEU", "Germany", 7700000000),
            ("JPN", "Japan", 5500000000),
            ("IND", "India", 5500000000),
        ],
    },
    "MAR": {
        "exports_total": 42000000000,
        "imports_total": 58000000000,
        "exports": [
            ("87", "Vehicles (not railway)", 8400000000),
            ("31", "Fertilizers", 6300000000),
            ("85", "Electrical machinery", 5460000000),
            ("62", "Articles of apparel (not knitted)", 3780000000),
            ("07", "Edible vegetables", 2940000000),
        ],
        "import_sources": [
            ("ESP", "Spain", 9860000000),
            ("FRA", "France", 8120000000),
            ("CHN", "China", 7540000000),
            ("USA", "United States", 4640000000),
            ("DEU", "Germany", 3480000000),
        ],
        "export_partners": [
            ("ESP", "Spain", 8820000000),
            ("FRA", "France", 8400000000),
            ("IND", "India", 3360000000),
            ("BRA", "Brazil", 2940000000),
            ("ITA", "Italy", 2520000000),
        ],
    },
    "RWA": {
        "exports_total": 1800000000,
        "imports_total": 4200000000,
        "exports": [
            ("09", "Coffee, tea, maté and spices", 450000000),
            ("26", "Ores, slag and ash", 396000000),
            ("71", "Precious metals and stones", 306000000),
            ("07", "Edible vegetables", 144000000),
            ("06", "Live trees and cut flowers", 90000000),
        ],
        "import_sources": [
            ("CHN", "China", 1008000000),
            ("IND", "India", 504000000),
            ("ARE", "UAE", 420000000),
            ("KEN", "Kenya", 336000000),
            ("TZA", "Tanzania", 252000000),
        ],
        "export_partners": [
            ("COD", "DR Congo", 360000000),
            ("ARE", "UAE", 270000000),
            ("CHE", "Switzerland", 180000000),
            ("USA", "United States", 126000000),
            ("BEL", "Belgium", 90000000),
        ],
    },
    "SEN": {
        "exports_total": 5500000000,
        "imports_total": 9500000000,
        "exports": [
            ("71", "Precious metals and stones", 1650000000),
            ("27", "Mineral fuels, oils", 825000000),
            ("03", "Fish and crustaceans", 715000000),
            ("25", "Salt; sulphur; earths and stone", 550000000),
            ("31", "Fertilizers", 385000000),
        ],
        "import_sources": [
            ("CHN", "China", 2375000000),
            ("FRA", "France", 1425000000),
            ("NGA", "Nigeria", 950000000),
            ("IND", "India", 665000000),
            ("TUR", "Turkey", 475000000),
        ],
        "export_partners": [
            ("MLI", "Mali", 825000000),
            ("CHE", "Switzerland", 660000000),
            ("IND", "India", 550000000),
            ("CHN", "China", 440000000),
            ("ESP", "Spain", 330000000),
        ],
    },
    "CIV": {
        "exports_total": 15000000000,
        "imports_total": 12000000000,
        "exports": [
            ("18", "Cocoa and preparations", 6000000000),
            ("08", "Edible fruit and nuts", 1500000000),
            ("40", "Rubber and articles", 1200000000),
            ("27", "Mineral fuels, oils", 1050000000),
            ("15", "Animal or vegetable fats", 750000000),
        ],
        "import_sources": [
            ("CHN", "China", 2640000000),
            ("FRA", "France", 1560000000),
            ("NGA", "Nigeria", 1440000000),
            ("IND", "India", 840000000),
            ("USA", "United States", 720000000),
        ],
        "export_partners": [
            ("NLD", "Netherlands", 2250000000),
            ("USA", "United States", 1650000000),
            ("DEU", "Germany", 1350000000),
            ("BEL", "Belgium", 1050000000),
            ("FRA", "France", 900000000),
        ],
    },
}


def compute_hhi(exports: list[tuple[str, str, int]], total: int) -> tuple[float, int, float]:
    """Return (hhi, score, commodity_dep_pct)."""
    if total == 0:
        return 0, 100, 0
    shares = [(val / total * 100) for _, _, val in exports]
    hhi = sum(s ** 2 for s in shares)
    # Add remaining share as "other"
    top_share = sum(shares)
    if top_share < 100:
        other = 100 - top_share
        hhi += other ** 2
    score = max(0, 100 - round(hhi / 100))
    # Commodity dependency: HS 01-27
    dep = sum(val for code, _, val in exports if code.isdigit() and int(code) <= 27) / total * 100
    return round(hhi, 1), score, round(dep, 1)


def main() -> None:
    now = datetime.now(UTC)
    year = 2024

    with SessionLocal() as s:
        for iso3, data in TRADE_DATA.items():
            total_exports = data["exports_total"]
            total_imports = data["imports_total"]

            # Exports by commodity
            for code, label, value in data["exports"]:
                stmt = insert(TradeAnnual).values(
                    reporter_iso3=iso3, year=year, flow="X",
                    partner_iso3=None, partner_name=None,
                    commodity_code=code, commodity_label=label,
                    trade_value_usd=value, source="seed", ingested_at=now,
                ).on_conflict_do_update(
                    constraint="uq_trade_annual_row",
                    set_={"trade_value_usd": value, "commodity_label": label, "source": "seed", "ingested_at": now},
                )
                s.execute(stmt)

            # Import sources (partner-level)
            for partner_iso, partner_name, value in data["import_sources"]:
                stmt = insert(TradeAnnual).values(
                    reporter_iso3=iso3, year=year, flow="M",
                    partner_iso3=partner_iso, partner_name=partner_name,
                    commodity_code=None, commodity_label=None,
                    trade_value_usd=value, source="seed", ingested_at=now,
                ).on_conflict_do_update(
                    constraint="uq_trade_annual_row",
                    set_={"trade_value_usd": value, "partner_name": partner_name, "source": "seed", "ingested_at": now},
                )
                s.execute(stmt)

            # Export partners
            for partner_iso, partner_name, value in data["export_partners"]:
                stmt = insert(TradeAnnual).values(
                    reporter_iso3=iso3, year=year, flow="X",
                    partner_iso3=partner_iso, partner_name=partner_name,
                    commodity_code=None, commodity_label=None,
                    trade_value_usd=value, source="seed", ingested_at=now,
                ).on_conflict_do_update(
                    constraint="uq_trade_annual_row",
                    set_={"trade_value_usd": value, "partner_name": partner_name, "source": "seed", "ingested_at": now},
                )
                s.execute(stmt)

            # Compute diversification
            hhi, div_score, dep_pct = compute_hhi(data["exports"], total_exports)

            country = s.get(Country, iso3)
            if country:
                country.economic_diversification_hhi = hhi
                country.economic_diversification_score = div_score
                country.economic_diversification_as_of = year
                country.commodity_dependency_pct = dep_pct

            print(f"{iso3}: HHI={hhi:.0f}, score={div_score}, dep={dep_pct:.0f}%, exports={total_exports/1e9:.1f}bn, imports={total_imports/1e9:.1f}bn")

        s.commit()
        print("Done")


if __name__ == "__main__":
    main()
