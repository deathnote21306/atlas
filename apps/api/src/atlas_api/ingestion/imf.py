"""IMF WEO DataMapper v1 ingester."""

import uuid
from datetime import UTC, date, datetime
from uuid import UUID

import httpx
import structlog

from atlas_api.ingestion.base import Ingester, SourceStats
from atlas_api.models import MacroIndicatorVintage
from atlas_api.services.country.indicators import IMF_WEO_CODES

log = structlog.get_logger()

BASE_URL = "https://www.imf.org/external/datamapper/api/v1/{indicator}/{iso3}"

COUNTRIES = ("CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY")


class ImfWeoIngester(Ingester):
    source_name = "imf_weo"

    async def run(self, vintage_id: UUID) -> SourceStats:
        stats = SourceStats(source=self.source_name)
        for iso3 in COUNTRIES:
            for indicator, imf_code in IMF_WEO_CODES.items():
                try:
                    rows = await self._fetch(iso3, imf_code)
                except httpx.HTTPError as exc:
                    stats.errors.append(f"{iso3}/{imf_code}: {exc}")
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

    async def _fetch(self, iso3: str, imf_code: str) -> list[dict[str, object]]:
        url = BASE_URL.format(indicator=imf_code, iso3=iso3)
        resp = await self.http.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        series = payload.get("values", {}).get(imf_code, {}).get(iso3, {})
        out: list[dict[str, object]] = []
        for period, val in series.items():
            try:
                sd: date | None = date(int(period), 12, 31)
            except ValueError:
                sd = None
            out.append({"period": str(period), "value": val, "source_date": sd})
        return out
