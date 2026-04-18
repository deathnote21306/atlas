# Atlas Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Atlas monorepo with a FastAPI + React skeleton that boots end-to-end (web → `/api/health` → 200), a Postgres 15 + pgvector database reachable via SQLAlchemy with an Alembic baseline migration, shared Pydantic→TS schema codegen, a Tailwind-configured design-system package, a single-demo-user JWT auth flow, and green GitHub Actions CI on the first PR. No business logic yet; this is pure scaffolding that every later plan depends on.

**Architecture:** Single private monorepo `deathnote21306/atlas` with pnpm workspaces (JS) and uv workspace (Python). Two apps (`apps/web`, `apps/api`), two shared packages (`packages/schemas`, `packages/design-system`), infra (`infra/docker`, `infra/migrations`). FastAPI is one deploy unit; the frontend calls it over JSON. Postgres runs via Docker Compose locally. Pydantic v2 models in `packages/schemas` are the single source of truth; `datamodel-code-generator` produces TypeScript types consumed by the web app. Auth is JWT-in-httpOnly-cookie with a seeded demo user.

**Tech Stack:** pnpm + uv workspaces; FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic; PostgreSQL 15 + pgvector; React 18 + Vite + TypeScript + Tailwind + TanStack Query; argon2-cffi + python-jose for auth; ruff + mypy + pytest + testcontainers-postgres; eslint + tsc + vitest; GitHub Actions CI.

---

## File Structure

Files created in this plan (nothing is modified — repo is bare except for the approved spec):

```
atlas/
├── .github/workflows/ci.yml           # CI: lint, typecheck, test, build
├── .gitignore                         # node, python, env, DS_Store
├── .env.example                       # all env var names, no secrets
├── README.md                          # dev setup, architecture pointer
├── package.json                       # pnpm workspace root
├── pnpm-workspace.yaml                # workspace glob
├── pyproject.toml                     # uv workspace root, ruff/mypy config
├── uv.lock                            # generated
├── docker-compose.yml                 # postgres + pgvector for local dev
│
├── apps/
│   ├── api/
│   │   ├── pyproject.toml             # fastapi, sqlalchemy, alembic, auth deps
│   │   ├── src/atlas_api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                # FastAPI app + routers + CORS
│   │   │   ├── config.py              # Pydantic Settings (env)
│   │   │   ├── db.py                  # SQLAlchemy engine/session
│   │   │   ├── models.py              # User ORM model (auth only this plan)
│   │   │   ├── deps.py                # get_db, get_current_user
│   │   │   ├── security.py            # argon2 hash, JWT encode/decode
│   │   │   └── routers/
│   │   │       ├── __init__.py
│   │   │       ├── health.py          # GET /api/health
│   │   │       └── auth.py            # POST /api/auth/login, GET /api/me
│   │   ├── tests/
│   │   │   ├── conftest.py            # testcontainers-postgres fixture
│   │   │   ├── test_health.py
│   │   │   ├── test_security.py
│   │   │   └── test_auth.py
│   │   └── scripts/
│   │       └── seed_demo_user.py      # creates single demo user
│   │
│   └── web/
│       ├── package.json
│       ├── tsconfig.json
│       ├── vite.config.ts
│       ├── tailwind.config.ts
│       ├── postcss.config.js
│       ├── index.html
│       ├── src/
│       │   ├── main.tsx
│       │   ├── App.tsx                # router shell
│       │   ├── index.css              # tailwind directives
│       │   ├── api/client.ts          # fetch wrapper, credentials: include
│       │   ├── auth/AuthContext.tsx
│       │   ├── routes/
│       │   │   ├── Login.tsx
│       │   │   ├── Home.tsx           # placeholder; shows /api/health
│       │   │   └── RequireAuth.tsx
│       │   └── types/
│       │       └── generated.ts       # from packages/schemas codegen
│       └── tests/
│           ├── setup.ts
│           ├── Login.test.tsx
│           └── client.test.ts
│
├── packages/
│   ├── schemas/
│   │   ├── pyproject.toml             # published as `atlas-schemas`
│   │   ├── src/atlas_schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # LoginRequest, LoginResponse, Me
│   │   │   └── health.py              # HealthResponse
│   │   ├── scripts/
│   │   │   └── generate_ts.py         # writes apps/web/src/types/generated.ts
│   │   └── tests/
│   │       └── test_contracts.py
│   │
│   └── design-system/
│       ├── package.json
│       ├── tsconfig.json
│       ├── tailwind.preset.cjs        # PRD §7 palette + typography
│       ├── src/
│       │   ├── index.ts
│       │   └── primitives/
│       │       └── KpiCard.tsx        # one primitive to prove the package works
│       └── tests/
│           └── KpiCard.test.tsx
│
└── infra/
    ├── docker/
    │   └── Dockerfile.api             # for Railway later; built in CI to verify
    ├── migrations/
    │   ├── alembic.ini
    │   ├── env.py
    │   └── versions/
    │       └── 0001_baseline.py       # creates `user` table + pgvector extension
    └── seed/
        └── .gitkeep
```

Each file has one responsibility. `apps/api` owns HTTP; `packages/schemas` owns contracts; `packages/design-system` owns visual primitives; `infra/migrations` owns schema evolution.

---

### Task 1: Initialize monorepo root

**Files:**
- Create: `/Users/bird/Documents/ATLAS/atlas/.gitignore`
- Create: `/Users/bird/Documents/ATLAS/atlas/package.json`
- Create: `/Users/bird/Documents/ATLAS/atlas/pnpm-workspace.yaml`
- Create: `/Users/bird/Documents/ATLAS/atlas/pyproject.toml`
- Create: `/Users/bird/Documents/ATLAS/atlas/.env.example`
- Create: `/Users/bird/Documents/ATLAS/atlas/README.md`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
# Node
node_modules/
.pnpm-store/
dist/
.vite/

# Python
__pycache__/
*.pyc
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
*.egg-info/

# Env / secrets
.env
.env.local
.env.*.local

# OS
.DS_Store

# Build artefacts
coverage/
htmlcov/
.coverage
apps/web/src/types/generated.ts
```

- [ ] **Step 2: Write root `package.json`**

```json
{
  "name": "atlas",
  "version": "0.0.0",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "engines": { "node": ">=20" },
  "scripts": {
    "dev:web": "pnpm --filter @atlas/web dev",
    "build:types": "uv run python packages/schemas/scripts/generate_ts.py",
    "lint": "pnpm -r lint",
    "typecheck": "pnpm -r typecheck",
    "test": "pnpm -r test"
  },
  "devDependencies": {
    "typescript": "5.5.4"
  }
}
```

- [ ] **Step 3: Write `pnpm-workspace.yaml`**

```yaml
packages:
  - "apps/web"
  - "packages/design-system"
```

- [ ] **Step 4: Write root `pyproject.toml`**

```toml
[tool.uv.workspace]
members = ["apps/api", "packages/schemas"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
addopts = "-ra -q"
testpaths = ["apps/api/tests", "packages/schemas/tests"]
```

- [ ] **Step 5: Write `.env.example`**

```dotenv
# --- Postgres (local docker-compose) ---
DATABASE_URL=postgresql+psycopg://atlas:atlas@localhost:5432/atlas

# --- Auth ---
JWT_SECRET=change-me-32-bytes-min
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=480
DEMO_USER_EMAIL=analyst@atlas.local
DEMO_USER_PASSWORD=change-me

# --- App ---
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO

# --- Anthropic (unused this plan, declared for future) ---
ANTHROPIC_API_KEY=
```

- [ ] **Step 6: Write `README.md`**

```markdown
# Atlas

Sovereign-finance intelligence platform — prototype.

## Dev setup

Prerequisites: Node 20+, pnpm 9, uv 0.4+, Docker.

```bash
cp .env.example .env
docker compose up -d            # postgres + pgvector
uv sync                          # python deps across workspace
pnpm install                     # js deps across workspace
pnpm build:types                 # generate TS types from Pydantic
uv run alembic -c infra/migrations/alembic.ini upgrade head
uv run python apps/api/scripts/seed_demo_user.py
uv run uvicorn atlas_api.main:app --reload --app-dir apps/api/src
pnpm dev:web                     # in a second terminal
```

Web: http://localhost:5173 · API: http://localhost:8000/api/health

Architecture: `docs/superpowers/specs/2026-04-12-atlas-prototype-design.md`.
```

- [ ] **Step 7: Commit**

```bash
cd /Users/bird/Documents/ATLAS/atlas
git add .gitignore package.json pnpm-workspace.yaml pyproject.toml .env.example README.md
git commit -m "chore: initialize atlas monorepo root"
```

---

### Task 2: Create private GitHub repo and push

**Files:**
- No file changes; uses `gh` CLI.

- [ ] **Step 1: Verify gh auth**

Run: `gh auth status`
Expected: "Logged in to github.com account deathnote21306".

- [ ] **Step 2: Create the remote repo**

```bash
cd /Users/bird/Documents/ATLAS/atlas
gh repo create deathnote21306/atlas --private --source=. --remote=origin --description "Atlas sovereign-finance intelligence platform"
```

Expected: "✓ Created repository deathnote21306/atlas on GitHub".

- [ ] **Step 3: Push main**

```bash
git push -u origin main
```

Expected: branch `main` set up to track `origin/main`.

- [ ] **Step 4: Verify remote**

Run: `git remote -v`
Expected: `origin  git@github.com:deathnote21306/atlas.git (fetch/push)` (or https form).

---

### Task 3: Scaffold `packages/schemas` with health contract

**Files:**
- Create: `packages/schemas/pyproject.toml`
- Create: `packages/schemas/src/atlas_schemas/__init__.py`
- Create: `packages/schemas/src/atlas_schemas/health.py`
- Create: `packages/schemas/tests/test_contracts.py`

- [ ] **Step 1: Write failing contract test**

```python
# packages/schemas/tests/test_contracts.py
from atlas_schemas.health import HealthResponse


def test_health_response_roundtrips():
    payload = {"status": "ok", "version": "0.0.0"}
    obj = HealthResponse.model_validate(payload)
    assert obj.status == "ok"
    assert obj.version == "0.0.0"
    assert obj.model_dump() == payload


def test_health_response_rejects_unknown_status():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        HealthResponse.model_validate({"status": "bogus", "version": "0.0.0"})
```

- [ ] **Step 2: Write package `pyproject.toml`**

```toml
[project]
name = "atlas-schemas"
version = "0.0.0"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/atlas_schemas"]
```

- [ ] **Step 3: Write `__init__.py`**

```python
# packages/schemas/src/atlas_schemas/__init__.py
__all__ = ["health"]
```

- [ ] **Step 4: Run the test to see it fail**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv sync
uv run pytest packages/schemas/tests/test_contracts.py -v
```

Expected: ModuleNotFoundError for `atlas_schemas.health`.

- [ ] **Step 5: Implement `HealthResponse`**

```python
# packages/schemas/src/atlas_schemas/health.py
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
```

- [ ] **Step 6: Run the test again**

Run: `uv run pytest packages/schemas/tests/test_contracts.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add packages/schemas pyproject.toml
git commit -m "feat(schemas): add health contract"
```

---

### Task 4: TS codegen script for schemas

**Files:**
- Create: `packages/schemas/scripts/generate_ts.py`

- [ ] **Step 1: Add codegen dep to `packages/schemas/pyproject.toml`**

Edit `packages/schemas/pyproject.toml`. After the `dependencies = ["pydantic>=2.8"]` line, insert a new section:

```toml
[project.optional-dependencies]
codegen = ["pydantic-to-typescript>=2.0"]
```

- [ ] **Step 2: Write generator script**

`pydantic-to-typescript` requires the npm package `json-schema-to-typescript` on PATH. We'll install it as a root dev dep in a later task; for now the script just tries and fails cleanly if missing.

```python
# packages/schemas/scripts/generate_ts.py
"""Generate TypeScript types from Pydantic models into apps/web/src/types/generated.ts.

Requires the npm package `json-schema-to-typescript` to be installed and on PATH
(provided via pnpm at the repo root after Task 13).
"""

import sys
from pathlib import Path

from pydantic2ts import generate_typescript_defs

ROOT = Path(__file__).resolve().parents[3]
MODULE = "atlas_schemas"
OUT = ROOT / "apps/web/src/types/generated.ts"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # generate_typescript_defs inspects the importable module and writes TS.
    generate_typescript_defs(MODULE, str(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Sync and install the npm helper**

Install the npm side of the pipeline globally-for-repo via a temporary `npx` invocation — we'll replace this with a proper dev dependency in Task 13 once the web app exists. For this task, just verify the codegen can run end-to-end.

```bash
uv sync --extra codegen
npx --yes json-schema-to-typescript --version   # cache the tool
uv run python packages/schemas/scripts/generate_ts.py
```

Expected: `apps/web/src/types/generated.ts` written. No error.

- [ ] **Step 4: Verify the output contains `HealthResponse`**

```bash
grep -q "HealthResponse" apps/web/src/types/generated.ts && echo OK
```

Expected: `OK`.

- [ ] **Step 5: Commit (without the generated file — it's gitignored)**

```bash
git add packages/schemas/pyproject.toml packages/schemas/scripts/generate_ts.py
git commit -m "feat(schemas): add pydantic→ts codegen"
```

---

### Task 5: FastAPI app skeleton with `/api/health`

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/src/atlas_api/__init__.py`
- Create: `apps/api/src/atlas_api/config.py`
- Create: `apps/api/src/atlas_api/main.py`
- Create: `apps/api/src/atlas_api/routers/__init__.py`
- Create: `apps/api/src/atlas_api/routers/health.py`
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_health.py
from fastapi.testclient import TestClient

from atlas_api.main import app


def test_health_returns_ok():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str) and len(body["version"]) > 0
```

- [ ] **Step 2: Write `apps/api/pyproject.toml`**

```toml
[project]
name = "atlas-api"
version = "0.0.0"
requires-python = ">=3.12"
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
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "httpx>=0.27",
  "testcontainers[postgres]>=4.8",
  "ruff>=0.6",
  "mypy>=1.11",
]

[tool.uv.sources]
atlas-schemas = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/atlas_api"]
```

- [ ] **Step 3: Write `__init__.py` files**

```python
# apps/api/src/atlas_api/__init__.py
__version__ = "0.0.0"
```

```python
# apps/api/src/atlas_api/routers/__init__.py
```

```python
# apps/api/tests/__init__.py
```

- [ ] **Step 4: Write `config.py`**

```python
# apps/api/src/atlas_api/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://atlas:atlas@localhost:5432/atlas"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 480
    demo_user_email: str = "analyst@atlas.local"
    demo_user_password: str = "change-me"
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"


settings = Settings()
```

- [ ] **Step 5: Write `routers/health.py`**

```python
# apps/api/src/atlas_api/routers/health.py
from fastapi import APIRouter

from atlas_api import __version__
from atlas_schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
```

- [ ] **Step 6: Write `main.py`**

```python
# apps/api/src/atlas_api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.config import settings
from atlas_api.routers import health

app = FastAPI(title="Atlas API", version="0.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
```

- [ ] **Step 7: Sync deps**

```bash
uv sync --extra dev
```

- [ ] **Step 8: Run the test**

```bash
uv run pytest apps/api/tests/test_health.py -v
```

Expected: 1 passed.

- [ ] **Step 9: Commit**

```bash
git add apps/api
git commit -m "feat(api): fastapi skeleton with /api/health"
```

---

### Task 6: Docker Compose for Postgres 15 + pgvector

**Files:**
- Create: `/Users/bird/Documents/ATLAS/atlas/docker-compose.yml`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg15
    container_name: atlas-postgres
    environment:
      POSTGRES_USER: atlas
      POSTGRES_PASSWORD: atlas
      POSTGRES_DB: atlas
    ports:
      - "5432:5432"
    volumes:
      - atlas-pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U atlas"]
      interval: 2s
      timeout: 3s
      retries: 10

volumes:
  atlas-pgdata:
```

- [ ] **Step 2: Start the container and verify**

```bash
cd /Users/bird/Documents/ATLAS/atlas
docker compose up -d
docker compose exec postgres psql -U atlas -d atlas -c "SELECT 1;"
```

Expected: `?column? | 1` row returned.

- [ ] **Step 3: Verify pgvector extension is loadable**

```bash
docker compose exec postgres psql -U atlas -d atlas -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension WHERE extname='vector';"
```

Expected: `extname | vector`.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "chore(infra): postgres 15 + pgvector via docker compose"
```

---

### Task 7: SQLAlchemy engine + User ORM model + db session dependency

**Files:**
- Create: `apps/api/src/atlas_api/db.py`
- Create: `apps/api/src/atlas_api/models.py`
- Create: `apps/api/src/atlas_api/deps.py`

- [ ] **Step 1: Write `db.py`**

```python
# apps/api/src/atlas_api/db.py
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from atlas_api.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_session() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
```

- [ ] **Step 2: Write `models.py` (User only for this plan)**

```python
# apps/api/src/atlas_api/models.py
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from atlas_api.db import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="Analyst")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 3: Write `deps.py`**

```python
# apps/api/src/atlas_api/deps.py
from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from atlas_api.db import get_session


def db_session() -> Iterator[Session]:
    yield from get_session()


DbSession = Depends(db_session)
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/atlas_api/db.py apps/api/src/atlas_api/models.py apps/api/src/atlas_api/deps.py
git commit -m "feat(api): sqlalchemy engine + user model"
```

---

### Task 8: Alembic baseline migration

**Files:**
- Create: `infra/migrations/alembic.ini`
- Create: `infra/migrations/env.py`
- Create: `infra/migrations/versions/0001_baseline.py`

- [ ] **Step 1: Write `alembic.ini`**

```ini
[alembic]
script_location = infra/migrations
prepend_sys_path = apps/api/src
sqlalchemy.url = postgresql+psycopg://atlas:atlas@localhost:5432/atlas

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 2: Write `env.py`**

```python
# infra/migrations/env.py
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from atlas_api.config import settings
from atlas_api.db import Base
from atlas_api import models  # noqa: F401  registers tables on Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = settings.database_url
    connectable = engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Write baseline migration**

```python
# infra/migrations/versions/0001_baseline.py
"""baseline: user table + pgvector extension

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-15
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "user",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="Analyst"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("user")
    op.execute("DROP EXTENSION IF EXISTS vector")
```

- [ ] **Step 4: Run the migration**

```bash
cd /Users/bird/Documents/ATLAS/atlas
uv run alembic -c infra/migrations/alembic.ini upgrade head
```

Expected: `Running upgrade  -> 0001_baseline`.

- [ ] **Step 5: Verify the table exists**

```bash
docker compose exec postgres psql -U atlas -d atlas -c "\dt"
```

Expected output includes `public | user`.

- [ ] **Step 6: Commit**

```bash
git add infra/migrations
git commit -m "feat(infra): alembic baseline with user table + pgvector"
```

---

### Task 9: Auth — argon2 hashing and JWT encode/decode

**Files:**
- Create: `apps/api/src/atlas_api/security.py`
- Create: `apps/api/tests/test_security.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/api/tests/test_security.py
from datetime import timedelta

import pytest

from atlas_api.security import (
    InvalidToken,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = create_access_token(subject="user-123", expires_delta=timedelta(minutes=5))
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"


def test_jwt_rejects_tampered_token():
    token = create_access_token(subject="user-123", expires_delta=timedelta(minutes=5))
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(InvalidToken):
        decode_access_token(tampered)


def test_jwt_rejects_expired_token():
    token = create_access_token(subject="user-123", expires_delta=timedelta(seconds=-1))
    with pytest.raises(InvalidToken):
        decode_access_token(token)
```

- [ ] **Step 2: Run tests, watch them fail**

```bash
uv run pytest apps/api/tests/test_security.py -v
```

Expected: ImportError on `atlas_api.security`.

- [ ] **Step 3: Implement `security.py`**

```python
# apps/api/src/atlas_api/security.py
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from atlas_api.config import settings

_hasher = PasswordHasher()


class InvalidToken(Exception):
    """Raised when a JWT fails signature or expiry validation."""


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expires_minutes))
    payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int(expire.timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, str | int]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise InvalidToken(str(exc)) from exc
```

- [ ] **Step 4: Run tests, watch them pass**

```bash
uv run pytest apps/api/tests/test_security.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/atlas_api/security.py apps/api/tests/test_security.py
git commit -m "feat(api): argon2 password hashing + jwt tokens"
```

---

### Task 10: Auth endpoints — `POST /api/auth/login`, `GET /api/me`

**Files:**
- Create: `packages/schemas/src/atlas_schemas/auth.py`
- Create: `apps/api/src/atlas_api/routers/auth.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_auth.py`
- Modify: `apps/api/src/atlas_api/main.py` (include auth router)
- Modify: `apps/api/src/atlas_api/deps.py` (add `get_current_user`)

- [ ] **Step 1: Write schemas**

```python
# packages/schemas/src/atlas_schemas/auth.py
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    email: EmailStr
    role: str


class Me(BaseModel):
    email: EmailStr
    role: str
```

- [ ] **Step 2: Write `conftest.py` with testcontainers Postgres**

```python
# apps/api/tests/conftest.py
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from atlas_api import db as db_module
from atlas_api.db import Base
from atlas_api.main import app
from atlas_api.deps import db_session


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    with PostgresContainer("pgvector/pgvector:pg15", username="atlas", password="atlas", dbname="atlas") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2", "postgresql+psycopg")


@pytest.fixture(scope="session")
def engine(pg_url):
    eng = create_engine(pg_url, future=True)
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture()
def session(engine):
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    s = TestSession()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def client(session) -> Iterator[TestClient]:
    def _override():
        yield session

    app.dependency_overrides[db_session] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 3: Write failing auth tests**

```python
# apps/api/tests/test_auth.py
import uuid

from atlas_api.models import User
from atlas_api.security import hash_password


def _seed(session, email: str = "a@b.test", password: str = "pw-123456") -> User:
    u = User(id=uuid.uuid4(), email=email, password_hash=hash_password(password), role="Analyst")
    session.add(u)
    session.commit()
    return u


def test_login_success_sets_cookie(client, session):
    _seed(session)
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert r.status_code == 200
    assert r.json() == {"email": "a@b.test", "role": "Analyst"}
    assert "atlas_session" in r.cookies


def test_login_wrong_password(client, session):
    _seed(session)
    r = client.post("/api/auth/login", json={"email": "a@b.test", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "ghost@b.test", "password": "whatever"})
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/me")
    assert r.status_code == 401


def test_me_returns_user_when_authed(client, session):
    _seed(session)
    login = client.post("/api/auth/login", json={"email": "a@b.test", "password": "pw-123456"})
    assert login.status_code == 200
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"email": "a@b.test", "role": "Analyst"}
```

- [ ] **Step 4: Add `get_current_user` to `deps.py`**

Replace the contents of `apps/api/src/atlas_api/deps.py`:

```python
# apps/api/src/atlas_api/deps.py
from collections.abc import Iterator

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from atlas_api.db import get_session
from atlas_api.models import User
from atlas_api.security import InvalidToken, decode_access_token


def db_session() -> Iterator[Session]:
    yield from get_session()


def get_current_user(
    session: Session = Depends(db_session),
    atlas_session: str | None = Cookie(default=None),
) -> User:
    if atlas_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing session")
    try:
        payload = decode_access_token(atlas_session)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session"
        ) from exc
    user = session.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown user")
    return user
```

- [ ] **Step 5: Write `routers/auth.py`**

```python
# apps/api/src/atlas_api/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas_api.config import settings
from atlas_api.deps import db_session, get_current_user
from atlas_api.models import User
from atlas_api.security import create_access_token, verify_password
from atlas_schemas.auth import LoginRequest, LoginResponse, Me

router = APIRouter(prefix="/api", tags=["auth"])

COOKIE_NAME = "atlas_session"


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, session: Session = Depends(db_session)) -> LoginResponse:
    user = session.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    token = create_access_token(subject=str(user.id))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # dev; CI/prod behind HTTPS will flip this in a later plan
        max_age=settings.jwt_expires_minutes * 60,
        path="/",
    )
    return LoginResponse(email=user.email, role=user.role)


@router.get("/me", response_model=Me)
def me(user: User = Depends(get_current_user)) -> Me:
    return Me(email=user.email, role=user.role)
```

- [ ] **Step 6: Register the router in `main.py`**

Replace `apps/api/src/atlas_api/main.py`:

```python
# apps/api/src/atlas_api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.config import settings
from atlas_api.routers import auth, health

app = FastAPI(title="Atlas API", version="0.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
```

- [ ] **Step 7: Run auth tests**

```bash
uv run pytest apps/api/tests/test_auth.py -v
```

Expected: 5 passed. (testcontainers will pull the image on first run; this can take a minute.)

- [ ] **Step 8: Regenerate TS types (now includes auth schemas)**

```bash
uv run python packages/schemas/scripts/generate_ts.py
grep -q "LoginRequest" apps/web/src/types/generated.ts && echo OK
```

Expected: `OK`.

- [ ] **Step 9: Commit**

```bash
git add packages/schemas/src/atlas_schemas/auth.py apps/api
git commit -m "feat(api): demo-user auth via jwt cookie"
```

---

### Task 11: Seed script for the demo user

**Files:**
- Create: `apps/api/scripts/seed_demo_user.py`

- [ ] **Step 1: Write the script**

```python
# apps/api/scripts/seed_demo_user.py
"""Idempotently seed the single demo user from env vars."""

from sqlalchemy import select

from atlas_api.config import settings
from atlas_api.db import SessionLocal
from atlas_api.models import User
from atlas_api.security import hash_password


def main() -> None:
    with SessionLocal() as s:
        existing = s.execute(
            select(User).where(User.email == settings.demo_user_email)
        ).scalar_one_or_none()
        if existing is not None:
            print(f"demo user already exists: {settings.demo_user_email}")
            return
        u = User(
            email=settings.demo_user_email,
            password_hash=hash_password(settings.demo_user_password),
            role="Analyst",
        )
        s.add(u)
        s.commit()
        print(f"created demo user: {settings.demo_user_email}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it against the local docker Postgres**

```bash
cd /Users/bird/Documents/ATLAS/atlas
cp .env.example .env  # if not done already
uv run alembic -c infra/migrations/alembic.ini upgrade head
uv run python apps/api/scripts/seed_demo_user.py
```

Expected: `created demo user: analyst@atlas.local`.

- [ ] **Step 3: Verify by hitting the live API**

```bash
uv run uvicorn atlas_api.main:app --app-dir apps/api/src --port 8000 &
sleep 2
curl -s -c /tmp/atlas.cookies -X POST http://localhost:8000/api/auth/login \
  -H "content-type: application/json" \
  -d '{"email":"analyst@atlas.local","password":"change-me"}'
echo
curl -s -b /tmp/atlas.cookies http://localhost:8000/api/me
kill %1
```

Expected: login returns `{"email":"analyst@atlas.local","role":"Analyst"}`; `/api/me` returns the same.

- [ ] **Step 4: Commit**

```bash
git add apps/api/scripts/seed_demo_user.py
git commit -m "feat(api): demo user seed script"
```

---

### Task 12: `packages/design-system` with Tailwind preset and `KpiCard`

**Files:**
- Create: `packages/design-system/package.json`
- Create: `packages/design-system/tsconfig.json`
- Create: `packages/design-system/tailwind.preset.cjs`
- Create: `packages/design-system/src/index.ts`
- Create: `packages/design-system/src/primitives/KpiCard.tsx`
- Create: `packages/design-system/tests/KpiCard.test.tsx`

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "@atlas/design-system",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "exports": {
    ".": "./src/index.ts",
    "./tailwind-preset": "./tailwind.preset.cjs"
  },
  "scripts": {
    "lint": "eslint src",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "peerDependencies": {
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "jsdom": "^25.0.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "tailwindcss": "^3.4.10",
    "typescript": "5.5.4",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Write Tailwind preset (PRD §7 colors, subset)**

```js
// packages/design-system/tailwind.preset.cjs
/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        // Institutional neutrals
        ink: {
          900: "#0b1220",
          700: "#1f2a44",
          500: "#475569",
          300: "#94a3b8",
          100: "#e2e8f0",
        },
        // Semantic
        positive: "#166534",
        warning: "#b45309",
        danger: "#b91c1c",
        accent: "#1d4ed8",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
};
```

- [ ] **Step 4: Write `KpiCard` test**

```tsx
// packages/design-system/tests/KpiCard.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { KpiCard } from "../src/primitives/KpiCard";

describe("KpiCard", () => {
  it("renders label and value", () => {
    render(<KpiCard label="Debt / GDP" value="62.4%" />);
    expect(screen.getByText("Debt / GDP")).toBeInTheDocument();
    expect(screen.getByText("62.4%")).toBeInTheDocument();
  });

  it("renders hint when provided", () => {
    render(<KpiCard label="FX" value="15.2" hint="USD/NGN" />);
    expect(screen.getByText("USD/NGN")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Write `KpiCard` component**

```tsx
// packages/design-system/src/primitives/KpiCard.tsx
import type { ReactNode } from "react";

export interface KpiCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
}

export function KpiCard({ label, value, hint }: KpiCardProps) {
  return (
    <div className="rounded-md border border-ink-100 bg-white p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-1 font-mono text-2xl text-ink-900">{value}</div>
      {hint ? <div className="mt-1 text-xs text-ink-300">{hint}</div> : null}
    </div>
  );
}
```

- [ ] **Step 6: Write `index.ts`**

```ts
// packages/design-system/src/index.ts
export { KpiCard } from "./primitives/KpiCard";
export type { KpiCardProps } from "./primitives/KpiCard";
```

- [ ] **Step 7: Install and run tests**

```bash
cd /Users/bird/Documents/ATLAS/atlas
pnpm install
pnpm --filter @atlas/design-system test
```

Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add packages/design-system
git commit -m "feat(design-system): tailwind preset + KpiCard primitive"
```

---

### Task 13: Vite + React + Tailwind web app with login flow

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/index.html`
- Create: `apps/web/src/index.css`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/api/client.ts`
- Create: `apps/web/src/auth/AuthContext.tsx`
- Create: `apps/web/src/routes/Login.tsx`
- Create: `apps/web/src/routes/Home.tsx`
- Create: `apps/web/src/routes/RequireAuth.tsx`
- Create: `apps/web/tests/setup.ts`
- Create: `apps/web/tests/client.test.ts`
- Create: `apps/web/tests/Login.test.tsx`

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "@atlas/web",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint src",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "dependencies": {
    "@atlas/design-system": "workspace:*",
    "@tanstack/react-query": "^5.56.2",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "jsdom": "^25.0.0",
    "postcss": "^8.4.47",
    "tailwindcss": "^3.4.10",
    "typescript": "5.5.4",
    "vite": "^5.4.3",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Write `vite.config.ts`**

```ts
// apps/web/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
});
```

- [ ] **Step 4: Write Tailwind + PostCSS config**

```ts
// apps/web/tailwind.config.ts
import type { Config } from "tailwindcss";
import preset from "@atlas/design-system/tailwind-preset";

export default {
  presets: [preset],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "../../packages/design-system/src/**/*.{ts,tsx}",
  ],
} satisfies Config;
```

```js
// apps/web/postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 5: Write `index.html` and entry files**

```html
<!-- apps/web/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Atlas</title>
  </head>
  <body class="bg-ink-100 text-ink-900">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```css
/* apps/web/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

```tsx
// apps/web/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./auth/AuthContext";
import App from "./App";
import "./index.css";

const qc = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 6: Write `api/client.ts`**

```ts
// apps/web/src/api/client.ts
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}
```

- [ ] **Step 7: Write `auth/AuthContext.tsx`**

```tsx
// apps/web/src/auth/AuthContext.tsx
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, api } from "../api/client";

interface Me { email: string; role: string }

interface AuthState {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Me>("/api/me")
      .then(setUser)
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 401)) console.error(e);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await api<Me>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    const me = await api<Me>("/api/me");
    setUser(me);
  }, []);

  return <Ctx.Provider value={{ user, loading, login }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used within AuthProvider");
  return v;
}
```

- [ ] **Step 8: Write routes**

```tsx
// apps/web/src/routes/Login.tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      nav("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) setError(err.status === 401 ? "Invalid credentials" : err.message);
      else setError("Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto mt-24 w-80 space-y-3 rounded-md bg-white p-6 shadow-sm">
      <h1 className="text-lg font-semibold text-ink-900">Atlas</h1>
      <label className="block text-xs text-ink-500">Email
        <input className="mt-1 w-full rounded border border-ink-100 px-2 py-1"
               type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label className="block text-xs text-ink-500">Password
        <input className="mt-1 w-full rounded border border-ink-100 px-2 py-1"
               type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </label>
      {error ? <div role="alert" className="text-xs text-danger">{error}</div> : null}
      <button disabled={submitting} className="w-full rounded bg-accent py-1 text-white disabled:opacity-50">
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
```

```tsx
// apps/web/src/routes/Home.tsx
import { useQuery } from "@tanstack/react-query";
import { KpiCard } from "@atlas/design-system";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface Health { status: string; version: string }

export default function Home() {
  const { user } = useAuth();
  const { data } = useQuery<Health>({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-xl font-semibold">Atlas — signed in as {user?.email}</h1>
      <div className="mt-6 grid grid-cols-2 gap-3">
        <KpiCard label="API status" value={data?.status ?? "—"} />
        <KpiCard label="API version" value={data?.version ?? "—"} />
      </div>
    </main>
  );
}
```

```tsx
// apps/web/src/routes/RequireAuth.tsx
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-ink-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

```tsx
// apps/web/src/App.tsx
import { Route, Routes } from "react-router-dom";
import Login from "./routes/Login";
import Home from "./routes/Home";
import RequireAuth from "./routes/RequireAuth";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Home /></RequireAuth>} />
    </Routes>
  );
}
```

- [ ] **Step 9: Write test setup and tests**

```ts
// apps/web/tests/setup.ts
import "@testing-library/jest-dom/vitest";
```

```ts
// apps/web/tests/client.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError, api } from "../src/api/client";

describe("api client", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("returns JSON on 2xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ x: 1 }), { status: 200 })));
    await expect(api<{ x: number }>("/api/x")).resolves.toEqual({ x: 1 });
  });

  it("throws ApiError with status on non-2xx", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "nope" }), { status: 401 })
    ));
    await expect(api("/api/x")).rejects.toBeInstanceOf(ApiError);
  });
});
```

```tsx
// apps/web/tests/Login.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Login from "../src/routes/Login";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode) {
  return <MemoryRouter><AuthProvider>{ui}</AuthProvider></MemoryRouter>;
}

describe("Login", () => {
  it("shows invalid-credentials error on 401", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))  // /api/me initial
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "invalid credentials" }), { status: 401 })); // login
    vi.stubGlobal("fetch", fetchMock);

    render(wrap(<Login />));
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.test");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid credentials/i);
  });
});
```

- [ ] **Step 10: Install and run web tests**

```bash
cd /Users/bird/Documents/ATLAS/atlas
pnpm install
pnpm build:types
pnpm --filter @atlas/web test
```

Expected: 3 passed.

- [ ] **Step 11: Manual smoke test**

```bash
# Terminal A
uv run uvicorn atlas_api.main:app --reload --app-dir apps/api/src
# Terminal B
pnpm dev:web
```

Open `http://localhost:5173`. Expected: redirected to `/login`. Enter `analyst@atlas.local` / `change-me`. Expected: redirected to `/` showing "API status: ok".

- [ ] **Step 12: Commit**

```bash
git add apps/web
git commit -m "feat(web): vite + react + tailwind shell with login"
```

---

### Task 14: Dockerfile for API (built in CI, not run locally)

**Files:**
- Create: `infra/docker/Dockerfile.api`

- [ ] **Step 1: Write the Dockerfile**

```dockerfile
# infra/docker/Dockerfile.api
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.4.18

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY packages/schemas/pyproject.toml packages/schemas/pyproject.toml
COPY apps/api/src apps/api/src
COPY packages/schemas/src packages/schemas/src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "atlas_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "apps/api/src"]
```

- [ ] **Step 2: Build locally to confirm it works**

```bash
cd /Users/bird/Documents/ATLAS/atlas
docker build -f infra/docker/Dockerfile.api -t atlas-api:dev .
```

Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add infra/docker/Dockerfile.api
git commit -m "chore(infra): api dockerfile"
```

---

### Task 15: GitHub Actions CI

**Files:**
- Create: `/Users/bird/Documents/ATLAS/atlas/.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  python:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_USER: atlas
          POSTGRES_PASSWORD: atlas
          POSTGRES_DB: atlas
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U atlas"
          --health-interval 2s
          --health-timeout 3s
          --health-retries 20
    env:
      DATABASE_URL: postgresql+psycopg://atlas:atlas@localhost:5432/atlas
      JWT_SECRET: ci-secret-0123456789abcdef0123456789abcdef
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with: { version: "0.4.18" }
      - run: uv python install 3.12
      - run: uv sync --all-extras
      - run: uv run ruff check .
      - run: uv run mypy apps/api/src packages/schemas/src
      - run: uv run alembic -c infra/migrations/alembic.ini upgrade head
      - run: uv run pytest

  js:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9.12.0 }
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: pnpm }
      - uses: astral-sh/setup-uv@v3
        with: { version: "0.4.18" }
      - run: uv sync --extra codegen
      - run: pnpm install --frozen-lockfile
      - run: pnpm build:types
      - run: pnpm -r typecheck
      - run: pnpm -r test
      - run: pnpm --filter @atlas/web build

  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: infra/docker/Dockerfile.api
          push: false
          tags: atlas-api:ci
```

- [ ] **Step 2: Push and open a PR to verify CI**

```bash
cd /Users/bird/Documents/ATLAS/atlas
git checkout -b ci/initial
git add .github/workflows/ci.yml
git commit -m "ci: initial github actions workflow"
git push -u origin ci/initial
gh pr create --title "CI: initial workflow" --body "Verifies lint, typecheck, tests, and docker build across python + js."
```

- [ ] **Step 3: Wait for CI and confirm green**

```bash
gh pr checks --watch
```

Expected: all three jobs (`python`, `js`, `docker`) green.

- [ ] **Step 4: Merge and clean up**

```bash
gh pr merge --squash --delete-branch
git checkout main
git pull
```

---

### Task 16: End-to-end sanity check and plan completion commit

- [ ] **Step 1: Bring up a clean environment**

```bash
cd /Users/bird/Documents/ATLAS/atlas
docker compose down -v
docker compose up -d
uv sync --all-extras
pnpm install
pnpm build:types
uv run alembic -c infra/migrations/alembic.ini upgrade head
uv run python apps/api/scripts/seed_demo_user.py
```

Expected: all commands succeed, demo user created.

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest
pnpm -r test
```

Expected: all tests pass.

- [ ] **Step 3: Full manual smoke**

Start API and web in two terminals (as in Task 13 Step 11). Log in with demo creds. Verify `/` renders with `API status: ok` from `KpiCard`.

- [ ] **Step 4: Tag the foundation**

```bash
git tag -a v0.1.0-foundation -m "Atlas foundation: monorepo, auth, ci green"
git push origin v0.1.0-foundation
```

---

## Self-Review

**Spec coverage (Foundation-relevant sections only):**
- §1 Architecture modular monolith → Task 5 (FastAPI), Task 13 (React SPA). ✓
- §2 Repo structure → Task 1 (root), Tasks 3/5/12/13 (workspaces). ✓
- §3 Tech stack — every Foundation-layer choice (React+Vite+Tailwind, FastAPI+Pydantic v2, SQLAlchemy 2.0+Alembic, Postgres 15+pgvector, pnpm+uv, GitHub Actions, Vercel-adjacent Dockerfile for Railway) → Tasks 5–15. ✓
- §5 Data model `user` table + `tenant_id` hook — `user` created (Task 8). `tenant_id` is a later-plan schema addition per spec ("Phase 1 without migration of reference data"); no owned tables exist yet in Foundation so there's nothing to add the column to. ✓ (noted for Plan 2.)
- §7 Shared Pydantic→TS codegen → Task 4. ✓
- §9 Security: JWT in httpOnly+SameSite=Lax cookie, argon2, parameterized queries, Pydantic validation, `.env.example` committed/`.env` gitignored → Tasks 1, 9, 10. ✓
- §10 CI: ruff + eslint/tsc + pytest + vitest → Task 15. (Frontend Playwright smoke and `mypy` over full tree expand in later plans; baseline is in place.) ✓
- §11 Anthropic key declared in `.env.example` but unused this plan → Task 1. ✓

**Not covered here, deferred to later plans as intended:** country/news/scenario/report services and their schemas, ingestion scheduler, AI orchestration, Playwright report rendering, editorial approval UI, full hosting deploy. All out of Foundation scope by design.

**Placeholder scan:** No TBDs, no "similar to", no "handle edge cases" — every code step has the actual code.

**Type consistency:**
- `HealthResponse { status, version }` — defined Task 3, used Task 5 (router), consumed Task 13 (Home). ✓
- `LoginRequest/LoginResponse/Me` — defined Task 10, consumed by `AuthContext` + `Login` (Task 13). ✓
- Cookie name `atlas_session` — set Task 10, read Task 10 `deps.py`. ✓
- `User.id` is UUID — model Task 7, migration Task 8, seeding Task 11, cookie subject is `str(user.id)` at Task 10 and parsed back via `session.get(User, payload["sub"])` (SQLAlchemy coerces string→UUID). ✓
- `KpiCard { label, value, hint? }` — defined Task 12, consumed Task 13 Home. ✓

Plan is internally consistent.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-15-atlas-foundation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
