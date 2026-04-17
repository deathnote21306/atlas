"""FX ingester — daily USD rates for our 9 country currencies.

Uses open.er-api.com (free, no key, full African currency coverage).
ExchangeRate.host was the original source but moved to mandatory API keys.
"""

import uuid
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert

from atlas_api.ingestion.base import Ingester, SourceStats
from atlas_api.models import FxRate
from atlas_api.services.country.indicators import ISO3_TO_CCY

log = structlog.get_logger()

BASE_URL = "https://open.er-api.com/v6/latest/USD"


class ExchangeRateHostIngester(Ingester):
    source_name = "open.er-api.com"

    async def run(self, vintage_id: UUID) -> SourceStats:
        stats = SourceStats(source=self.source_name)
        try:
            resp = await self.http.get(BASE_URL, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as exc:
            stats.errors.append(str(exc))
            return stats

        rates = payload.get("rates") or {}
        ts = payload.get("time_last_update_unix")
        if ts is None:
            stats.errors.append("missing date in response")
            return stats
        obs_date = datetime.fromtimestamp(int(ts), tz=UTC).date()

        now = datetime.now(UTC)
        for iso3, ccy in ISO3_TO_CCY.items():
            rate = rates.get(ccy)
            if rate is None:
                stats.rows_skipped += 1
                continue
            if rate == 0:
                stats.errors.append(f"{iso3}/{ccy}: zero rate")
                continue
            # payload.rates[ccy] is CCY per USD; we store usd_per_ccy, so invert.
            usd_per_ccy = 1.0 / float(rate)
            stmt = insert(FxRate).values(
                id=uuid.uuid4(),
                iso3=iso3,
                ccy=ccy,
                usd_per_ccy=usd_per_ccy,
                observation_date=obs_date,
                source=self.source_name,
                ingested_at=now,
            ).on_conflict_do_update(
                constraint="uq_fx_daily",
                set_={
                    "usd_per_ccy": usd_per_ccy,
                    "source": self.source_name,
                    "ingested_at": now,
                },
            )
            self.session.execute(stmt)
            stats.rows_written += 1
        self.session.commit()
        return stats
