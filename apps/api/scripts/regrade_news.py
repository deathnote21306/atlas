"""Re-grade stored news articles against the new relevance policy.

Usage:
    PYTHONPATH=apps/api/src:packages/schemas/src .venv/bin/python \
        apps/api/scripts/regrade_news.py [batch_size]

Safe to run repeatedly. Each run grades up to batch_size items that have not
been graded yet, so run it until "seen" comes back as 0.
"""

from __future__ import annotations

import sys

from atlas_api.db import SessionLocal
from atlas_api.services.news.regrade import regrade_batch


def main() -> int:
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    with SessionLocal() as session:
        stats = regrade_batch(session, batch)
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
