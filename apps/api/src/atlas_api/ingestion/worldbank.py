"""World Bank v2 API ingester for our 12 macro indicators × 10 countries."""

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

import httpx
import structlog

from atlas_api.ingestion.base import Ingester, SourceStats
from atlas_api.models import MacroIndicatorVintage
from atlas_api.services.country.indicators import WORLDBANK_CODES

log = structlog.get_logger()

BASE_URL = "https://api.worldbank.org/v2/country/{iso3}/indicator/{code}"
PARAMS = {"format": "json", "date": "2020:2026", "per_page": "500"}

COUNTRIES = ("CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY")


class WorldBankIngester(Ingester):
    source_name = "worldbank"

    async def run(self, vintage_id: UUID) -> SourceStats:
        stats = SourceStats(source=self.source_name)
        for iso3 in COUNTRIES:
            for indicator, wb_code in WORLDBANK_CODES.items():
                try:
                    rows = await self._fetch(iso3, wb_code)
                except httpx.HTTPError as exc:
                    stats.errors.append(f"{iso3}/{wb_code}: {exc}")
                    continue
                for obs in rows:
                    self.session.add(MacroIndicatorVintage(
                        id=uuid.uuid4(),
                        iso3=iso3,
                        indicator=indicator.value,
                        value=obs["value"],
                        source=self.source_name,
                        source_date=obs["source_date"],
                        ingested_at=datetime.now(UTC),
                        period=obs["period"],
                        vintage_id=vintage_id,
                    ))
                    stats.rows_written += 1
        self.session.commit()
        return stats

    async def _fetch(self, iso3: str, wb_code: str) -> list[dict[str, object]]:
        url = BASE_URL.format(iso3=iso3, code=wb_code)
        resp = await self.http.get(url, params=PARAMS, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return []
        observations = payload[1] or []
        out: list[dict[str, object]] = []
        for o in observations:
            period = o.get("date")
            if not period:
                continue
            # source_date: last day of year for annual data
            try:
                sd: date | None = date(int(period), 12, 31)
            except ValueError:
                sd = None
            out.append({"period": period, "value": o.get("value"), "source_date": sd})
        return out
