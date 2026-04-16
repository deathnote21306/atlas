"""ExchangeRate.host FX ingester — daily USD rates for our 9 country currencies.

Note: if ExchangeRate.host starts requiring a key (they moved to freemium),
set env var EXCHANGERATE_HOST_KEY and extend PARAMS. If the API is fully
gated, swap to Frankfurter (api.frankfurter.app) — same response shape.
"""

import os
import uuid
from datetime import UTC, date, datetime
from uuid import UUID

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert

from atlas_api.ingestion.base import Ingester, SourceStats
from atlas_api.models import FxRate
from atlas_api.services.country.indicators import ISO3_TO_CCY

log = structlog.get_logger()

BASE_URL = "https://api.exchangerate.host/latest"


class ExchangeRateHostIngester(Ingester):
    source_name = "exchangerate.host"

    async def run(self, vintage_id: UUID) -> SourceStats:
        stats = SourceStats(source=self.source_name)
        currencies = sorted(set(ISO3_TO_CCY.values()))
        params: dict[str, str] = {"base": "USD", "symbols": ",".join(currencies)}
        key = os.getenv("EXCHANGERATE_HOST_KEY")
        if key:
            params["access_key"] = key
        try:
            resp = await self.http.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as exc:
            stats.errors.append(str(exc))
            return stats

        rates = payload.get("rates") or {}
        obs_date_raw = payload.get("date")
        if obs_date_raw is None:
            stats.errors.append("missing date in response")
            return stats
        obs_date = date.fromisoformat(obs_date_raw)

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
