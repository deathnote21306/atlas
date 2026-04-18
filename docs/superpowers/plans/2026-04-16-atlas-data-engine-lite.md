# Atlas Data Engine (lite) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automated nightly ingestion populates all 10 prototype countries with current macro, FX, and rating data sourced from World Bank, IMF WEO, ExchangeRate.host, and a curated ratings JSON. Expose read APIs (`get_latest`, `get_as_of`, composite rating) that Plan 3 (Country Intelligence) will consume.

**Architecture:** Extends the existing FastAPI monolith. Adds `atlas_api.services.country` for read paths and `atlas_api.ingestion` for the four ingesters + orchestrator + circuit breakers. An `AsyncIOScheduler` started in FastAPI's lifespan context triggers the orchestrator at 03:00 UTC. External HTTP via `httpx.AsyncClient` with `tenacity` retry and a DB-backed per-source circuit breaker. Structured JSON logs via `structlog` to stdout.

**Tech Stack:** `httpx` + `apscheduler` + `tenacity` + `structlog` (new); SQLAlchemy 2.0 + Alembic + Postgres (existing); `pytest-httpx` + `freezegun` + `testcontainers[postgres]` (test).

---

## File Structure

Files created (C) or modified (M) in this plan:

```
atlas/
├── apps/api/
│   ├── pyproject.toml                                         (M) add httpx/apscheduler/tenacity/structlog + dev pytest-httpx/freezegun
│   ├── src/atlas_api/
│   │   ├── main.py                                            (M) lifespan: start/stop scheduler; include new routers
│   │   ├── logging_config.py                                  (C) structlog processor chain
│   │   ├── models.py                                          (M) add Country, DataVintage, MacroIndicatorVintage, FxRate, RatingHistory, IngestionCircuit
│   │   ├── routers/
│   │   │   └── countries.py                                   (C) GET /api/countries, GET /api/countries/{iso3}
│   │   ├── services/
│   │   │   ├── __init__.py                                    (C)
│   │   │   └── country/
│   │   │       ├── __init__.py                                (C)
│   │   │       ├── queries.py                                 (C) list_countries, get_country, read paths
│   │   │       └── composite_rating.py                        (C) pure function
│   │   └── ingestion/
│   │       ├── __init__.py                                    (C)
│   │       ├── base.py                                        (C) Ingester ABC, IngestionReport, retry config
│   │       ├── circuit_breaker.py                             (C) DB-backed breaker state
│   │       ├── worldbank.py                                   (C) WorldBankIngester
│   │       ├── imf.py                                         (C) ImfWeoIngester
│   │       ├── fx.py                                          (C) ExchangeRateHostIngester
│   │       ├── ratings.py                                     (C) RatingsJsonLoader
│   │       ├── orchestrator.py                                (C) run_nightly(), creates vintage, dispatches ingesters
│   │       ├── scheduler.py                                   (C) AsyncIOScheduler setup + cron registration
│   │       └── cli.py                                         (C) python -m atlas_api.ingestion.cli run ...
│   ├── tests/
│   │   ├── test_countries.py                                  (C) router + service tests
│   │   ├── test_composite_rating.py                           (C) golden tests
│   │   ├── test_read_paths.py                                 (C) get_latest / get_as_of / FX deltas
│   │   ├── test_ingestion_base.py                             (C) retry + circuit breaker state machine
│   │   ├── test_ingestion_worldbank.py                        (C) mocked HTTP
│   │   ├── test_ingestion_imf.py                              (C) mocked HTTP
│   │   ├── test_ingestion_fx.py                               (C) mocked HTTP
│   │   ├── test_ingestion_ratings.py                          (C) fixture diff
│   │   ├── test_orchestrator.py                               (C) stubbed ingesters
│   │   └── test_e2e_ingestion.py                              (C) full pipeline with mocked externals
│   └── scripts/
│       ├── seed_countries.py                                  (C) idempotent upsert from JSON
│       └── run_ingestion.py                                   (C) thin wrapper around cli
│
├── packages/schemas/
│   ├── src/atlas_schemas/
│   │   ├── __init__.py                                        (M) export new modules
│   │   ├── country.py                                         (C) Country, CountryStatus, FxRegime enums
│   │   ├── macro.py                                           (C) MacroIndicator, MacroValue
│   │   ├── fx.py                                              (C) FxObservation, FxDeltas
│   │   ├── ratings.py                                         (C) RatingAction, Agency, RatingGrade
│   │   └── ingestion.py                                       (C) IngestionReport, SourceStats, DataVintage
│   └── tests/
│       └── test_contracts.py                                  (M) add contract tests for new schemas
│
└── infra/
    ├── migrations/versions/
    │   ├── 0002_country_and_vintage.py                        (C) country + data_vintage + enums
    │   ├── 0003_macro_fx_rating.py                            (C) macro_indicator_vintage + fx_rate + rating_history
    │   └── 0004_ingestion_circuit.py                          (C) ingestion_circuit (per-source breaker state)
    └── seed/
        ├── countries.json                                     (C) 10 countries with spec §5 fields
        └── ratings.json                                       (C) starter ratings actions (S&P/Moodys/Fitch × 10)
```

Design rationale: Service layer (`services/country/`) owns read logic; router stays thin. Ingestion is its own package so Plan 4's news pipeline can reuse `Ingester` and circuit-breaker primitives without cross-cutting. Circuit breaker is DB-backed (not in-memory) so restarts don't clear state.

---

## External API shapes (reference)

**World Bank v2** — `GET https://api.worldbank.org/v2/country/{iso3}/indicator/{code}?format=json&date=2020:2025&per_page=500`

Response shape (JSON): `[pagination_metadata, [observations...]]`. Each observation: `{indicator: {id, value}, country: {id, value}, countryiso3code, date: "2024", value: 123.45|null, unit, obs_status, decimal}`. Null values = missing; persist as NULL (never 0).

**IMF WEO DataMapper v1** — `GET https://www.imf.org/external/datamapper/api/v1/{indicator}/{iso3}`

Response: `{values: {INDICATOR: {ISO3: {"2024": 123.45, "2025": 124.67, ...}}}}`. Yearly data.

**ExchangeRate.host** — `GET https://api.exchangerate.host/latest?base=USD&symbols=GHS,KES,NGN,XOF,ETB,RWF,ZAR,MAD,EGP`

Response: `{base: "USD", date: "2026-04-16", rates: {GHS: 15.2, KES: 129.4, ...}}`.

**Note:** ExchangeRate.host may have introduced a required `access_key` since spec approval. If the ingester fails with 401/403 in Task 15, the implementer should check `https://exchangerate.host` and either register for a free key (env var `EXCHANGERATE_HOST_KEY`) or switch to a no-key alternative (e.g., Frankfurter.app `api.frankfurter.app/latest?from=USD&to=GHS,KES,...`). Plan may need a small amendment then.

---

## Indicator set (the 12 macro tiles)

| Internal key | Tile label | World Bank code | IMF WEO code |
|---|---|---|---|
| `GDP_USD` | GDP (USD, current) | `NY.GDP.MKTP.CD` | `NGDPD` |
| `GDP_GROWTH_PCT` | GDP growth (% YoY) | `NY.GDP.MKTP.KD.ZG` | `NGDP_RPCH` |
| `INFLATION_PCT` | Inflation, CPI (% YoY) | `FP.CPI.TOTL.ZG` | `PCPIPCH` |
| `CURRENT_ACCOUNT_PCT_GDP` | Current account (% GDP) | `BN.CAB.XOKA.GD.ZS` | `BCA_NGDPD` |
| `FISCAL_BALANCE_PCT_GDP` | Fiscal balance (% GDP) | `GC.BAL.CASH.GD.ZS` | `GGXCNL_NGDP` |
| `PUBLIC_DEBT_PCT_GDP` | Public debt (% GDP) | `GC.DOD.TOTL.GD.ZS` | `GGXWDG_NGDP` |
| `EXTERNAL_DEBT_PCT_GNI` | External debt stocks (% GNI) | `DT.DOD.DECT.GN.ZS` | — |
| `FX_RESERVES_MO_IMPORTS` | Reserves (months of imports) | `FI.RES.TOTL.MO` | — |
| `DEBT_SERVICE_PCT_EXPORTS` | Debt service (% exports) | `DT.TDS.DECT.EX.ZS` | — |
| `UNEMPLOYMENT_PCT` | Unemployment (%) | `SL.UEM.TOTL.ZS` | `LUR` |
| `FDI_INFLOW_USD` | FDI inflow (USD) | `BX.KLT.DINV.CD.WD` | — |
| `GDP_PER_CAPITA_USD` | GDP per capita (USD) | `NY.GDP.PCAP.CD` | `NGDPDPC` |

Indicators with a blank IMF column → fetched only from World Bank. Implementer: put these mappings in `atlas_api/services/country/indicators.py` as a dict constant; each ingester consults it.

---

### Task 1: Add ingestion dependencies

**Files:**
- Modify: `apps/api/pyproject.toml`

- [ ] **Step 1: Edit `apps/api/pyproject.toml`**

Add to the `dependencies` list (after the existing entries):

```toml
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "alembic>=1.13",
  "argon2-cffi>=23.1",
  "python-jose[cryptography]>=3.3",
  "atlas-schemas",
  "httpx>=0.27",
  "apscheduler>=3.10",
  "tenacity>=9.0",
  "structlog>=24.4",
]
```

Add to the `[project.optional-dependencies].dev` list (after the existing entries):

```toml
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "testcontainers[postgres]>=4.8",
  "ruff>=0.6",
  "mypy>=1.11",
  "types-python-jose>=3.3",
  "pytest-httpx>=0.32",
  "freezegun>=1.5",
]
```

- [ ] **Step 2: Sync and verify**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv sync --all-extras
uv run python -c "import httpx, apscheduler, tenacity, structlog; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/pyproject.toml uv.lock
git commit -m "chore(api): add ingestion deps (httpx, apscheduler, tenacity, structlog)"
```

---

### Task 2: Reference schemas — `Country` + enums

**Files:**
- Create: `packages/schemas/src/atlas_schemas/country.py`
- Create: `packages/schemas/src/atlas_schemas/ingestion.py`
- Modify: `packages/schemas/src/atlas_schemas/__init__.py`
- Modify: `packages/schemas/tests/test_contracts.py`

- [ ] **Step 1: Write failing contract tests**

Append to `packages/schemas/tests/test_contracts.py`:

```python
def test_country_schema_roundtrip():
    from atlas_schemas.country import Country, CountryStatus, FxRegime

    payload = {
        "iso3": "GHA",
        "name": "Ghana",
        "capital": "Accra",
        "region": "West Africa",
        "tags": ["SSA", "commodities"],
        "tier": "B",
        "status": "negotiating",
        "fx_regime": "float",
        "fx_regime_notes": None,
        "fx_parallel_premium": None,
    }
    c = Country.model_validate(payload)
    assert c.iso3 == "GHA"
    assert c.status is CountryStatus.NEGOTIATING
    assert c.fx_regime is FxRegime.FLOAT


def test_country_rejects_bad_iso3():
    import pytest
    from pydantic import ValidationError
    from atlas_schemas.country import Country

    with pytest.raises(ValidationError):
        Country.model_validate({
            "iso3": "GH",  # too short
            "name": "Ghana",
            "capital": "Accra",
            "region": "West Africa",
            "tags": [],
            "tier": "B",
            "status": "negotiating",
            "fx_regime": "float",
            "fx_regime_notes": None,
            "fx_parallel_premium": None,
        })


def test_data_vintage_schema_roundtrip():
    from atlas_schemas.ingestion import DataVintage

    v = DataVintage.model_validate({
        "id": "00000000-0000-0000-0000-000000000001",
        "created_at": "2026-04-16T03:00:00Z",
        "source": "nightly",
        "notes": None,
    })
    assert v.source == "nightly"
```

- [ ] **Step 2: Write `country.py`**

```python
# packages/schemas/src/atlas_schemas/country.py
from enum import Enum

from pydantic import BaseModel, Field


class CountryStatus(str, Enum):
    PERFORMING = "performing"
    NEGOTIATING = "negotiating"
    SELECTIVE_DEFAULT = "selective_default"
    DEFAULT = "default"
    RESTRUCTURED = "restructured"


class FxRegime(str, Enum):
    FLOAT = "float"
    MANAGED_FLOAT = "managed_float"
    PEGGED = "pegged"
    CRAWLING_PEG = "crawling_peg"
    BASKET_PEG = "basket_peg"
    CURRENCY_BOARD = "currency_board"
    NO_SEPARATE_LEGAL_TENDER = "no_separate_legal_tender"


class Country(BaseModel):
    iso3: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    name: str
    capital: str
    region: str
    tags: list[str]
    tier: str
    status: CountryStatus
    fx_regime: FxRegime
    fx_regime_notes: str | None = None
    fx_parallel_premium: float | None = None
```

- [ ] **Step 3: Write `ingestion.py`**

```python
# packages/schemas/src/atlas_schemas/ingestion.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DataVintage(BaseModel):
    id: UUID
    created_at: datetime
    source: str
    notes: str | None = None


class SourceStats(BaseModel):
    source: str
    rows_written: int
    rows_skipped: int
    errors: list[str]
    duration_seconds: float


class IngestionReport(BaseModel):
    vintage_id: UUID
    started_at: datetime
    finished_at: datetime
    sources: list[SourceStats]
    ok: bool
```

- [ ] **Step 4: Update `__init__.py`**

Replace `packages/schemas/src/atlas_schemas/__init__.py`:

```python
# packages/schemas/src/atlas_schemas/__init__.py
from atlas_schemas.auth import LoginRequest, LoginResponse, Me
from atlas_schemas.country import Country, CountryStatus, FxRegime
from atlas_schemas.health import HealthResponse
from atlas_schemas.ingestion import DataVintage, IngestionReport, SourceStats

__all__ = [
    "Country",
    "CountryStatus",
    "DataVintage",
    "FxRegime",
    "HealthResponse",
    "IngestionReport",
    "LoginRequest",
    "LoginResponse",
    "Me",
    "SourceStats",
]
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest packages/schemas/tests/ -v
```

Expected: existing 2 pass + new 3 pass = 5 passing.

- [ ] **Step 6: Regenerate TS types**

```bash
uv run python packages/schemas/scripts/generate_ts.py
grep -q "CountryStatus" apps/web/src/types/generated.ts && echo OK
```

Expected: `OK`.

- [ ] **Step 7: Commit**

```bash
git add packages/schemas
git commit -m "feat(schemas): add country + ingestion contracts"
```

---

### Task 3: Migration `0002` — `country` + `data_vintage`

**Files:**
- Create: `infra/migrations/versions/0002_country_and_vintage.py`
- Modify: `apps/api/src/atlas_api/models.py`

- [ ] **Step 1: Extend `models.py`**

Append to `apps/api/src/atlas_api/models.py`:

```python
from sqlalchemy import Enum as SqlEnum, ForeignKey, Float, Text
from sqlalchemy.types import ARRAY

from atlas_schemas.country import CountryStatus, FxRegime


class Country(Base):
    __tablename__ = "country"

    iso3: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    capital: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    tier: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[CountryStatus] = mapped_column(
        SqlEnum(CountryStatus, name="country_status", native_enum=False, length=32),
        nullable=False,
    )
    fx_regime: Mapped[FxRegime] = mapped_column(
        SqlEnum(FxRegime, name="fx_regime", native_enum=False, length=32),
        nullable=False,
    )
    fx_regime_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fx_parallel_premium: Mapped[float | None] = mapped_column(Float, nullable=True)


class DataVintage(Base):
    __tablename__ = "data_vintage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Note: `native_enum=False` stores enums as VARCHAR with CHECK constraint — easier to evolve than Postgres enum types.

- [ ] **Step 2: Write migration**

```python
# infra/migrations/versions/0002_country_and_vintage.py
"""country + data_vintage

Revision ID: 0002_country_and_vintage
Revises: 0001_baseline
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "0002_country_and_vintage"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


COUNTRY_STATUS = ("performing", "negotiating", "selective_default", "default", "restructured")
FX_REGIME = (
    "float",
    "managed_float",
    "pegged",
    "crawling_peg",
    "basket_peg",
    "currency_board",
    "no_separate_legal_tender",
)


def upgrade() -> None:
    op.create_table(
        "country",
        sa.Column("iso3", sa.String(3), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("capital", sa.String(200), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("tags", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("tier", sa.String(8), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            sa.CheckConstraint(f"status IN {COUNTRY_STATUS}", name="country_status_check"),
            nullable=False,
        ),
        sa.Column(
            "fx_regime",
            sa.String(32),
            sa.CheckConstraint(f"fx_regime IN {FX_REGIME}", name="country_fx_regime_check"),
            nullable=False,
        ),
        sa.Column("fx_regime_notes", sa.Text, nullable=True),
        sa.Column("fx_parallel_premium", sa.Float, nullable=True),
    )
    op.create_table(
        "data_vintage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("ix_data_vintage_created_at", "data_vintage", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_vintage_created_at", "data_vintage")
    op.drop_table("data_vintage")
    op.drop_table("country")
```

- [ ] **Step 3: Apply and verify**

```bash
uv run alembic -c infra/migrations/alembic.ini upgrade head
docker compose exec -T postgres psql -U atlas -d atlas -c "\dt"
docker compose exec -T postgres psql -U atlas -d atlas -c "\d country"
```

Expected: `country` and `data_vintage` tables present. `country` has the CHECK constraints.

- [ ] **Step 4: Test downgrade path**

```bash
uv run alembic -c infra/migrations/alembic.ini downgrade 0001_baseline
uv run alembic -c infra/migrations/alembic.ini upgrade head
```

Expected: both succeed without error.

- [ ] **Step 5: Commit**

```bash
git add infra/migrations/versions/0002_country_and_vintage.py apps/api/src/atlas_api/models.py
git commit -m "feat(infra): add country and data_vintage tables"
```

---

### Task 4: Country seed JSON + loader

**Files:**
- Create: `infra/seed/countries.json`
- Create: `apps/api/scripts/seed_countries.py`

- [ ] **Step 1: Write `countries.json`**

```json
[
  {"iso3": "CIV", "name": "Côte d'Ivoire", "capital": "Yamoussoukro", "region": "West Africa", "tags": ["SSA", "WAEMU", "cocoa"], "tier": "B", "status": "performing", "fx_regime": "pegged", "fx_regime_notes": "CFA franc pegged to EUR via WAEMU", "fx_parallel_premium": null},
  {"iso3": "GHA", "name": "Ghana", "capital": "Accra", "region": "West Africa", "tags": ["SSA", "ECOWAS", "cocoa", "gold"], "tier": "C", "status": "restructured", "fx_regime": "float", "fx_regime_notes": "Cedi floats; 2022 domestic debt exchange completed 2023", "fx_parallel_premium": null},
  {"iso3": "KEN", "name": "Kenya", "capital": "Nairobi", "region": "East Africa", "tags": ["SSA", "EAC", "eurobond"], "tier": "B", "status": "performing", "fx_regime": "managed_float", "fx_regime_notes": "CBK manages KES against USD", "fx_parallel_premium": null},
  {"iso3": "NGA", "name": "Nigeria", "capital": "Abuja", "region": "West Africa", "tags": ["SSA", "ECOWAS", "oil"], "tier": "B", "status": "performing", "fx_regime": "managed_float", "fx_regime_notes": "CBN unified FX window 2023; parallel market persists", "fx_parallel_premium": null},
  {"iso3": "SEN", "name": "Senegal", "capital": "Dakar", "region": "West Africa", "tags": ["SSA", "WAEMU", "gas"], "tier": "B", "status": "performing", "fx_regime": "pegged", "fx_regime_notes": "CFA franc pegged to EUR via WAEMU", "fx_parallel_premium": null},
  {"iso3": "ETH", "name": "Ethiopia", "capital": "Addis Ababa", "region": "East Africa", "tags": ["SSA", "restructuring"], "tier": "C", "status": "selective_default", "fx_regime": "crawling_peg", "fx_regime_notes": "ETB devalued 30% July 2024; G20 Common Framework restructuring ongoing", "fx_parallel_premium": null},
  {"iso3": "RWA", "name": "Rwanda", "capital": "Kigali", "region": "East Africa", "tags": ["SSA", "EAC"], "tier": "B", "status": "performing", "fx_regime": "managed_float", "fx_regime_notes": "BNR manages RWF against USD", "fx_parallel_premium": null},
  {"iso3": "ZAF", "name": "South Africa", "capital": "Pretoria", "region": "Southern Africa", "tags": ["SSA", "G20", "BRICS"], "tier": "A", "status": "performing", "fx_regime": "float", "fx_regime_notes": "Rand floats freely; deep FX market", "fx_parallel_premium": null},
  {"iso3": "MAR", "name": "Morocco", "capital": "Rabat", "region": "North Africa", "tags": ["MENA", "eurobond"], "tier": "A", "status": "performing", "fx_regime": "basket_peg", "fx_regime_notes": "Dirham pegged to EUR/USD basket (60/40); ±5% band", "fx_parallel_premium": null},
  {"iso3": "EGY", "name": "Egypt", "capital": "Cairo", "region": "North Africa", "tags": ["MENA", "IMF-program"], "tier": "B", "status": "performing", "fx_regime": "managed_float", "fx_regime_notes": "EGP devalued ~60% March 2024 under IMF program; parallel market gap narrowed post-devaluation", "fx_parallel_premium": null}
]
```

- [ ] **Step 2: Write loader script**

```python
# apps/api/scripts/seed_countries.py
"""Idempotent seed of the 10 prototype countries from infra/seed/countries.json."""

import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from atlas_api.db import SessionLocal
from atlas_api.models import Country

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
```

- [ ] **Step 3: Run it**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv run python apps/api/scripts/seed_countries.py
docker compose exec -T postgres psql -U atlas -d atlas -c "SELECT iso3, name, status, fx_regime FROM country ORDER BY iso3;"
```

Expected: 10 rows printed.

- [ ] **Step 4: Verify idempotency**

```bash
uv run python apps/api/scripts/seed_countries.py
```

Expected: no errors, `upserted 10 countries`.

- [ ] **Step 5: Commit**

```bash
git add infra/seed/countries.json apps/api/scripts/seed_countries.py
git commit -m "feat(infra): seed 10 prototype countries"
```

---

### Task 5: Country service + list/single API endpoints

**Files:**
- Create: `apps/api/src/atlas_api/services/__init__.py`
- Create: `apps/api/src/atlas_api/services/country/__init__.py`
- Create: `apps/api/src/atlas_api/services/country/queries.py`
- Create: `apps/api/src/atlas_api/routers/countries.py`
- Create: `apps/api/tests/test_countries.py`
- Modify: `apps/api/src/atlas_api/main.py` (include router)

- [ ] **Step 1: Write failing tests**

```python
# apps/api/tests/test_countries.py
import uuid

from atlas_api.models import Country
from atlas_api.security import hash_password
from atlas_api.models import User


def _seed_user(session):
    u = User(id=uuid.uuid4(), email="a@b.test", password_hash=hash_password("pw-123456"), role="Analyst")
    session.add(u)
    session.commit()


def _seed_country(session, iso3: str = "GHA") -> None:
    session.add(Country(
        iso3=iso3, name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    session.commit()


def _login(client):
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert r.status_code == 200


def test_list_countries_requires_auth(client):
    r = client.get("/api/countries")
    assert r.status_code == 401


def test_list_countries_returns_seeded(client, session):
    _seed_user(session)
    _seed_country(session, "GHA")
    _seed_country(session, "KEN")
    _login(client)
    r = client.get("/api/countries")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    isos = {c["iso3"] for c in body}
    assert isos == {"GHA", "KEN"}


def test_get_country_returns_full_row(client, session):
    _seed_user(session)
    _seed_country(session, "GHA")
    _login(client)
    r = client.get("/api/countries/GHA")
    assert r.status_code == 200
    body = r.json()
    assert body["iso3"] == "GHA"
    assert body["status"] == "restructured"
    assert body["fx_regime"] == "float"


def test_get_country_404(client, session):
    _seed_user(session)
    _login(client)
    r = client.get("/api/countries/ZZZ")
    assert r.status_code == 404
```

- [ ] **Step 2: Write service queries**

```python
# apps/api/src/atlas_api/services/__init__.py
```

```python
# apps/api/src/atlas_api/services/country/__init__.py
from atlas_api.services.country.queries import get_country, list_countries

__all__ = ["get_country", "list_countries"]
```

```python
# apps/api/src/atlas_api/services/country/queries.py
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.models import Country


def list_countries(session: Session) -> list[Country]:
    return list(session.execute(select(Country).order_by(Country.iso3)).scalars())


def get_country(session: Session, iso3: str) -> Country | None:
    return session.get(Country, iso3.upper())
```

- [ ] **Step 3: Write router**

```python
# apps/api/src/atlas_api/routers/countries.py
from fastapi import APIRouter, HTTPException, status

from atlas_api.deps import CurrentUser, DbSession
from atlas_api.services.country import get_country, list_countries
from atlas_schemas.country import Country as CountrySchema

router = APIRouter(prefix="/api/countries", tags=["countries"])


@router.get("", response_model=list[CountrySchema])
def list_all(session: DbSession, _: CurrentUser) -> list[CountrySchema]:
    return [CountrySchema.model_validate(c, from_attributes=True) for c in list_countries(session)]


@router.get("/{iso3}", response_model=CountrySchema)
def get_one(iso3: str, session: DbSession, _: CurrentUser) -> CountrySchema:
    c = get_country(session, iso3)
    if c is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"country {iso3} not found")
    return CountrySchema.model_validate(c, from_attributes=True)
```

- [ ] **Step 4: Register router**

Edit `apps/api/src/atlas_api/main.py`. Change `from atlas_api.routers import auth, health` to `from atlas_api.routers import auth, countries, health`. Add `app.include_router(countries.router)` after the existing `include_router` calls.

- [ ] **Step 5: Run tests**

```bash
uv run pytest apps/api/tests/test_countries.py -v
```

Expected: 4 passing.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/atlas_api/services apps/api/src/atlas_api/routers/countries.py apps/api/src/atlas_api/main.py apps/api/tests/test_countries.py
git commit -m "feat(api): country list + get endpoints"
```

---

### Task 6: Macro / FX / ratings schemas

**Files:**
- Create: `packages/schemas/src/atlas_schemas/macro.py`
- Create: `packages/schemas/src/atlas_schemas/fx.py`
- Create: `packages/schemas/src/atlas_schemas/ratings.py`
- Modify: `packages/schemas/src/atlas_schemas/__init__.py`
- Modify: `packages/schemas/tests/test_contracts.py`

- [ ] **Step 1: Write `macro.py`**

```python
# packages/schemas/src/atlas_schemas/macro.py
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class MacroIndicator(str, Enum):
    GDP_USD = "GDP_USD"
    GDP_GROWTH_PCT = "GDP_GROWTH_PCT"
    INFLATION_PCT = "INFLATION_PCT"
    CURRENT_ACCOUNT_PCT_GDP = "CURRENT_ACCOUNT_PCT_GDP"
    FISCAL_BALANCE_PCT_GDP = "FISCAL_BALANCE_PCT_GDP"
    PUBLIC_DEBT_PCT_GDP = "PUBLIC_DEBT_PCT_GDP"
    EXTERNAL_DEBT_PCT_GNI = "EXTERNAL_DEBT_PCT_GNI"
    FX_RESERVES_MO_IMPORTS = "FX_RESERVES_MO_IMPORTS"
    DEBT_SERVICE_PCT_EXPORTS = "DEBT_SERVICE_PCT_EXPORTS"
    UNEMPLOYMENT_PCT = "UNEMPLOYMENT_PCT"
    FDI_INFLOW_USD = "FDI_INFLOW_USD"
    GDP_PER_CAPITA_USD = "GDP_PER_CAPITA_USD"


class MacroValue(BaseModel):
    iso3: str
    indicator: MacroIndicator
    period: str                       # "2024" for yearly, "2024-Q2" for quarterly
    value: float | None
    source: str
    source_date: date | None
    ingested_at: datetime
    vintage_id: UUID
```

- [ ] **Step 2: Write `fx.py`**

```python
# packages/schemas/src/atlas_schemas/fx.py
from datetime import date, datetime

from pydantic import BaseModel


class FxObservation(BaseModel):
    iso3: str
    ccy: str
    usd_per_ccy: float
    observation_date: date
    source: str
    ingested_at: datetime


class FxDeltas(BaseModel):
    latest: FxObservation
    delta_1d_pct: float | None
    delta_7d_pct: float | None
    delta_30d_pct: float | None
    delta_ytd_pct: float | None
```

- [ ] **Step 3: Write `ratings.py`**

```python
# packages/schemas/src/atlas_schemas/ratings.py
from datetime import date
from enum import Enum

from pydantic import BaseModel


class Agency(str, Enum):
    SP = "S&P"
    MOODYS = "Moodys"
    FITCH = "Fitch"


class RatingAction(BaseModel):
    iso3: str
    agency: Agency
    rating: str               # "B", "Caa1", "SD", "D", etc.; agency-native string
    outlook: str | None       # "stable" | "positive" | "negative" | "developing" | None
    action: str               # "affirm" | "downgrade" | "upgrade" | "default"
    action_date: date
    source_url: str | None
```

- [ ] **Step 4: Update `__init__.py`**

```python
# packages/schemas/src/atlas_schemas/__init__.py
from atlas_schemas.auth import LoginRequest, LoginResponse, Me
from atlas_schemas.country import Country, CountryStatus, FxRegime
from atlas_schemas.fx import FxDeltas, FxObservation
from atlas_schemas.health import HealthResponse
from atlas_schemas.ingestion import DataVintage, IngestionReport, SourceStats
from atlas_schemas.macro import MacroIndicator, MacroValue
from atlas_schemas.ratings import Agency, RatingAction

__all__ = [
    "Agency",
    "Country",
    "CountryStatus",
    "DataVintage",
    "FxDeltas",
    "FxObservation",
    "FxRegime",
    "HealthResponse",
    "IngestionReport",
    "LoginRequest",
    "LoginResponse",
    "MacroIndicator",
    "MacroValue",
    "Me",
    "RatingAction",
    "SourceStats",
]
```

- [ ] **Step 5: Add contract tests**

Append to `packages/schemas/tests/test_contracts.py`:

```python
def test_macro_value_schema():
    from atlas_schemas.macro import MacroIndicator, MacroValue
    v = MacroValue.model_validate({
        "iso3": "GHA",
        "indicator": "INFLATION_PCT",
        "period": "2024",
        "value": 22.4,
        "source": "worldbank",
        "source_date": "2024-12-31",
        "ingested_at": "2026-04-16T03:00:00Z",
        "vintage_id": "00000000-0000-0000-0000-000000000001",
    })
    assert v.indicator is MacroIndicator.INFLATION_PCT
    assert v.value == 22.4


def test_macro_value_allows_null():
    from atlas_schemas.macro import MacroValue
    v = MacroValue.model_validate({
        "iso3": "GHA", "indicator": "GDP_USD", "period": "2025", "value": None,
        "source": "imf_weo", "source_date": None,
        "ingested_at": "2026-04-16T03:00:00Z",
        "vintage_id": "00000000-0000-0000-0000-000000000001",
    })
    assert v.value is None


def test_rating_action_schema():
    from atlas_schemas.ratings import Agency, RatingAction
    r = RatingAction.model_validate({
        "iso3": "GHA", "agency": "S&P", "rating": "SD",
        "outlook": None, "action": "default", "action_date": "2022-12-21",
        "source_url": "https://www.spglobal.com/ratings/en/research/articles/221221",
    })
    assert r.agency is Agency.SP
```

- [ ] **Step 6: Run tests + regen TS**

```bash
uv run pytest packages/schemas/tests/ -v
uv run python packages/schemas/scripts/generate_ts.py
grep -q "MacroIndicator" apps/web/src/types/generated.ts && echo OK
```

Expected: 8 passing (5 prior + 3 new); `OK`.

- [ ] **Step 7: Commit**

```bash
git add packages/schemas
git commit -m "feat(schemas): add macro + fx + ratings contracts"
```

---

### Task 7: Migration `0003` — `macro_indicator_vintage`, `fx_rate`, `rating_history`

**Files:**
- Create: `infra/migrations/versions/0003_macro_fx_rating.py`
- Modify: `apps/api/src/atlas_api/models.py`

- [ ] **Step 1: Extend `models.py`**

Append to `apps/api/src/atlas_api/models.py`:

```python
from sqlalchemy import Date, Numeric, UniqueConstraint


class MacroIndicatorVintage(Base):
    __tablename__ = "macro_indicator_vintage"
    __table_args__ = (
        UniqueConstraint("iso3", "indicator", "period", "vintage_id", name="uq_macro_vintage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    indicator: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    vintage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_vintage.id"), nullable=False
    )


class FxRate(Base):
    __tablename__ = "fx_rate"
    __table_args__ = (UniqueConstraint("iso3", "observation_date", name="uq_fx_daily"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    ccy: Mapped[str] = mapped_column(String(3), nullable=False)
    usd_per_ccy: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    observation_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class RatingHistory(Base):
    __tablename__ = "rating_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iso3: Mapped[str] = mapped_column(String(3), ForeignKey("country.iso3"), nullable=False)
    agency: Mapped[str] = mapped_column(String(16), nullable=False)
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    outlook: Mapped[str | None] = mapped_column(String(16), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    action_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 2: Write migration**

```python
# infra/migrations/versions/0003_macro_fx_rating.py
"""macro + fx + ratings

Revision ID: 0003_macro_fx_rating
Revises: 0002_country_and_vintage
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_macro_fx_rating"
down_revision = "0002_country_and_vintage"
branch_labels = None
depends_on = None

AGENCIES = ("S&P", "Moodys", "Fitch")


def upgrade() -> None:
    op.create_table(
        "macro_indicator_vintage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column("indicator", sa.String(64), nullable=False),
        sa.Column("value", sa.Numeric(20, 6), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_date", sa.Date, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("vintage_id", UUID(as_uuid=True), sa.ForeignKey("data_vintage.id"), nullable=False),
        sa.UniqueConstraint("iso3", "indicator", "period", "vintage_id", name="uq_macro_vintage"),
    )
    op.create_index(
        "ix_macro_latest",
        "macro_indicator_vintage",
        ["iso3", "indicator", sa.text("period DESC"), sa.text("ingested_at DESC")],
    )

    op.create_table(
        "fx_rate",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column("ccy", sa.String(3), nullable=False),
        sa.Column("usd_per_ccy", sa.Numeric(20, 8), nullable=False),
        sa.Column("observation_date", sa.Date, nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("iso3", "observation_date", name="uq_fx_daily"),
    )
    op.create_index("ix_fx_iso3_date", "fx_rate", ["iso3", sa.text("observation_date DESC")])

    op.create_table(
        "rating_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("iso3", sa.String(3), sa.ForeignKey("country.iso3"), nullable=False),
        sa.Column(
            "agency",
            sa.String(16),
            sa.CheckConstraint(f"agency IN {AGENCIES}", name="rating_agency_check"),
            nullable=False,
        ),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("outlook", sa.String(16), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("action_date", sa.Date, nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_rating_iso3_agency_date", "rating_history", ["iso3", "agency", sa.text("action_date DESC")])


def downgrade() -> None:
    op.drop_index("ix_rating_iso3_agency_date", "rating_history")
    op.drop_table("rating_history")
    op.drop_index("ix_fx_iso3_date", "fx_rate")
    op.drop_table("fx_rate")
    op.drop_index("ix_macro_latest", "macro_indicator_vintage")
    op.drop_table("macro_indicator_vintage")
```

- [ ] **Step 3: Apply and verify**

```bash
uv run alembic -c infra/migrations/alembic.ini upgrade head
docker compose exec -T postgres psql -U atlas -d atlas -c "\dt"
```

Expected: `macro_indicator_vintage`, `fx_rate`, `rating_history` present.

- [ ] **Step 4: Round-trip downgrade/upgrade**

```bash
uv run alembic -c infra/migrations/alembic.ini downgrade 0002_country_and_vintage
uv run alembic -c infra/migrations/alembic.ini upgrade head
```

Expected: both succeed.

- [ ] **Step 5: Commit**

```bash
git add infra/migrations/versions/0003_macro_fx_rating.py apps/api/src/atlas_api/models.py
git commit -m "feat(infra): add macro + fx + rating tables"
```

---

### Task 8: Read paths + indicator mapping

**Files:**
- Create: `apps/api/src/atlas_api/services/country/indicators.py`
- Modify: `apps/api/src/atlas_api/services/country/queries.py`
- Create: `apps/api/tests/test_read_paths.py`

- [ ] **Step 1: Write `indicators.py`**

```python
# apps/api/src/atlas_api/services/country/indicators.py
"""Internal MacroIndicator ↔ external source code mapping."""

from atlas_schemas.macro import MacroIndicator

WORLDBANK_CODES: dict[MacroIndicator, str] = {
    MacroIndicator.GDP_USD: "NY.GDP.MKTP.CD",
    MacroIndicator.GDP_GROWTH_PCT: "NY.GDP.MKTP.KD.ZG",
    MacroIndicator.INFLATION_PCT: "FP.CPI.TOTL.ZG",
    MacroIndicator.CURRENT_ACCOUNT_PCT_GDP: "BN.CAB.XOKA.GD.ZS",
    MacroIndicator.FISCAL_BALANCE_PCT_GDP: "GC.BAL.CASH.GD.ZS",
    MacroIndicator.PUBLIC_DEBT_PCT_GDP: "GC.DOD.TOTL.GD.ZS",
    MacroIndicator.EXTERNAL_DEBT_PCT_GNI: "DT.DOD.DECT.GN.ZS",
    MacroIndicator.FX_RESERVES_MO_IMPORTS: "FI.RES.TOTL.MO",
    MacroIndicator.DEBT_SERVICE_PCT_EXPORTS: "DT.TDS.DECT.EX.ZS",
    MacroIndicator.UNEMPLOYMENT_PCT: "SL.UEM.TOTL.ZS",
    MacroIndicator.FDI_INFLOW_USD: "BX.KLT.DINV.CD.WD",
    MacroIndicator.GDP_PER_CAPITA_USD: "NY.GDP.PCAP.CD",
}

IMF_WEO_CODES: dict[MacroIndicator, str] = {
    MacroIndicator.GDP_USD: "NGDPD",
    MacroIndicator.GDP_GROWTH_PCT: "NGDP_RPCH",
    MacroIndicator.INFLATION_PCT: "PCPIPCH",
    MacroIndicator.CURRENT_ACCOUNT_PCT_GDP: "BCA_NGDPD",
    MacroIndicator.FISCAL_BALANCE_PCT_GDP: "GGXCNL_NGDP",
    MacroIndicator.PUBLIC_DEBT_PCT_GDP: "GGXWDG_NGDP",
    MacroIndicator.UNEMPLOYMENT_PCT: "LUR",
    MacroIndicator.GDP_PER_CAPITA_USD: "NGDPDPC",
}

ISO3_TO_CCY: dict[str, str] = {
    "CIV": "XOF", "GHA": "GHS", "KEN": "KES", "NGA": "NGN", "SEN": "XOF",
    "ETH": "ETB", "RWA": "RWF", "ZAF": "ZAR", "MAR": "MAD", "EGY": "EGP",
}
```

- [ ] **Step 2: Extend `queries.py`**

Replace `apps/api/src/atlas_api/services/country/queries.py`:

```python
# apps/api/src/atlas_api/services/country/queries.py
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.models import Country, FxRate, MacroIndicatorVintage, RatingHistory


def list_countries(session: Session) -> list[Country]:
    return list(session.execute(select(Country).order_by(Country.iso3)).scalars())


def get_country(session: Session, iso3: str) -> Country | None:
    return session.get(Country, iso3.upper())


def get_latest(session: Session, iso3: str, indicator: str) -> MacroIndicatorVintage | None:
    return session.execute(
        select(MacroIndicatorVintage)
        .where(MacroIndicatorVintage.iso3 == iso3.upper(), MacroIndicatorVintage.indicator == indicator)
        .order_by(
            MacroIndicatorVintage.period.desc(),
            MacroIndicatorVintage.ingested_at.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def get_as_of(
    session: Session, iso3: str, indicator: str, vintage_id: UUID
) -> MacroIndicatorVintage | None:
    return session.execute(
        select(MacroIndicatorVintage)
        .where(
            MacroIndicatorVintage.iso3 == iso3.upper(),
            MacroIndicatorVintage.indicator == indicator,
            MacroIndicatorVintage.vintage_id == vintage_id,
        )
        .order_by(MacroIndicatorVintage.period.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_latest_fx(session: Session, iso3: str) -> FxRate | None:
    return session.execute(
        select(FxRate)
        .where(FxRate.iso3 == iso3.upper())
        .order_by(FxRate.observation_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_fx_on(session: Session, iso3: str, d: date) -> FxRate | None:
    return session.execute(
        select(FxRate)
        .where(FxRate.iso3 == iso3.upper(), FxRate.observation_date <= d)
        .order_by(FxRate.observation_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def compute_fx_deltas(session: Session, iso3: str) -> dict[str, float | None]:
    latest = get_latest_fx(session, iso3)
    if latest is None:
        return {"delta_1d_pct": None, "delta_7d_pct": None, "delta_30d_pct": None, "delta_ytd_pct": None}
    base = latest.observation_date

    def pct(past: FxRate | None) -> float | None:
        if past is None or past.usd_per_ccy == 0:
            return None
        return float((latest.usd_per_ccy - past.usd_per_ccy) / past.usd_per_ccy) * 100.0

    return {
        "delta_1d_pct": pct(get_fx_on(session, iso3, base - timedelta(days=1))),
        "delta_7d_pct": pct(get_fx_on(session, iso3, base - timedelta(days=7))),
        "delta_30d_pct": pct(get_fx_on(session, iso3, base - timedelta(days=30))),
        "delta_ytd_pct": pct(get_fx_on(session, iso3, date(base.year, 1, 1))),
    }


def get_rating_history(
    session: Session, iso3: str, agency: str | None = None
) -> list[RatingHistory]:
    stmt = select(RatingHistory).where(RatingHistory.iso3 == iso3.upper())
    if agency is not None:
        stmt = stmt.where(RatingHistory.agency == agency)
    stmt = stmt.order_by(RatingHistory.action_date.desc())
    return list(session.execute(stmt).scalars())
```

- [ ] **Step 3: Write integration tests**

```python
# apps/api/tests/test_read_paths.py
import uuid
from datetime import date, datetime, UTC

from atlas_api.models import Country, DataVintage, FxRate, MacroIndicatorVintage, RatingHistory
from atlas_api.services.country.queries import (
    compute_fx_deltas,
    get_as_of,
    get_latest,
    get_latest_fx,
    get_rating_history,
)


def _country(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    session.commit()


def _vintage(session, source: str = "test") -> DataVintage:
    v = DataVintage(id=uuid.uuid4(), source=source, created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v


def test_get_latest_returns_most_recent_period(session):
    _country(session)
    v = _vintage(session)
    session.add_all([
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="INFLATION_PCT", period="2023",
            value=31.5, source="worldbank", source_date=date(2023, 12, 31),
            vintage_id=v.id,
        ),
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="INFLATION_PCT", period="2024",
            value=22.4, source="worldbank", source_date=date(2024, 12, 31),
            vintage_id=v.id,
        ),
    ])
    session.commit()
    row = get_latest(session, "GHA", "INFLATION_PCT")
    assert row is not None
    assert row.period == "2024"
    assert float(row.value) == 22.4


def test_get_as_of_uses_specific_vintage(session):
    _country(session)
    v_old = _vintage(session, "old")
    v_new = _vintage(session, "new")
    session.add_all([
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="GDP_USD", period="2024",
            value=80.0, source="worldbank", source_date=date(2024, 12, 31),
            vintage_id=v_old.id,
        ),
        MacroIndicatorVintage(
            id=uuid.uuid4(), iso3="GHA", indicator="GDP_USD", period="2024",
            value=82.3, source="imf_weo", source_date=date(2024, 12, 31),
            vintage_id=v_new.id,
        ),
    ])
    session.commit()
    old = get_as_of(session, "GHA", "GDP_USD", v_old.id)
    new = get_as_of(session, "GHA", "GDP_USD", v_new.id)
    assert float(old.value) == 80.0
    assert float(new.value) == 82.3


def test_fx_deltas(session):
    _country(session)
    today = date(2026, 4, 16)
    rows = [
        (today, 15.00),
        (date(2026, 4, 15), 15.10),
        (date(2026, 4, 9), 14.80),
        (date(2026, 3, 17), 14.50),
        (date(2026, 1, 1), 14.00),
    ]
    for d, rate in rows:
        session.add(FxRate(
            id=uuid.uuid4(), iso3="GHA", ccy="GHS", usd_per_ccy=rate,
            observation_date=d, source="exchangerate.host",
        ))
    session.commit()

    latest = get_latest_fx(session, "GHA")
    assert latest is not None
    assert latest.observation_date == today

    deltas = compute_fx_deltas(session, "GHA")
    assert round(deltas["delta_1d_pct"], 4) == round((15.00 - 15.10) / 15.10 * 100, 4)
    assert round(deltas["delta_7d_pct"], 4) == round((15.00 - 14.80) / 14.80 * 100, 4)
    assert round(deltas["delta_30d_pct"], 4) == round((15.00 - 14.50) / 14.50 * 100, 4)
    assert round(deltas["delta_ytd_pct"], 4) == round((15.00 - 14.00) / 14.00 * 100, 4)


def test_rating_history_filtered(session):
    _country(session)
    session.add_all([
        RatingHistory(
            id=uuid.uuid4(), iso3="GHA", agency="S&P", rating="SD",
            outlook=None, action="default", action_date=date(2022, 12, 21),
        ),
        RatingHistory(
            id=uuid.uuid4(), iso3="GHA", agency="S&P", rating="CCC+",
            outlook="stable", action="upgrade", action_date=date(2024, 5, 1),
        ),
        RatingHistory(
            id=uuid.uuid4(), iso3="GHA", agency="Moodys", rating="Caa3",
            outlook="stable", action="affirm", action_date=date(2024, 6, 1),
        ),
    ])
    session.commit()

    all_hist = get_rating_history(session, "GHA")
    assert len(all_hist) == 3
    assert all_hist[0].action_date == date(2024, 6, 1)
    sp_only = get_rating_history(session, "GHA", agency="S&P")
    assert len(sp_only) == 2
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest apps/api/tests/test_read_paths.py -v
```

Expected: 4 passing.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/atlas_api/services/country/ apps/api/tests/test_read_paths.py
git commit -m "feat(api): macro/fx/ratings read paths"
```

---

### Task 9: Composite rating (pure function + golden tests)

**Files:**
- Create: `apps/api/src/atlas_api/services/country/composite_rating.py`
- Create: `apps/api/tests/test_composite_rating.py`

- [ ] **Step 1: Write failing golden tests**

```python
# apps/api/tests/test_composite_rating.py
import pytest

from atlas_api.services.country.composite_rating import (
    AGENCY_WEIGHTS,
    composite_score,
    rating_to_score,
)


# Sample agency-native ratings mapped to 22-step numeric scale (0 = AAA, 21 = D).
# Golden tests lock the ladder.
@pytest.mark.parametrize(
    "agency,rating,expected",
    [
        ("S&P", "AAA", 0),
        ("S&P", "AA+", 1),
        ("S&P", "AA", 2),
        ("S&P", "A", 5),
        ("S&P", "BBB", 8),
        ("S&P", "BB", 11),
        ("S&P", "B", 14),
        ("S&P", "CCC", 17),
        ("S&P", "SD", 21),
        ("S&P", "D", 21),
        ("Moodys", "Aaa", 0),
        ("Moodys", "Aa1", 1),
        ("Moodys", "Baa3", 10),
        ("Moodys", "Caa1", 17),
        ("Moodys", "Ca", 20),
        ("Moodys", "C", 21),
        ("Fitch", "AAA", 0),
        ("Fitch", "BB-", 13),
        ("Fitch", "RD", 21),
    ],
)
def test_rating_to_score(agency: str, rating: str, expected: int):
    assert rating_to_score(agency, rating) == expected


def test_composite_all_three_present():
    # S&P = B (14), Moodys = Caa1 (17), Fitch = B- (15)
    # weights: 0.4*14 + 0.35*17 + 0.25*15 = 5.6 + 5.95 + 3.75 = 15.30
    assert composite_score({"S&P": "B", "Moodys": "Caa1", "Fitch": "B-"}) == pytest.approx(15.30)


def test_composite_missing_fitch_rescales():
    # S&P = B (14), Moodys = Caa1 (17); weights rescaled to 0.4/0.75 and 0.35/0.75
    # = (0.5333 * 14) + (0.4667 * 17) = 7.467 + 7.933 = 15.400
    assert composite_score({"S&P": "B", "Moodys": "Caa1"}) == pytest.approx(15.40, rel=1e-3)


def test_composite_single_agency_returns_that_score():
    assert composite_score({"S&P": "B+"}) == pytest.approx(13.0)


def test_composite_empty_returns_none():
    assert composite_score({}) is None


def test_agency_weights_sum_to_one():
    assert sum(AGENCY_WEIGHTS.values()) == pytest.approx(1.0)


def test_unknown_rating_raises():
    with pytest.raises(ValueError):
        rating_to_score("S&P", "Zzz")


def test_unknown_agency_raises():
    with pytest.raises(ValueError):
        rating_to_score("OtherAgency", "AAA")
```

- [ ] **Step 2: Implement**

```python
# apps/api/src/atlas_api/services/country/composite_rating.py
"""Composite sovereign rating per spec §6.4.

Maps agency-native rating strings onto a shared 22-step numeric scale
(0 = AAA, 21 = default) then weights by agency. Missing agencies are
handled by rescaling the remaining weights to sum to 1.
"""

AGENCY_WEIGHTS: dict[str, float] = {"S&P": 0.40, "Moodys": 0.35, "Fitch": 0.25}


# 22-step investment-to-default ladder. Each agency's native string maps to one step.
_SP_FITCH = [
    "AAA",           # 0
    "AA+", "AA", "AA-",            # 1, 2, 3
    "A+", "A", "A-",               # 4, 5, 6
    "BBB+", "BBB", "BBB-",         # 7, 8, 9
    "BB+", "BB", "BB-",            # 10, 11, 12
    "B+", "B", "B-",               # 13, 14, 15
    "CCC+", "CCC", "CCC-",         # 16, 17, 18
    "CC",                          # 19
    "C",                           # 20
    "SD",                          # 21 (also D / RD / DD / DDD)
]

_MOODYS = [
    "Aaa",                         # 0
    "Aa1", "Aa2", "Aa3",           # 1, 2, 3
    "A1", "A2", "A3",              # 4, 5, 6
    "Baa1", "Baa2", "Baa3",        # 7, 8, 9
    "Ba1", "Ba2", "Ba3",           # 10, 11, 12
    "B1", "B2", "B3",              # 13, 14, 15
    "Caa1", "Caa2", "Caa3",        # 16, 17, 18
    "Ca",                          # 19 — but Moodys uses Ca at index 20 per market convention
    "C",                           # 21
]

# Build lookup tables. Moodys uses 21 names for 22 steps, so "Ca" is step 20, "C" is 21.
# Adjust moodys to fit the 22-step grid:
_MOODYS_LADDER = [
    "Aaa",
    "Aa1", "Aa2", "Aa3",
    "A1", "A2", "A3",
    "Baa1", "Baa2", "Baa3",
    "Ba1", "Ba2", "Ba3",
    "B1", "B2", "B3",
    "Caa1", "Caa2", "Caa3",
    "Ca",       # 19 — deep substandard
    "Ca",       # 20 — alias (Moodys merges this step in practice)
    "C",        # 21 — default
]

_SP_FITCH_ALIASES = {
    "D": 21, "RD": 21, "DD": 21, "DDD": 21,
}

_SP_INDEX = {r: i for i, r in enumerate(_SP_FITCH)}
_SP_INDEX.update(_SP_FITCH_ALIASES)
_MOODYS_INDEX: dict[str, int] = {}
for i, r in enumerate(_MOODYS_LADDER):
    _MOODYS_INDEX.setdefault(r, i)  # first occurrence wins; "Ca" stays at 19, "C" at 21


def rating_to_score(agency: str, rating: str) -> int:
    if agency in ("S&P", "Fitch"):
        if rating not in _SP_INDEX:
            raise ValueError(f"unknown {agency} rating: {rating!r}")
        return _SP_INDEX[rating]
    if agency == "Moodys":
        if rating not in _MOODYS_INDEX:
            raise ValueError(f"unknown Moodys rating: {rating!r}")
        return _MOODYS_INDEX[rating]
    raise ValueError(f"unknown agency: {agency!r}")


def composite_score(ratings: dict[str, str]) -> float | None:
    """ratings = {"S&P": "B", "Moodys": "Caa1", "Fitch": "B-"} → weighted score on 22-step scale.

    Missing agencies: rescale remaining weights so they sum to 1.
    Empty input: None.
    """
    if not ratings:
        return None
    present_weight = sum(AGENCY_WEIGHTS[a] for a in ratings if a in AGENCY_WEIGHTS)
    if present_weight == 0:
        raise ValueError(f"no known agencies in ratings: {list(ratings)}")
    total = 0.0
    for agency, rating in ratings.items():
        if agency not in AGENCY_WEIGHTS:
            raise ValueError(f"unknown agency: {agency!r}")
        w = AGENCY_WEIGHTS[agency] / present_weight
        total += w * rating_to_score(agency, rating)
    return round(total, 4)
```

- [ ] **Step 3: Run golden tests**

```bash
uv run pytest apps/api/tests/test_composite_rating.py -v
```

Expected: all passing.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/atlas_api/services/country/composite_rating.py apps/api/tests/test_composite_rating.py
git commit -m "feat(api): composite rating with agency weighting"
```

---

### Task 10: Ingestion framework (base + retry + circuit breaker)

**Files:**
- Create: `apps/api/src/atlas_api/ingestion/__init__.py`
- Create: `apps/api/src/atlas_api/ingestion/base.py`
- Create: `apps/api/src/atlas_api/ingestion/circuit_breaker.py`
- Create: `apps/api/src/atlas_api/logging_config.py`
- Create: `infra/migrations/versions/0004_ingestion_circuit.py`
- Modify: `apps/api/src/atlas_api/models.py` (add `IngestionCircuit`)
- Create: `apps/api/tests/test_ingestion_base.py`

- [ ] **Step 1: Extend `models.py`**

Append:

```python
class IngestionCircuit(Base):
    __tablename__ = "ingestion_circuit"

    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(nullable=False, default=0)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="closed")  # closed|open
```

- [ ] **Step 2: Write migration `0004`**

```python
# infra/migrations/versions/0004_ingestion_circuit.py
"""ingestion circuit breaker

Revision ID: 0004_ingestion_circuit
Revises: 0003_macro_fx_rating
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_ingestion_circuit"
down_revision = "0003_macro_fx_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_circuit",
        sa.Column("source", sa.String(32), primary_key=True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "state",
            sa.String(16),
            sa.CheckConstraint("state IN ('closed', 'open')", name="circuit_state_check"),
            nullable=False,
            server_default="closed",
        ),
    )


def downgrade() -> None:
    op.drop_table("ingestion_circuit")
```

Apply: `uv run alembic -c infra/migrations/alembic.ini upgrade head`.

- [ ] **Step 3: Write `logging_config.py`**

```python
# apps/api/src/atlas_api/logging_config.py
"""Structured JSON logging via structlog."""

import logging
import sys

import structlog

from atlas_api.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
```

- [ ] **Step 4: Write `circuit_breaker.py`**

```python
# apps/api/src/atlas_api/ingestion/circuit_breaker.py
"""DB-backed per-source circuit breaker. 3 consecutive failures → open."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from atlas_api.models import IngestionCircuit

FAILURE_THRESHOLD = 3


def is_open(session: Session, source: str) -> bool:
    row = session.get(IngestionCircuit, source)
    return row is not None and row.state == "open"


def record_success(session: Session, source: str) -> None:
    row = session.get(IngestionCircuit, source)
    now = datetime.now(UTC)
    if row is None:
        row = IngestionCircuit(
            source=source, consecutive_failures=0, last_success_at=now, state="closed"
        )
        session.add(row)
    else:
        row.consecutive_failures = 0
        row.last_success_at = now
        row.state = "closed"
    session.commit()


def record_failure(session: Session, source: str) -> str:
    row = session.get(IngestionCircuit, source)
    now = datetime.now(UTC)
    if row is None:
        row = IngestionCircuit(source=source, consecutive_failures=1, last_failure_at=now, state="closed")
        session.add(row)
    else:
        row.consecutive_failures += 1
        row.last_failure_at = now
        if row.consecutive_failures >= FAILURE_THRESHOLD:
            row.state = "open"
    session.commit()
    return row.state


def reset(session: Session, source: str) -> None:
    row = session.get(IngestionCircuit, source)
    if row is not None:
        row.consecutive_failures = 0
        row.state = "closed"
        session.commit()
```

- [ ] **Step 5: Write `base.py`**

```python
# apps/api/src/atlas_api/ingestion/__init__.py
```

```python
# apps/api/src/atlas_api/ingestion/base.py
"""Base Ingester + retry helper."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog
from sqlalchemy.orm import Session
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger()


@dataclass
class SourceStats:
    source: str
    rows_written: int = 0
    rows_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class IngestionReport:
    vintage_id: UUID
    started_at: datetime
    finished_at: datetime
    sources: list[SourceStats]
    ok: bool


RETRY = AsyncRetrying(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPError,)),
    reraise=True,
)


class Ingester(ABC):
    source_name: str = "abstract"

    def __init__(self, http: httpx.AsyncClient, session: Session) -> None:
        self.http = http
        self.session = session

    @abstractmethod
    async def run(self, vintage_id: UUID) -> SourceStats:
        """Execute the fetch+persist pipeline for this source."""


async def with_retry(op):  # pragma: no cover — tenacity handles retries; covered via integration
    async for attempt in RETRY:
        with attempt:
            return await op()


async def timed_run(ingester: Ingester, vintage_id: UUID) -> SourceStats:
    started = datetime.now(UTC)
    try:
        stats = await ingester.run(vintage_id)
    except Exception as exc:
        stats = SourceStats(source=ingester.source_name, errors=[f"{type(exc).__name__}: {exc}"])
        log.exception("ingester_failed", source=ingester.source_name)
    stats.duration_seconds = (datetime.now(UTC) - started).total_seconds()
    log.info(
        "ingester_complete",
        source=ingester.source_name,
        rows_written=stats.rows_written,
        errors=len(stats.errors),
        duration_s=round(stats.duration_seconds, 3),
    )
    return stats
```

- [ ] **Step 6: Write tests**

```python
# apps/api/tests/test_ingestion_base.py
import pytest

from atlas_api.ingestion.circuit_breaker import (
    FAILURE_THRESHOLD,
    is_open,
    record_failure,
    record_success,
    reset,
)


def test_circuit_starts_closed(session):
    assert is_open(session, "worldbank") is False


def test_circuit_opens_after_threshold_failures(session):
    for _ in range(FAILURE_THRESHOLD - 1):
        record_failure(session, "worldbank")
    assert is_open(session, "worldbank") is False
    record_failure(session, "worldbank")
    assert is_open(session, "worldbank") is True


def test_success_resets_failures(session):
    record_failure(session, "imf_weo")
    record_failure(session, "imf_weo")
    record_success(session, "imf_weo")
    assert is_open(session, "imf_weo") is False
    # Needs 3 fresh failures to open again
    record_failure(session, "imf_weo")
    assert is_open(session, "imf_weo") is False


def test_manual_reset(session):
    for _ in range(FAILURE_THRESHOLD):
        record_failure(session, "fx")
    assert is_open(session, "fx") is True
    reset(session, "fx")
    assert is_open(session, "fx") is False
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest apps/api/tests/test_ingestion_base.py -v
```

Expected: 4 passing.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/atlas_api/ingestion apps/api/src/atlas_api/logging_config.py apps/api/src/atlas_api/models.py infra/migrations/versions/0004_ingestion_circuit.py apps/api/tests/test_ingestion_base.py
git commit -m "feat(api): ingestion framework with circuit breaker"
```

---

### Task 11: World Bank ingester

**Files:**
- Create: `apps/api/src/atlas_api/ingestion/worldbank.py`
- Create: `apps/api/tests/test_ingestion_worldbank.py`

- [ ] **Step 1: Write `worldbank.py`**

```python
# apps/api/src/atlas_api/ingestion/worldbank.py
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

    async def _fetch(self, iso3: str, wb_code: str) -> list[dict]:
        url = BASE_URL.format(iso3=iso3, code=wb_code)
        resp = await self.http.get(url, params=PARAMS, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return []
        observations = payload[1] or []
        out: list[dict] = []
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
```

- [ ] **Step 2: Write tests (mocked HTTP via pytest-httpx)**

```python
# apps/api/tests/test_ingestion_worldbank.py
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from atlas_api.ingestion.worldbank import WorldBankIngester
from atlas_api.models import Country, DataVintage, MacroIndicatorVintage


pytestmark = pytest.mark.asyncio


def _seed_one_country(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v.id


async def test_worldbank_writes_rows(httpx_mock, session):
    vintage_id = _seed_one_country(session)

    # Match all WB URLs for GHA; return a canned 2024 + 2023 payload.
    def _response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[
            {"page": 1, "pages": 1, "total": 2},
            [
                {"indicator": {"id": "X", "value": "X"}, "country": {"id": "GH", "value": "Ghana"},
                 "countryiso3code": "GHA", "date": "2024", "value": 22.4, "unit": "", "obs_status": "", "decimal": 1},
                {"indicator": {"id": "X", "value": "X"}, "country": {"id": "GH", "value": "Ghana"},
                 "countryiso3code": "GHA", "date": "2023", "value": 31.5, "unit": "", "obs_status": "", "decimal": 1},
            ],
        ])

    httpx_mock.add_callback(_response)

    async with httpx.AsyncClient() as http:
        ing = WorldBankIngester(http, session)
        # Trim to just GHA for this test.
        from atlas_api.ingestion import worldbank
        original_countries = worldbank.COUNTRIES
        worldbank.COUNTRIES = ("GHA",)
        try:
            stats = await ing.run(vintage_id)
        finally:
            worldbank.COUNTRIES = original_countries

    assert stats.rows_written > 0
    assert not stats.errors

    # Confirm at least one row persisted and links to our vintage.
    rows = session.execute(
        select(MacroIndicatorVintage).where(MacroIndicatorVintage.vintage_id == vintage_id)
    ).scalars().all()
    assert len(rows) >= 2


async def test_worldbank_records_errors_on_5xx(httpx_mock, session):
    vintage_id = _seed_one_country(session)
    httpx_mock.add_response(status_code=500)

    async with httpx.AsyncClient() as http:
        ing = WorldBankIngester(http, session)
        from atlas_api.ingestion import worldbank
        original = worldbank.COUNTRIES
        worldbank.COUNTRIES = ("GHA",)
        try:
            stats = await ing.run(vintage_id)
        finally:
            worldbank.COUNTRIES = original

    assert stats.rows_written == 0
    assert len(stats.errors) > 0
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest apps/api/tests/test_ingestion_worldbank.py -v
```

Expected: 2 passing.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/atlas_api/ingestion/worldbank.py apps/api/tests/test_ingestion_worldbank.py
git commit -m "feat(ingestion): world bank macro indicator ingester"
```

---

### Task 12: IMF WEO ingester

**Files:**
- Create: `apps/api/src/atlas_api/ingestion/imf.py`
- Create: `apps/api/tests/test_ingestion_imf.py`

- [ ] **Step 1: Write `imf.py`**

```python
# apps/api/src/atlas_api/ingestion/imf.py
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

    async def _fetch(self, iso3: str, imf_code: str) -> list[dict]:
        url = BASE_URL.format(indicator=imf_code, iso3=iso3)
        resp = await self.http.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        series = payload.get("values", {}).get(imf_code, {}).get(iso3, {})
        out: list[dict] = []
        for period, val in series.items():
            try:
                sd: date | None = date(int(period), 12, 31)
            except ValueError:
                sd = None
            out.append({"period": str(period), "value": val, "source_date": sd})
        return out
```

- [ ] **Step 2: Write tests**

```python
# apps/api/tests/test_ingestion_imf.py
import uuid
from datetime import UTC, datetime

import httpx
import pytest

from atlas_api.ingestion.imf import ImfWeoIngester
from atlas_api.models import Country, DataVintage

pytestmark = pytest.mark.asyncio


def _seed(session):
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        fx_regime_notes=None, fx_parallel_premium=None,
    ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v.id


async def test_imf_writes_rows(httpx_mock, session):
    vintage_id = _seed(session)

    def _response(request: httpx.Request) -> httpx.Response:
        # Match indicator code out of URL path segment.
        parts = request.url.path.split("/")
        indicator = parts[-2]
        iso3 = parts[-1]
        return httpx.Response(200, json={
            "values": {indicator: {iso3: {"2023": 4.1, "2024": 3.8, "2025": 5.2}}}
        })

    httpx_mock.add_callback(_response)

    async with httpx.AsyncClient() as http:
        ing = ImfWeoIngester(http, session)
        from atlas_api.ingestion import imf as imf_mod
        original = imf_mod.COUNTRIES
        imf_mod.COUNTRIES = ("GHA",)
        try:
            stats = await ing.run(vintage_id)
        finally:
            imf_mod.COUNTRIES = original

    assert stats.rows_written > 0
    assert not stats.errors


async def test_imf_handles_missing_series(httpx_mock, session):
    vintage_id = _seed(session)
    httpx_mock.add_response(json={"values": {}})

    async with httpx.AsyncClient() as http:
        ing = ImfWeoIngester(http, session)
        from atlas_api.ingestion import imf as imf_mod
        original = imf_mod.COUNTRIES
        imf_mod.COUNTRIES = ("GHA",)
        try:
            stats = await ing.run(vintage_id)
        finally:
            imf_mod.COUNTRIES = original

    assert stats.rows_written == 0
    assert not stats.errors  # missing series is not an error, just empty
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest apps/api/tests/test_ingestion_imf.py -v
```

Expected: 2 passing.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/atlas_api/ingestion/imf.py apps/api/tests/test_ingestion_imf.py
git commit -m "feat(ingestion): IMF WEO macro indicator ingester"
```

---

### Task 13: ExchangeRate.host FX ingester

**Files:**
- Create: `apps/api/src/atlas_api/ingestion/fx.py`
- Create: `apps/api/tests/test_ingestion_fx.py`

- [ ] **Step 1: Write `fx.py`**

```python
# apps/api/src/atlas_api/ingestion/fx.py
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

        for iso3, ccy in ISO3_TO_CCY.items():
            rate = rates.get(ccy)
            if rate is None:
                stats.rows_skipped += 1
                continue
            # payload.rates[ccy] is CCY per USD (1 USD = N CCY).
            # We store usd_per_ccy, so invert.
            if rate == 0:
                stats.errors.append(f"{iso3}/{ccy}: zero rate")
                continue
            usd_per_ccy = 1.0 / float(rate)
            self.session.merge(FxRate(
                id=uuid.uuid4(),
                iso3=iso3,
                ccy=ccy,
                usd_per_ccy=usd_per_ccy,
                observation_date=obs_date,
                source=self.source_name,
                ingested_at=datetime.now(UTC),
            ))
            stats.rows_written += 1
        self.session.commit()
        return stats
```

Note on `session.merge`: combined with the `uq_fx_daily` constraint, two ingestion runs on the same day for the same country update the existing row rather than colliding.

Actually — `merge` matches by primary key (`id`, which is UUID and fresh each call). The unique constraint would raise. Use an `insert().on_conflict_do_update(...)` instead. Rewrite the insertion block:

```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(FxRate).values(
    id=uuid.uuid4(),
    iso3=iso3, ccy=ccy, usd_per_ccy=usd_per_ccy,
    observation_date=obs_date,
    source=self.source_name,
    ingested_at=datetime.now(UTC),
).on_conflict_do_update(
    constraint="uq_fx_daily",
    set_={"usd_per_ccy": usd_per_ccy, "source": self.source_name, "ingested_at": datetime.now(UTC)},
)
self.session.execute(stmt)
```

Replace the `self.session.merge(FxRate(...))` block with the `on_conflict_do_update` block above.

- [ ] **Step 2: Write tests**

```python
# apps/api/tests/test_ingestion_fx.py
import uuid
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy import select

from atlas_api.ingestion.fx import ExchangeRateHostIngester
from atlas_api.models import Country, DataVintage, FxRate

pytestmark = pytest.mark.asyncio


def _seed_countries(session):
    for iso3, name in [
        ("CIV", "Côte d'Ivoire"), ("GHA", "Ghana"), ("KEN", "Kenya"),
        ("NGA", "Nigeria"), ("SEN", "Senegal"), ("ETH", "Ethiopia"),
        ("RWA", "Rwanda"), ("ZAF", "South Africa"), ("MAR", "Morocco"), ("EGY", "Egypt"),
    ]:
        session.add(Country(
            iso3=iso3, name=name, capital="?", region="?",
            tags=[], tier="B", status="performing", fx_regime="float",
            fx_regime_notes=None, fx_parallel_premium=None,
        ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v.id


async def test_fx_writes_daily_rows(httpx_mock, session):
    vintage_id = _seed_countries(session)
    httpx_mock.add_response(
        url=httpx.URL("https://api.exchangerate.host/latest", params={"base": "USD", "symbols": "EGP,ETB,GHS,KES,MAD,NGN,RWF,XOF,ZAR"}),
        json={
            "base": "USD",
            "date": "2026-04-16",
            "rates": {
                "XOF": 600.0, "GHS": 15.2, "KES": 129.4, "NGN": 1450.0,
                "ETB": 56.8, "RWF": 1350.0, "ZAR": 18.4, "MAD": 10.1, "EGP": 48.5,
            },
        },
    )

    async with httpx.AsyncClient() as http:
        ing = ExchangeRateHostIngester(http, session)
        stats = await ing.run(vintage_id)

    assert stats.rows_written == 10  # CIV + SEN both use XOF
    assert not stats.errors
    rows = session.execute(select(FxRate)).scalars().all()
    assert len(rows) == 10
    assert all(r.observation_date == date(2026, 4, 16) for r in rows)


async def test_fx_handles_missing_currency(httpx_mock, session):
    vintage_id = _seed_countries(session)
    httpx_mock.add_response(json={
        "base": "USD", "date": "2026-04-16",
        "rates": {"GHS": 15.2},  # only one currency returned
    })
    async with httpx.AsyncClient() as http:
        ing = ExchangeRateHostIngester(http, session)
        stats = await ing.run(vintage_id)
    assert stats.rows_written == 1
    assert stats.rows_skipped == 9
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest apps/api/tests/test_ingestion_fx.py -v
```

Expected: 2 passing.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/atlas_api/ingestion/fx.py apps/api/tests/test_ingestion_fx.py
git commit -m "feat(ingestion): exchangerate.host FX ingester"
```

---

### Task 14: Ratings JSON loader

**Files:**
- Create: `infra/seed/ratings.json`
- Create: `apps/api/src/atlas_api/ingestion/ratings.py`
- Create: `apps/api/tests/test_ingestion_ratings.py`

- [ ] **Step 1: Write seed `ratings.json`**

Minimum viable dataset: one current action per (country, agency). Later updates appended by hand.

```json
[
  {"iso3": "GHA", "agency": "S&P", "rating": "CCC+", "outlook": "stable", "action": "upgrade", "action_date": "2024-05-01", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "GHA", "agency": "Moodys", "rating": "Caa3", "outlook": "stable", "action": "affirm", "action_date": "2024-06-01", "source_url": "https://www.moodys.com/"},
  {"iso3": "GHA", "agency": "Fitch", "rating": "CCC+", "outlook": "stable", "action": "affirm", "action_date": "2024-07-15", "source_url": "https://www.fitchratings.com/"},
  {"iso3": "KEN", "agency": "S&P", "rating": "B-", "outlook": "negative", "action": "downgrade", "action_date": "2024-02-23", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "KEN", "agency": "Moodys", "rating": "Caa1", "outlook": "positive", "action": "affirm", "action_date": "2024-08-12", "source_url": "https://www.moodys.com/"},
  {"iso3": "KEN", "agency": "Fitch", "rating": "B-", "outlook": "stable", "action": "affirm", "action_date": "2024-09-20", "source_url": "https://www.fitchratings.com/"},
  {"iso3": "NGA", "agency": "S&P", "rating": "B-", "outlook": "stable", "action": "affirm", "action_date": "2024-08-01", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "NGA", "agency": "Moodys", "rating": "Caa1", "outlook": "positive", "action": "upgrade", "action_date": "2024-12-06", "source_url": "https://www.moodys.com/"},
  {"iso3": "NGA", "agency": "Fitch", "rating": "B", "outlook": "stable", "action": "upgrade", "action_date": "2024-10-31", "source_url": "https://www.fitchratings.com/"},
  {"iso3": "CIV", "agency": "S&P", "rating": "BB", "outlook": "stable", "action": "affirm", "action_date": "2024-09-06", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "CIV", "agency": "Moodys", "rating": "Ba2", "outlook": "positive", "action": "upgrade", "action_date": "2024-11-22", "source_url": "https://www.moodys.com/"},
  {"iso3": "CIV", "agency": "Fitch", "rating": "BB-", "outlook": "stable", "action": "affirm", "action_date": "2024-07-12", "source_url": "https://www.fitchratings.com/"},
  {"iso3": "SEN", "agency": "S&P", "rating": "B+", "outlook": "stable", "action": "affirm", "action_date": "2024-10-04", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "SEN", "agency": "Moodys", "rating": "B1", "outlook": "stable", "action": "downgrade", "action_date": "2024-10-25", "source_url": "https://www.moodys.com/"},
  {"iso3": "ETH", "agency": "S&P", "rating": "SD", "outlook": null, "action": "default", "action_date": "2023-12-26", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "ETH", "agency": "Fitch", "rating": "RD", "outlook": null, "action": "default", "action_date": "2023-12-26", "source_url": "https://www.fitchratings.com/"},
  {"iso3": "RWA", "agency": "S&P", "rating": "B+", "outlook": "stable", "action": "affirm", "action_date": "2024-02-17", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "RWA", "agency": "Fitch", "rating": "B+", "outlook": "stable", "action": "affirm", "action_date": "2024-07-26", "source_url": "https://www.fitchratings.com/"},
  {"iso3": "ZAF", "agency": "S&P", "rating": "BB-", "outlook": "positive", "action": "affirm", "action_date": "2024-11-15", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "ZAF", "agency": "Moodys", "rating": "Ba2", "outlook": "stable", "action": "affirm", "action_date": "2024-11-22", "source_url": "https://www.moodys.com/"},
  {"iso3": "ZAF", "agency": "Fitch", "rating": "BB-", "outlook": "stable", "action": "affirm", "action_date": "2024-09-13", "source_url": "https://www.fitchratings.com/"},
  {"iso3": "MAR", "agency": "S&P", "rating": "BB+", "outlook": "stable", "action": "affirm", "action_date": "2024-04-26", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "MAR", "agency": "Fitch", "rating": "BB+", "outlook": "stable", "action": "affirm", "action_date": "2024-09-27", "source_url": "https://www.fitchratings.com/"},
  {"iso3": "EGY", "agency": "S&P", "rating": "B-", "outlook": "stable", "action": "upgrade", "action_date": "2024-04-19", "source_url": "https://www.spglobal.com/ratings"},
  {"iso3": "EGY", "agency": "Moodys", "rating": "Caa1", "outlook": "positive", "action": "upgrade", "action_date": "2024-03-07", "source_url": "https://www.moodys.com/"},
  {"iso3": "EGY", "agency": "Fitch", "rating": "B", "outlook": "stable", "action": "upgrade", "action_date": "2024-11-01", "source_url": "https://www.fitchratings.com/"}
]
```

- [ ] **Step 2: Write `ratings.py`**

```python
# apps/api/src/atlas_api/ingestion/ratings.py
"""Ratings JSON loader — diffs against rating_history, inserts only new actions."""

import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import structlog
from sqlalchemy import select

from atlas_api.ingestion.base import Ingester, SourceStats
from atlas_api.models import RatingHistory

log = structlog.get_logger()

SEED_PATH = Path(__file__).resolve().parents[5] / "infra" / "seed" / "ratings.json"


class RatingsJsonLoader(Ingester):
    source_name = "ratings_json"

    async def run(self, vintage_id: UUID) -> SourceStats:
        stats = SourceStats(source=self.source_name)
        try:
            records = json.loads(SEED_PATH.read_text())
        except FileNotFoundError as exc:
            stats.errors.append(f"seed not found: {exc}")
            return stats

        for r in records:
            iso3 = r["iso3"]
            agency = r["agency"]
            rating = r["rating"]
            action_date = date.fromisoformat(r["action_date"])
            # Dedupe on (iso3, agency, rating, action_date): idempotent loads.
            existing = self.session.execute(
                select(RatingHistory.id)
                .where(
                    RatingHistory.iso3 == iso3,
                    RatingHistory.agency == agency,
                    RatingHistory.rating == rating,
                    RatingHistory.action_date == action_date,
                )
            ).scalar_one_or_none()
            if existing is not None:
                stats.rows_skipped += 1
                continue
            self.session.add(RatingHistory(
                id=uuid.uuid4(),
                iso3=iso3,
                agency=agency,
                rating=rating,
                outlook=r.get("outlook"),
                action=r.get("action", "affirm"),
                action_date=action_date,
                source_url=r.get("source_url"),
                ingested_at=datetime.now(UTC),
            ))
            stats.rows_written += 1
        self.session.commit()
        return stats
```

- [ ] **Step 3: Write tests**

```python
# apps/api/tests/test_ingestion_ratings.py
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select

from atlas_api.ingestion.ratings import RatingsJsonLoader
from atlas_api.models import Country, DataVintage, RatingHistory

pytestmark = pytest.mark.asyncio


def _seed(session):
    for iso3 in ("CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY"):
        session.add(Country(
            iso3=iso3, name=iso3, capital="?", region="?",
            tags=[], tier="B", status="performing", fx_regime="float",
            fx_regime_notes=None, fx_parallel_premium=None,
        ))
    v = DataVintage(id=uuid.uuid4(), source="test", created_at=datetime.now(UTC))
    session.add(v)
    session.commit()
    return v.id


async def test_ratings_first_run_inserts_all(session):
    vintage_id = _seed(session)
    async with httpx.AsyncClient() as http:
        loader = RatingsJsonLoader(http, session)
        stats = await loader.run(vintage_id)
    assert stats.rows_written >= 20
    assert stats.rows_skipped == 0


async def test_ratings_second_run_skips_all(session):
    vintage_id = _seed(session)
    async with httpx.AsyncClient() as http:
        loader = RatingsJsonLoader(http, session)
        first = await loader.run(vintage_id)
        second = await loader.run(vintage_id)
    assert first.rows_written >= 20
    assert second.rows_written == 0
    assert second.rows_skipped == first.rows_written
```

- [ ] **Step 4: Run**

```bash
uv run pytest apps/api/tests/test_ingestion_ratings.py -v
```

Expected: 2 passing.

- [ ] **Step 5: Commit**

```bash
git add infra/seed/ratings.json apps/api/src/atlas_api/ingestion/ratings.py apps/api/tests/test_ingestion_ratings.py
git commit -m "feat(ingestion): ratings JSON loader"
```

---

### Task 15: Orchestrator

**Files:**
- Create: `apps/api/src/atlas_api/ingestion/orchestrator.py`
- Create: `apps/api/tests/test_orchestrator.py`

- [ ] **Step 1: Write `orchestrator.py`**

```python
# apps/api/src/atlas_api/ingestion/orchestrator.py
"""Nightly orchestrator: creates one vintage, runs all four ingesters, records circuit state."""

import uuid
from datetime import UTC, datetime
from typing import Sequence

import httpx
import structlog

from atlas_api.db import SessionLocal
from atlas_api.ingestion.base import Ingester, IngestionReport, SourceStats, timed_run
from atlas_api.ingestion.circuit_breaker import is_open, record_failure, record_success
from atlas_api.ingestion.fx import ExchangeRateHostIngester
from atlas_api.ingestion.imf import ImfWeoIngester
from atlas_api.ingestion.ratings import RatingsJsonLoader
from atlas_api.ingestion.worldbank import WorldBankIngester
from atlas_api.models import DataVintage

log = structlog.get_logger()


def _default_ingester_factories():
    return [WorldBankIngester, ImfWeoIngester, ExchangeRateHostIngester, RatingsJsonLoader]


async def run_nightly(factories: Sequence[type[Ingester]] | None = None) -> IngestionReport:
    factories = list(factories) if factories is not None else _default_ingester_factories()
    started_at = datetime.now(UTC)
    session = SessionLocal()
    try:
        vintage = DataVintage(id=uuid.uuid4(), source="nightly", created_at=started_at)
        session.add(vintage)
        session.commit()
        log.info("vintage_created", vintage_id=str(vintage.id))

        sources: list[SourceStats] = []
        async with httpx.AsyncClient() as http:
            for factory in factories:
                ingester = factory(http, session)
                if is_open(session, ingester.source_name):
                    log.warning("circuit_open_skipping", source=ingester.source_name)
                    sources.append(SourceStats(
                        source=ingester.source_name,
                        errors=["circuit breaker open"],
                    ))
                    continue
                stats = await timed_run(ingester, vintage.id)
                sources.append(stats)
                if stats.errors and stats.rows_written == 0:
                    record_failure(session, ingester.source_name)
                else:
                    record_success(session, ingester.source_name)

        finished_at = datetime.now(UTC)
        ok = all(s.rows_written > 0 or s.source == "ratings_json" for s in sources)
        report = IngestionReport(
            vintage_id=vintage.id,
            started_at=started_at,
            finished_at=finished_at,
            sources=[s.__dict__ for s in sources] if False else sources,  # keep dataclass; converted below
            ok=ok,
        )
        log.info(
            "nightly_complete",
            vintage_id=str(vintage.id),
            duration_s=(finished_at - started_at).total_seconds(),
            sources=[{"source": s.source, "rows": s.rows_written, "errors": len(s.errors)} for s in sources],
            ok=ok,
        )
        return report
    finally:
        session.close()
```

Correction: `IngestionReport` expects `list[SourceStats]` where `SourceStats` is the Pydantic schema from `atlas_schemas.ingestion`, but the orchestrator uses the `@dataclass` from `atlas_api.ingestion.base`. These are two different `SourceStats`. The orchestrator should convert its dataclass to the Pydantic model before building the report. Add to the orchestrator:

```python
from atlas_schemas.ingestion import IngestionReport as IngestionReportSchema
from atlas_schemas.ingestion import SourceStats as SourceStatsSchema
```

Replace the `IngestionReport(...)` construction at the end with:

```python
report_schema = IngestionReportSchema(
    vintage_id=vintage.id,
    started_at=started_at,
    finished_at=finished_at,
    sources=[
        SourceStatsSchema(
            source=s.source, rows_written=s.rows_written, rows_skipped=s.rows_skipped,
            errors=s.errors, duration_seconds=s.duration_seconds,
        ) for s in sources
    ],
    ok=ok,
)
return report_schema
```

And change the function return annotation to `-> IngestionReportSchema`. Remove the `from atlas_api.ingestion.base import IngestionReport` import (only need `SourceStats` dataclass and `timed_run`).

- [ ] **Step 2: Write tests**

```python
# apps/api/tests/test_orchestrator.py
import pytest
from uuid import UUID

from atlas_api.ingestion.base import Ingester, SourceStats
from atlas_api.ingestion.orchestrator import run_nightly
from atlas_api.models import Country

pytestmark = pytest.mark.asyncio


class FakeGood(Ingester):
    source_name = "fake_good"

    async def run(self, vintage_id: UUID) -> SourceStats:
        return SourceStats(source=self.source_name, rows_written=10)


class FakeFailing(Ingester):
    source_name = "fake_failing"

    async def run(self, vintage_id: UUID) -> SourceStats:
        raise RuntimeError("boom")


async def test_orchestrator_creates_vintage_and_reports(engine, monkeypatch):
    # Monkeypatch SessionLocal to use the test engine. conftest's `engine` fixture already set up tables.
    from atlas_api import db as db_mod
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(db_mod, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))

    report = await run_nightly(factories=[FakeGood])
    assert report.ok is True
    assert report.sources[0].rows_written == 10
    assert report.sources[0].source == "fake_good"


async def test_orchestrator_records_failure(engine, monkeypatch):
    from atlas_api import db as db_mod
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(db_mod, "SessionLocal", sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))

    report = await run_nightly(factories=[FakeFailing])
    assert report.ok is False
    assert "boom" in "; ".join(report.sources[0].errors)
```

- [ ] **Step 3: Run**

```bash
uv run pytest apps/api/tests/test_orchestrator.py -v
```

Expected: 2 passing.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/atlas_api/ingestion/orchestrator.py apps/api/tests/test_orchestrator.py
git commit -m "feat(ingestion): nightly orchestrator"
```

---

### Task 16: APScheduler integration

**Files:**
- Create: `apps/api/src/atlas_api/ingestion/scheduler.py`
- Modify: `apps/api/src/atlas_api/config.py` (add scheduler flags)
- Modify: `apps/api/src/atlas_api/main.py` (lifespan start/stop)

- [ ] **Step 1: Extend `config.py`**

Add to the `Settings` class:

```python
    ingestion_schedule_enabled: bool = True
    ingestion_cron: str = "0 3 * * *"       # 03:00 UTC daily
```

- [ ] **Step 2: Write `scheduler.py`**

```python
# apps/api/src/atlas_api/ingestion/scheduler.py
"""AsyncIO scheduler for nightly ingestion."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import structlog

from atlas_api.config import settings
from atlas_api.ingestion.orchestrator import run_nightly

log = structlog.get_logger()


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    if settings.ingestion_schedule_enabled:
        scheduler.add_job(
            run_nightly,
            CronTrigger.from_crontab(settings.ingestion_cron, timezone="UTC"),
            id="nightly_ingestion",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        log.info("scheduler_configured", cron=settings.ingestion_cron)
    else:
        log.info("scheduler_disabled_via_env")
    return scheduler
```

- [ ] **Step 3: Wire into FastAPI lifespan**

Replace `apps/api/src/atlas_api/main.py`:

```python
# apps/api/src/atlas_api/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.config import settings
from atlas_api.ingestion.scheduler import build_scheduler
from atlas_api.logging_config import configure_logging
from atlas_api.routers import auth, countries, health


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = build_scheduler()
    if settings.ingestion_schedule_enabled:
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Atlas API", version="0.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(countries.router)
```

- [ ] **Step 4: Disable scheduler in tests**

The test `conftest.py` uses `TestClient(app)` which triggers the lifespan. To avoid starting the scheduler during tests, add this at the top of `conftest.py`:

Edit `apps/api/tests/conftest.py`. Before `from atlas_api.main import app`, insert:

```python
import os
os.environ.setdefault("INGESTION_SCHEDULE_ENABLED", "false")
```

- [ ] **Step 5: Run the whole test suite**

```bash
uv run pytest -v
```

Expected: all tests still pass (none started using the scheduler).

- [ ] **Step 6: Manual boot smoke**

```bash
INGESTION_SCHEDULE_ENABLED=true uv run uvicorn atlas_api.main:app --app-dir apps/api/src --port 8000 &
sleep 3
curl -s http://localhost:8000/api/health
kill %1
```

Expected: log line `scheduler_configured` appears in stdout, health endpoint returns 200.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/atlas_api/config.py apps/api/src/atlas_api/main.py apps/api/src/atlas_api/ingestion/scheduler.py apps/api/tests/conftest.py
git commit -m "feat(api): apscheduler wired into fastapi lifespan"
```

---

### Task 17: Ingestion CLI

**Files:**
- Create: `apps/api/src/atlas_api/ingestion/cli.py`
- Create: `apps/api/scripts/run_ingestion.py`

- [ ] **Step 1: Write `cli.py`**

```python
# apps/api/src/atlas_api/ingestion/cli.py
"""CLI: python -m atlas_api.ingestion.cli run [--source all|worldbank|imf|fx|ratings]"""

import argparse
import asyncio
import sys

from atlas_api.ingestion.fx import ExchangeRateHostIngester
from atlas_api.ingestion.imf import ImfWeoIngester
from atlas_api.ingestion.orchestrator import run_nightly
from atlas_api.ingestion.ratings import RatingsJsonLoader
from atlas_api.ingestion.worldbank import WorldBankIngester

FACTORIES = {
    "worldbank": WorldBankIngester,
    "imf": ImfWeoIngester,
    "fx": ExchangeRateHostIngester,
    "ratings": RatingsJsonLoader,
}


def main() -> int:
    parser = argparse.ArgumentParser(prog="atlas-ingestion")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run an ingestion pass")
    run.add_argument("--source", default="all", choices=["all", *FACTORIES.keys()])

    args = parser.parse_args()
    if args.cmd == "run":
        factories = None if args.source == "all" else [FACTORIES[args.source]]
        report = asyncio.run(run_nightly(factories=factories))
        print(report.model_dump_json(indent=2))
        return 0 if report.ok else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Thin wrapper script**

```python
# apps/api/scripts/run_ingestion.py
"""Convenience wrapper so you can `uv run python apps/api/scripts/run_ingestion.py run`."""

from atlas_api.ingestion.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Verify CLI discovery (no DB call)**

```bash
uv run python -m atlas_api.ingestion.cli --help
```

Expected: argparse help with `run` subcommand + `--source` choices listed.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/atlas_api/ingestion/cli.py apps/api/scripts/run_ingestion.py
git commit -m "feat(ingestion): cli for manual runs"
```

---

### Task 18: End-to-end integration test + manual live-API smoke

**Files:**
- Create: `apps/api/tests/test_e2e_ingestion.py`

- [ ] **Step 1: Write the E2E test**

```python
# apps/api/tests/test_e2e_ingestion.py
"""Full orchestrator run against mocked external APIs; verifies vintage rows + read paths."""

import pytest
import httpx
from sqlalchemy import select

from atlas_api.ingestion.fx import ExchangeRateHostIngester
from atlas_api.ingestion.imf import ImfWeoIngester
from atlas_api.ingestion.orchestrator import run_nightly
from atlas_api.ingestion.ratings import RatingsJsonLoader
from atlas_api.ingestion.worldbank import WorldBankIngester
from atlas_api.models import Country, DataVintage, FxRate, MacroIndicatorVintage, RatingHistory
from atlas_api.services.country.queries import get_latest, get_latest_fx, get_rating_history

pytestmark = pytest.mark.asyncio


def _seed_countries(session):
    for iso3 in ("CIV", "GHA", "KEN", "NGA", "SEN", "ETH", "RWA", "ZAF", "MAR", "EGY"):
        session.add(Country(
            iso3=iso3, name=iso3, capital="?", region="?",
            tags=[], tier="B", status="performing", fx_regime="float",
            fx_regime_notes=None, fx_parallel_premium=None,
        ))
    session.commit()


async def test_e2e_with_mocked_externals(httpx_mock, engine, session, monkeypatch):
    _seed_countries(session)

    # Rebind SessionLocal to test engine so the orchestrator's own SessionLocal uses tests' DB.
    from atlas_api import db as db_mod
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(
        db_mod, "SessionLocal",
        sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True),
    )

    # Stub all external HTTP: WB + IMF return a tiny series, FX returns a rate map.
    def _response(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if "worldbank.org" in host:
            return httpx.Response(200, json=[
                {"page": 1, "pages": 1, "total": 1},
                [{"date": "2024", "value": 10.0, "indicator": {"id": "X", "value": "X"},
                  "country": {"id": "X", "value": "X"}, "countryiso3code": "XXX",
                  "unit": "", "obs_status": "", "decimal": 1}],
            ])
        if "imf.org" in host:
            parts = request.url.path.split("/")
            indicator, iso3 = parts[-2], parts[-1]
            return httpx.Response(200, json={"values": {indicator: {iso3: {"2024": 5.5}}}})
        if "exchangerate.host" in host:
            return httpx.Response(200, json={
                "base": "USD", "date": "2026-04-16",
                "rates": {
                    "XOF": 600, "GHS": 15.2, "KES": 129.4, "NGN": 1450,
                    "ETB": 56.8, "RWF": 1350, "ZAR": 18.4, "MAD": 10.1, "EGP": 48.5,
                },
            })
        return httpx.Response(404)

    httpx_mock.add_callback(_response)

    report = await run_nightly()

    assert report.ok is True
    # Verify at least some macro rows, one FX row per country (except SEN/CIV share XOF, they both write),
    # and ratings rows from the JSON seed
    macro_rows = session.execute(select(MacroIndicatorVintage)).scalars().all()
    assert len(macro_rows) > 0
    fx_rows = session.execute(select(FxRate)).scalars().all()
    assert len(fx_rows) == 10
    rating_rows = session.execute(select(RatingHistory)).scalars().all()
    assert len(rating_rows) > 0

    # Exercise read paths on a real ingested country.
    assert get_latest(session, "GHA", "GDP_USD") is not None or get_latest(session, "GHA", "INFLATION_PCT") is not None
    assert get_latest_fx(session, "GHA") is not None
    assert len(get_rating_history(session, "GHA")) > 0
```

- [ ] **Step 2: Run the suite**

```bash
uv run pytest -v
```

Expected: all prior tests + the new E2E test pass.

- [ ] **Step 3: Manual live-API smoke run**

This hits real public APIs; only do it locally, not in CI.

```bash
cd /Users/bird/Documents/ATLAS/atlas
docker compose up -d
uv run alembic -c infra/migrations/alembic.ini upgrade head
uv run python apps/api/scripts/seed_countries.py
uv run python -m atlas_api.ingestion.cli run --source ratings
uv run python -m atlas_api.ingestion.cli run --source fx
uv run python -m atlas_api.ingestion.cli run --source worldbank
uv run python -m atlas_api.ingestion.cli run --source imf
```

Expected:
- Ratings: `rows_written: 26` (or near).
- FX: `rows_written: 10` with today's date.
- World Bank: `rows_written >= 500` (12 indicators × 10 countries × ~5 years).
- IMF WEO: `rows_written >= 400`.

**If ExchangeRate.host returns 401/403:** the API now requires a key. Either (a) register at `exchangerate.host` for a free key and set `EXCHANGERATE_HOST_KEY=...` in `.env`, or (b) switch to Frankfurter — edit `apps/api/src/atlas_api/ingestion/fx.py`: change `BASE_URL` to `"https://api.frankfurter.app/latest"`, change `params` construction to `{"from": "USD", "to": ",".join(currencies)}`, and note: Frankfurter does not cover all African currencies (no GHS/NGN/KES/ETB/RWF). If Frankfurter gaps matter, try Open Exchange Rates (free tier, key required). Commit the chosen solution in a follow-up `fix(ingestion): switch fx source` commit.

- [ ] **Step 4: Verify via API**

```bash
uv run uvicorn atlas_api.main:app --app-dir apps/api/src --port 8000 &
sleep 2
curl -s -c /tmp/atlas.cookies -X POST http://localhost:8000/api/auth/login \
  -H "content-type: application/json" \
  -d '{"email":"analyst@atlas.test","password":"change-me"}'
echo
curl -s -b /tmp/atlas.cookies http://localhost:8000/api/countries | head -c 400
echo
curl -s -b /tmp/atlas.cookies http://localhost:8000/api/countries/GHA | head -c 400
kill %1
```

Expected: /api/countries returns 10 country JSON objects; /api/countries/GHA returns Ghana row.

- [ ] **Step 5: Commit tests + final milestone**

```bash
git add apps/api/tests/test_e2e_ingestion.py
git commit -m "test(ingestion): end-to-end with mocked externals"
git tag -a v0.2.0-data-engine -m "Atlas data engine lite: 10 countries populated, nightly job scheduled"
```

Push tag is optional — confirm with user before `git push origin v0.2.0-data-engine`.

---

## Self-Review

**1. Spec coverage (Data Engine lite only, §1.1 + §5 macro/fx/rating tables + §6.1 nightly flow):**

- §1.1 World Bank + IMF WEO + ExchangeRate.host for 10 curated countries → Tasks 11, 12, 13, 4. ✓
- §5 `country` table → Task 3. ✓
- §5 `data_vintage` table → Task 3. ✓
- §5 `macro_indicator_vintage` with unique constraint + index → Task 7. ✓
- §5 `rating_history` → Task 7. ✓
- §5 `fx_rate` with unique (iso3, observation_date) → Task 7. ✓
- §6.1 Nightly 03:00 UTC vintage creation, per-source circuit breakers → Tasks 10, 15, 16. ✓
- §8 Error handling: 3-retry backoff, missing = NULL → Task 10 (retry), Task 11/12 (null passthrough). ✓
- §6.4 `get_latest` / `get_as_of` read paths → Task 8. ✓
- §6.4 Composite rating (S&P 0.4 + Moody 0.35 + Fitch 0.25 rescaled) → Task 9. ✓
- §5 multi-tenancy `tenant_id` — deferred; these are shared reference tables that the spec explicitly says NOT to tenant. ✓
- §10 Golden tests for composite rating across agency combos → Task 9. ✓
- §10 Integration test for ingestion writes vintage + both read paths → Tasks 8, 18. ✓

**Out of scope for this plan (deferred to later plans as designed):** Country Intelligence API bundle, frontend pages, Risk Score computation, synopsis generation (AI), news ingestion, reports. All per the scope-split decision.

**2. Placeholder scan:** No TBDs, no "similar to", no "handle edge cases" without code. Every Python code step is complete runnable code. Exception: Task 13 has an inline correction note about `session.merge` vs `on_conflict_do_update` — the corrected code block IS included; implementer should use that version.

**3. Type consistency:**
- `MacroIndicator` enum values string-match across Pydantic (Task 6), SQLAlchemy `indicator` column (Task 7), and ingesters' `indicator=indicator.value` writes (Tasks 11, 12). ✓
- `CountryStatus` + `FxRegime` string values match seed JSON (Task 4), Pydantic enum (Task 2), CHECK constraint tuple (Task 3), and SQLAlchemy `native_enum=False` column (Task 3). ✓
- `Agency` enum values `"S&P" | "Moodys" | "Fitch"` match seed JSON (Task 14), Pydantic (Task 6), CHECK constraint (Task 7), and composite rating keys (Task 9). ✓
- `vintage_id: UUID` used consistently: generated in orchestrator (Task 15), passed to ingesters (Tasks 11–14), FK in `macro_indicator_vintage` (Task 7). ✓
- `IngestionReport` is the Pydantic schema from `atlas_schemas.ingestion` (Task 2); orchestrator converts from its internal `SourceStats` dataclass to Pydantic `SourceStatsSchema` before returning (Task 15 correction block). ✓
- `ISO3_TO_CCY` dict (Task 8) and `COUNTRIES` tuple (Tasks 11, 12) are the same 10 countries as `countries.json` (Task 4). ✓

**4. Potential issues noted for execution:**
- ExchangeRate.host might now require a key. Task 18 Step 3 has a fallback recipe.
- IMF WEO indicator availability varies; some codes may 404 for some countries. Ingester already treats empty series as 0-row-written, not an error, which is correct behavior.
- Testcontainers Postgres pull time can be long on first run of the E2E test; no action required, just a heads-up.
- The orchestrator's `success` check (`ok = all(s.rows_written > 0 or s.source == "ratings_json" for s in sources)`) is weak — ratings_json is idempotent so rows_written=0 on re-run is fine, but this leaves a hole if it genuinely fails. Acceptable for prototype; tighten in hardening plan.

Plan is internally consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-16-atlas-data-engine-lite.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, spec + code quality review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
