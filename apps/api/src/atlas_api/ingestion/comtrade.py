"""UN Comtrade ingester — annual trade data for 10 African countries.

Uses the Comtrade API v1 with HS 2-digit commodity classification.
Free tier: 500 requests/day. Each country×year = 4 requests.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from atlas_api.models import TradeAnnual

log = structlog.get_logger()

BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

COMTRADE_REPORTER_CODES = {
    "ETH": 231,
    "GHA": 288,
    "KEN": 404,
    "NGA": 566,
    "EGY": 818,
    "ZAF": 710,
    "RWA": 646,
    "MAR": 504,
    "SEN": 686,
    "CIV": 384,
}

# Reverse mapping for partner codes (common partners)
M49_TO_ISO3 = {
    156: "CHN",
    356: "IND",
    784: "ARE",
    840: "USA",
    276: "DEU",
    826: "GBR",
    528: "NLD",
    250: "FRA",
    724: "ESP",
    380: "ITA",
    682: "SAU",
    392: "JPN",
    56: "BEL",
    756: "CHE",
    76: "BRA",
    792: "TUR",
    643: "RUS",
    800: "UGA",
    586: "PAK",
    180: "COD",
    834: "TZA",
    466: "MLI",
    710: "ZAF",
    404: "KEN",
    566: "NGA",
    231: "ETH",
    288: "GHA",
    818: "EGY",
    504: "MAR",
    686: "SEN",
    384: "CIV",
    646: "RWA",
}


def _get_api_key() -> str:
    # Try config first (loads .env), then raw env var
    try:
        from atlas_api.config import settings

        key = getattr(settings, "comtrade_api_key", "") or os.environ.get("COMTRADE_API_KEY", "")
    except Exception:
        key = os.environ.get("COMTRADE_API_KEY", "")
    if not key:
        raise RuntimeError("COMTRADE_API_KEY not set")
    return key


def _fetch(
    http: httpx.Client,
    reporter_code: int,
    year: int,
    flow: str,
    cmd_code: str,
    partner_code: str = "0",
) -> list[dict[str, Any]]:
    """Single Comtrade API call. Returns parsed data rows."""
    params: dict[str, str] = {
        "reporterCode": str(reporter_code),
        "period": str(year),
        "flowCode": flow,
        "cmdCode": cmd_code,
        "maxRecords": "500",
    }
    if partner_code:
        params["partnerCode"] = partner_code
    headers = {"Ocp-Apim-Subscription-Key": _get_api_key()}

    for attempt in range(3):
        try:
            resp = http.get(BASE_URL, params=params, headers=headers, timeout=30)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "10"))
                log.warning("comtrade_rate_limited", retry_after=retry_after)
                time.sleep(retry_after)
                continue
            if resp.status_code != 200:
                log.warning("comtrade_http_error", status=resp.status_code, body=resp.text[:200])
                return []
            data = resp.json()
            return list(data.get("data", []))
        except httpx.TimeoutException:
            log.warning("comtrade_timeout", attempt=attempt)
            if attempt < 2:
                time.sleep(2**attempt)
        except Exception:
            log.exception("comtrade_fetch_error")
            return []
    return []


HS2_LABELS = {
    "01": "Live animals",
    "02": "Meat",
    "03": "Fish and crustaceans",
    "04": "Dairy, eggs, honey",
    "05": "Animal products n.e.s.",
    "06": "Live trees and cut flowers",
    "07": "Edible vegetables",
    "08": "Edible fruit and nuts",
    "09": "Coffee, tea, maté and spices",
    "10": "Cereals",
    "11": "Milling products",
    "12": "Oil seeds and oleaginous fruits",
    "13": "Lac; gums, resins",
    "14": "Vegetable plaiting materials",
    "15": "Animal or vegetable fats",
    "16": "Preparations of meat/fish",
    "17": "Sugars and confectionery",
    "18": "Cocoa and preparations",
    "19": "Preparations of cereals",
    "20": "Preparations of vegetables/fruit",
    "21": "Misc. edible preparations",
    "22": "Beverages",
    "23": "Food industry residues",
    "24": "Tobacco",
    "25": "Salt; sulphur; earths and stone",
    "26": "Ores, slag and ash",
    "27": "Mineral fuels, oils",
    "28": "Inorganic chemicals",
    "29": "Organic chemicals",
    "30": "Pharmaceutical products",
    "31": "Fertilizers",
    "39": "Plastics",
    "40": "Rubber and articles",
    "41": "Raw hides and skins",
    "44": "Wood and articles",
    "47": "Pulp of wood",
    "48": "Paper",
    "52": "Cotton",
    "61": "Articles of apparel (knitted)",
    "62": "Articles of apparel (not knitted)",
    "71": "Precious metals and stones",
    "72": "Iron and steel",
    "73": "Articles of iron/steel",
    "84": "Machinery",
    "85": "Electrical machinery",
    "87": "Vehicles (not railway)",
    "88": "Aircraft",
    "90": "Optical/medical instruments",
}


def _store_commodity_rows(
    session: Session, iso3: str, year: int, flow: str, rows: list[dict], now: datetime
) -> int:
    """Store commodity-level rows (exports/imports by HS2 chapter)."""
    count = 0
    for row in rows:
        code = str(row.get("cmdCode", "")).strip()
        if not code or code == "TOTAL":
            continue
        value = row.get("primaryValue") or row.get("fobvalue") or row.get("cifvalue")
        if value is None or value == 0:
            continue

        label = row.get("cmdDesc") or HS2_LABELS.get(code, f"HS {code}")

        stmt = (
            insert(TradeAnnual)
            .values(
                reporter_iso3=iso3,
                year=year,
                flow=flow,
                partner_iso3=None,
                partner_name=None,
                commodity_code=code,
                commodity_label=label,
                trade_value_usd=int(value),
                source="comtrade",
                source_period=str(year),
                ingested_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_trade_annual_row",
                set_={
                    "trade_value_usd": int(value),
                    "commodity_label": label,
                    "source": "comtrade",
                    "ingested_at": now,
                },
            )
        )
        session.execute(stmt)
        count += 1
    return count


M49_TO_NAME = {
    156: "China",
    356: "India",
    784: "UAE",
    840: "United States",
    276: "Germany",
    826: "United Kingdom",
    528: "Netherlands",
    250: "France",
    724: "Spain",
    380: "Italy",
    682: "Saudi Arabia",
    392: "Japan",
    56: "Belgium",
    756: "Switzerland",
    76: "Brazil",
    792: "Turkey",
    643: "Russia",
    800: "Uganda",
    586: "Pakistan",
    180: "DR Congo",
    834: "Tanzania",
    466: "Mali",
    710: "South Africa",
    404: "Kenya",
    566: "Nigeria",
    231: "Ethiopia",
    288: "Ghana",
    818: "Egypt",
    504: "Morocco",
    686: "Senegal",
    384: "Côte d'Ivoire",
    646: "Rwanda",
    410: "South Korea",
    764: "Thailand",
    360: "Indonesia",
    458: "Malaysia",
    704: "Vietnam",
}


def _store_partner_rows(
    session: Session, iso3: str, year: int, flow: str, rows: list[dict], now: datetime
) -> int:
    """Store partner-level rows (trade by partner country)."""
    count = 0
    for row in rows:
        partner_code = row.get("partnerCode") or row.get("partner2Code")
        if partner_code is None or int(partner_code) == 0:
            continue
        partner_iso = M49_TO_ISO3.get(int(partner_code))
        partner_name = row.get("partnerDesc") or M49_TO_NAME.get(int(partner_code), "")
        value = row.get("primaryValue") or row.get("fobvalue") or row.get("cifvalue")
        if value is None:
            continue

        stmt = (
            insert(TradeAnnual)
            .values(
                reporter_iso3=iso3,
                year=year,
                flow=flow,
                partner_iso3=partner_iso,
                partner_name=partner_name,
                commodity_code=None,
                commodity_label=None,
                trade_value_usd=int(value),
                source="comtrade",
                source_period=str(year),
                ingested_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_trade_annual_row",
                set_={
                    "trade_value_usd": int(value),
                    "partner_name": partner_name,
                    "source": "comtrade",
                    "ingested_at": now,
                },
            )
        )
        session.execute(stmt)
        count += 1
    return count


def backfill(
    session: Session,
    countries: list[str] | None = None,
    years: list[int] | None = None,
) -> dict[str, Any]:
    """Fetch trade data from Comtrade for specified countries × years."""
    if countries is None:
        countries = list(COMTRADE_REPORTER_CODES.keys())
    if years is None:
        years = [2020, 2021, 2022, 2023, 2024]

    stats: dict[str, int | list[str]] = {
        "countries": len(countries),
        "years": len(years),
        "requests": 0,
        "rows_written": 0,
        "errors": [],
    }

    now = datetime.now(UTC)
    total_requests = len(countries) * len(years) * 4
    log.info(
        "comtrade_backfill_start",
        countries=len(countries),
        years=years,
        estimated_requests=total_requests,
    )

    with httpx.Client() as http:
        for iso3 in countries:
            code = COMTRADE_REPORTER_CODES.get(iso3)
            if code is None:
                stats["errors"].append(f"{iso3}: no M49 code")
                continue

            for year in years:
                try:
                    # 1. Exports by commodity
                    time.sleep(0.2)
                    rows = _fetch(http, code, year, "X", "AG2")
                    stats["requests"] += 1
                    written = _store_commodity_rows(session, iso3, year, "X", rows, now)
                    stats["rows_written"] += written

                    # 2. Imports by commodity
                    time.sleep(0.2)
                    rows = _fetch(http, code, year, "M", "AG2")
                    stats["requests"] += 1
                    written = _store_commodity_rows(session, iso3, year, "M", rows, now)
                    stats["rows_written"] += written

                    # 3. Exports by partner (omit partnerCode to get breakdown)
                    time.sleep(0.2)
                    rows = _fetch(http, code, year, "X", "TOTAL", "")
                    stats["requests"] += 1
                    written = _store_partner_rows(session, iso3, year, "X", rows, now)
                    stats["rows_written"] += written

                    # 4. Imports by partner
                    time.sleep(0.2)
                    rows = _fetch(http, code, year, "M", "TOTAL", "")
                    stats["requests"] += 1
                    written = _store_partner_rows(session, iso3, year, "M", rows, now)
                    stats["rows_written"] += written

                    session.commit()
                    log.info(
                        "comtrade_country_year_done",
                        iso3=iso3,
                        year=year,
                        requests=stats["requests"],
                    )
                except Exception as e:
                    log.exception("comtrade_error", iso3=iso3, year=year)
                    stats["errors"].append(f"{iso3}/{year}: {e}")

    log.info("comtrade_backfill_complete", **{k: v for k, v in stats.items() if k != "errors"})
    return stats
