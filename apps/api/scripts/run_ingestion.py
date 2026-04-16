"""Convenience wrapper so you can `uv run python apps/api/scripts/run_ingestion.py run`."""

from atlas_api.ingestion.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
