"""REER ingester — IMF IFS primary, BIS fallback.

Fetches Real Effective Exchange Rate data and stores in reer_history.
Updates Country.fx_reer_deviation_pct with the latest observation.
"""

from __future__ import annotations

import csv
import io
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

IMF_IFS_URL = "https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/IFS/M.{iso2}.EREER_IX"
IMF_SERIES_CODES = ["EREER_IX", "EREER_IX_CPI"]

BIS_BULK_URL = "https://data.bis.org/static/bulk/WS_EER_D_csv_col.zip"


def _parse_imf_response(data: dict) -> list[dict[str, Any]]:
    """Extract observations from IMF SDMX-JSON response."""
    observations = []
    try:
        dataset = data.get("CompactData", {}).get("DataSet", {})
        series = dataset.get("Series", {})
        if not series:
            return []

        obs_list = series.get("Obs", [])
        if isinstance(obs_list, dict):
            obs_list = [obs_list]

        base = series.get("@BASE_YEAR", "2010")

        for obs in obs_list:
            period_str = obs.get("@TIME_PERIOD", "")
            value_str = obs.get("@OBS_VALUE", "")
            if not period_str or not value_str:
                continue
            try:
                year, month = period_str.split("-")
                period = date(int(year), int(month), 1)
                value = float(value_str)
                observations.append({"period": period, "value": value, "base_period": str(base)})
            except (ValueError, IndexError):
                continue
    except Exception:
        log.exception("imf_parse_error")
    return observations


def fetch_imf_ifs(iso3: str, months_back: int = 24) -> list[dict[str, Any]]:
    """Fetch REER from IMF IFS for a single country."""
    iso2 = ISO3_TO_ISO2.get(iso3)
    if not iso2:
        return []

    for series_code in IMF_SERIES_CODES:
        url = IMF_IFS_URL.format(iso2=iso2).replace("EREER_IX", series_code)
        try:
            resp = httpx.get(url, timeout=60, follow_redirects=True)
            if resp.status_code != 200:
                log.warning(
                    "imf_ifs_http_error", iso3=iso3, status=resp.status_code, series=series_code
                )
                continue

            data = resp.json()
            obs = _parse_imf_response(data)
            if obs:
                log.info("imf_ifs_fetched", iso3=iso3, series=series_code, count=len(obs))
                for o in obs:
                    o["source_series_id"] = f"IFS.M.{iso2}.{series_code}"
                return obs
        except httpx.TimeoutException:
            log.warning("imf_ifs_timeout", iso3=iso3, series=series_code)
        except Exception:
            log.exception("imf_ifs_error", iso3=iso3, series=series_code)

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

    stats = {
        "ran_at": datetime.now(UTC).isoformat(),
        "countries_attempted": len(countries),
        "countries_imf_ifs": 0,
        "countries_bis_fallback": 0,
        "countries_seed_only": 0,
        "countries_error": 0,
        "details": [],
    }

    now = datetime.now(UTC)
    imf_missed: list[str] = []

    # Step 1: Try IMF IFS for each country
    for iso3 in countries:
        try:
            obs = fetch_imf_ifs(iso3, months_back=24 if not force else 240)
            if obs:
                for o in obs:
                    stmt = (
                        insert(REERHistory)
                        .values(
                            iso3=iso3,
                            period=o["period"],
                            reer_index=o["value"],
                            base_period=o["base_period"],
                            source="imf_ifs",
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
                            source="imf_ifs",
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

                stats["countries_imf_ifs"] += 1
                stats["details"].append(
                    {
                        "iso3": iso3,
                        "source": "imf_ifs",
                        "latest_period": str(latest["period"]),
                        "deviation_pct": dev,
                    }
                )
                log.info(
                    "reer_ingested",
                    iso3=iso3,
                    source="imf_ifs",
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
