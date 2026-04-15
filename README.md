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
