"""REER ingester — IMF EER (api.imf.org SDMX 2.1) primary, BIS fallback.

Fetches Real Effective Exchange Rate data and stores in reer_history.
Updates Country.fx_reer_deviation_pct with the latest observation.
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, date, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from atlas_api.models import Country, REERHistory

log = structlog.get_logger()

ISO3_TO_ISO2 = {
    "ETH": "ET",
    "GHA": "GH",
    "KEN": "KE",
    "NGA": "NG",
    "EGY": "EG",
    "ZAF": "ZA",
    "RWA": "RW",
    "MAR": "MA",
    "SEN": "SN",
    "CIV": "CI",
}

# IMF dissemination SDMX 2.1 REST API (the legacy dataservices.imf.org
# SDMX-JSON service was decommissioned in 2025). The EER dataflow returns
# SDMX-ML StructureSpecificData keyed COUNTRY.INDICATOR.FREQUENCY with ISO3
# country codes; the CPI-based real effective exchange rate index (ref year
# 2010, all-country-weights basket) is REER_IX_RY2010_ACW_RCPI.
IMF_EER_BASE = "https://api.imf.org/external/sdmx/2.1"
IMF_EER_FLOW = "IMF.STA,EER,6.0.0"
IMF_REER_INDICATOR = "REER_IX_RY2010_ACW_RCPI"
IMF_EER_BASE_YEAR = "2010"

BIS_BULK_URL = "https://data.bis.org/static/bulk/WS_EER_D_csv_col.zip"


def _eer_data_url(iso3: str, start_period: str) -> str:
    """Build the SDMX 2.1 data query URL for a country's monthly REER series."""
    key = f"{iso3}.{IMF_REER_INDICATOR}.M"
    return f"{IMF_EER_BASE}/data/{IMF_EER_FLOW}/{key}?startPeriod={start_period}"


def _parse_eer_period(time_period: str) -> date | None:
    """Parse an SDMX monthly period like '2024-M04' into a date (first of month)."""
    try:
        year, month = time_period.split("-M")
        return date(int(year), int(month), 1)
    except (ValueError, IndexError):
        return None


def _local_name(tag: str) -> str:
    """Strip the XML namespace from an ElementTree tag."""
    return tag.rsplit("}", 1)[-1]


def _parse_eer_xml(text: str) -> list[dict[str, Any]]:
    """Extract observations from an IMF EER SDMX-ML StructureSpecificData response."""
    observations: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        log.warning("eer_xml_parse_error")
        return []

    for series in root.iter():
        if _local_name(series.tag) != "Series":
            continue
        indicator = series.attrib.get("INDICATOR", IMF_REER_INDICATOR)
        for obs in series:
            if _local_name(obs.tag) != "Obs":
                continue
            period = _parse_eer_period(obs.attrib.get("TIME_PERIOD", ""))
            value_str = obs.attrib.get("OBS_VALUE", "")
            if period is None or not value_str:
                continue
            try:
                value = float(value_str)
            except ValueError:
                continue
            observations.append(
                {
                    "period": period,
                    "value": value,
                    "base_period": IMF_EER_BASE_YEAR,
                    "indicator": indicator,
                }
            )
    return observations


def fetch_imf_eer(iso3: str, months_back: int = 24) -> list[dict[str, Any]]:
    """Fetch monthly REER from the IMF EER dataflow for a single country (ISO3)."""
    today = date.today()
    start_month = today.month - (months_back % 12)
    start_year = today.year - (months_back // 12)
    if start_month <= 0:
        start_month += 12
        start_year -= 1
    start_period = f"{start_year:04d}-{start_month:02d}"

    url = _eer_data_url(iso3, start_period)
    try:
        resp = httpx.get(url, timeout=60, follow_redirects=True)
        if resp.status_code != 200:
            log.warning("imf_eer_http_error", iso3=iso3, status=resp.status_code)
            return []

        obs = _parse_eer_xml(resp.text)
        for o in obs:
            indicator = o.pop("indicator", IMF_REER_INDICATOR)
            o["source_series_id"] = f"IMF.STA.EER.{iso3}.{indicator}.M"
        if obs:
            log.info("imf_eer_fetched", iso3=iso3, count=len(obs))
        return obs
    except httpx.TimeoutException:
        log.warning("imf_eer_timeout", iso3=iso3)
    except Exception:
        log.exception("imf_eer_error", iso3=iso3)

    return []


def fetch_bis_bulk(iso3_list: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Fetch BIS bulk REER CSV and extract data for requested countries."""
    result: dict[str, list[dict[str, Any]]] = {iso3: [] for iso3 in iso3_list}
    try:
        resp = httpx.get(BIS_BULK_URL, timeout=120, follow_redirects=True)
        if resp.status_code != 200:
            log.warning("bis_bulk_http_error", status=resp.status_code)
            return result

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
            if not csv_names:
                log.warning("bis_bulk_no_csv")
                return result

            with zf.open(csv_names[0]) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    freq = row.get("FREQ", "")
                    eer_type = row.get("EER_TYPE", row.get("TYPE", ""))
                    ref_area = row.get("REF_AREA", "")

                    if freq != "M" or ref_area not in iso3_list:
                        continue
                    if eer_type not in ("R", "B"):
                        continue

                    period_str = row.get("TIME_PERIOD", "")
                    value_str = row.get("OBS_VALUE", "")
                    if not period_str or not value_str:
                        continue

                    try:
                        year, month = period_str.split("-")
                        period = date(int(year), int(month), 1)
                        value = float(value_str)
                        result[ref_area].append(
                            {
                                "period": period,
                                "value": value,
                                "base_period": "2010",
                                "source_series_id": f"BIS.WS_EER.M.{ref_area}.{eer_type}",
                            }
                        )
                    except (ValueError, IndexError):
                        continue

        for iso3 in result:
            if result[iso3]:
                log.info("bis_fetched", iso3=iso3, count=len(result[iso3]))
    except httpx.TimeoutException:
        log.warning("bis_bulk_timeout")
    except Exception:
        log.exception("bis_bulk_error")

    return result


def compute_deviation(session: Session, iso3: str, latest_index: float) -> float | None:
    """Compute REER deviation from 10-year trailing mean."""
    ten_years_ago = date(date.today().year - 10, date.today().month, 1)
    avg = session.execute(
        select(func.avg(REERHistory.reer_index)).where(
            REERHistory.iso3 == iso3, REERHistory.period >= ten_years_ago
        )
    ).scalar()

    if avg is None or float(avg) == 0:
        return None
    return round((latest_index / float(avg) - 1) * 100, 2)


def run_reer_ingest(
    session: Session,
    countries: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Run REER ingestion for specified countries (or all 10)."""
    if countries is None:
        countries = list(ISO3_TO_ISO2.keys())

    stats: dict[str, Any] = {
        "ran_at": datetime.now(UTC).isoformat(),
        "countries_attempted": len(countries),
        "countries_imf_eer": 0,
        "countries_bis_fallback": 0,
        "countries_seed_only": 0,
        "countries_error": 0,
        "details": [],
    }

    now = datetime.now(UTC)
    imf_missed: list[str] = []

    # Step 1: Try IMF EER (api.imf.org SDMX 2.1) for each country
    for iso3 in countries:
        try:
            obs = fetch_imf_eer(iso3, months_back=24 if not force else 240)
            if obs:
                for o in obs:
                    stmt = (
                        insert(REERHistory)
                        .values(
                            iso3=iso3,
                            period=o["period"],
                            reer_index=o["value"],
                            base_period=o["base_period"],
                            source="imf_eer",
                            source_series_id=o.get("source_series_id"),
                            fetched_at=now,
                        )
                        .on_conflict_do_nothing(constraint="uq_reer_country_period_source")
                    )
                    session.execute(stmt)

                # Compute deviation for latest observation
                latest = max(obs, key=lambda x: x["period"])
                dev = compute_deviation(session, iso3, latest["value"])
                if dev is not None:
                    stmt = (
                        insert(REERHistory)
                        .values(
                            iso3=iso3,
                            period=latest["period"],
                            reer_index=latest["value"],
                            reer_deviation_pct=dev,
                            base_period=latest["base_period"],
                            source="imf_eer",
                            source_series_id=latest.get("source_series_id"),
                            fetched_at=now,
                        )
                        .on_conflict_do_update(
                            constraint="uq_reer_country_period_source",
                            set_={"reer_deviation_pct": dev},
                        )
                    )
                    session.execute(stmt)

                # Update Country cache
                country = session.get(Country, iso3)
                if country:
                    country.fx_reer_deviation_pct = dev
                    country.fx_reer_as_of = datetime.combine(
                        latest["period"], datetime.min.time(), tzinfo=UTC
                    )

                stats["countries_imf_eer"] += 1
                stats["details"].append(
                    {
                        "iso3": iso3,
                        "source": "imf_eer",
                        "latest_period": str(latest["period"]),
                        "deviation_pct": dev,
                    }
                )
                log.info(
                    "reer_ingested",
                    iso3=iso3,
                    source="imf_eer",
                    period=str(latest["period"]),
                    deviation=dev,
                )
            else:
                imf_missed.append(iso3)
        except Exception:
            log.exception("reer_ingest_error", iso3=iso3)
            imf_missed.append(iso3)
            stats["countries_error"] += 1

    session.commit()

    # Step 2: BIS fallback for missed countries
    if imf_missed:
        log.info("reer_bis_fallback", countries=imf_missed)
        try:
            bis_data = fetch_bis_bulk(imf_missed)
            for iso3 in imf_missed:
                obs = bis_data.get(iso3, [])
                if obs:
                    source = "bis_broad"
                    for o in obs:
                        stmt = (
                            insert(REERHistory)
                            .values(
                                iso3=iso3,
                                period=o["period"],
                                reer_index=o["value"],
                                base_period=o["base_period"],
                                source=source,
                                source_series_id=o.get("source_series_id"),
                                fetched_at=now,
                            )
                            .on_conflict_do_nothing(constraint="uq_reer_country_period_source")
                        )
                        session.execute(stmt)

                    latest = max(obs, key=lambda x: x["period"])
                    dev = compute_deviation(session, iso3, latest["value"])

                    country = session.get(Country, iso3)
                    if country and dev is not None:
                        country.fx_reer_deviation_pct = dev
                        country.fx_reer_as_of = datetime.combine(
                            latest["period"], datetime.min.time(), tzinfo=UTC
                        )

                    stats["countries_bis_fallback"] += 1
                    stats["details"].append(
                        {
                            "iso3": iso3,
                            "source": source,
                            "latest_period": str(latest["period"]),
                            "deviation_pct": dev,
                        }
                    )
                else:
                    stats["countries_seed_only"] += 1
                    stats["details"].append(
                        {
                            "iso3": iso3,
                            "source": "seed",
                            "latest_period": None,
                            "deviation_pct": None,
                        }
                    )
                    log.warning("reer_no_source", iso3=iso3)

            session.commit()
        except Exception:
            log.exception("reer_bis_fallback_error")
            for iso3 in imf_missed:
                if not any(d["iso3"] == iso3 for d in stats["details"]):
                    stats["countries_seed_only"] += 1
                    stats["details"].append(
                        {
                            "iso3": iso3,
                            "source": "seed",
                            "latest_period": None,
                            "deviation_pct": None,
                        }
                    )

    log.info("reer_ingest_complete", **{k: v for k, v in stats.items() if k != "details"})
    return stats
