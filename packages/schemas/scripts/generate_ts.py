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
    generate_typescript_defs(MODULE, str(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
