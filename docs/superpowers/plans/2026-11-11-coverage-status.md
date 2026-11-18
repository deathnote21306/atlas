# Coverage Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every country carries an explicit, honest coverage label (Full Intelligence, Standard Intelligence, Benchmark Data, Coming Soon) visible on the country list and the country page, satisfying CI-005.

**Architecture:** A `coverage_status` string column on `country`, constrained by a `CoverageStatus` StrEnum in the shared schemas package so the value crosses the Pydantic-to-TypeScript codegen boundary intact. A `CoverageBadge` design-system primitive owns the enum-to-display-label mapping and the colors, so no caller hardcodes a label. The badge is rendered in two places: a new Coverage column on the country list table, and the country page header.

**Tech Stack:** SQLAlchemy 2.0, Alembic, Pydantic v2, `atlas_schemas` workspace package, React 18, Tailwind, Vitest, Testing Library, pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-atlas-prd-v2.md`

## Global Constraints

- The four coverage values are exactly `full`, `standard`, `benchmark`, `coming_soon`. Their display labels are exactly `Full Intelligence`, `Standard Intelligence`, `Benchmark Data`, `Coming Soon` (CI-005, copied verbatim).
- The existing `tier` column (values `A`, `B`, `C`) is market tiering and a different axis. Do not reuse, rename or overload it.
- CI-004: missing or unverified information displays N/A or unavailable. A coverage label must never imply data that is not there.
- §02 non-goal: no opaque score replacing professional judgment. The badge shows a named label, never a number.
- §16: contrast compliant with WCAG AA where practical, and the label must be legible without relying on color alone.
- No new runtime dependencies.
- Migration revision id is `0019_country_coverage_status`, `down_revision = "0018_report_pdf_bytes"`.

## Assignment decision (recorded, not open)

All ten existing countries are seeded as `standard`, not `full`. Four of the eight pillars required by CI-002 (politics, companies, finance, infrastructure, regulation) do not exist yet for any country, so no country can honestly be labeled Full Intelligence today. Gabon arrives as `standard` in Plan 2 and is promoted to `full` in Plan 5, when the pillars that justify the label exist. The column default for any newly ingested country is `coming_soon`.

## Review Focus

1. **A country row inserted without an explicit value** (a new country arrives via ingestion, not the seed) must come back as `coming_soon`, not null and not a 500. Test in Task 1.
2. **A legacy or hand-edited value not in the enum** reaching the badge must render a neutral fallback rather than crashing the country list. Test in Task 2.
3. **A `coming_soon` country must not render as though it has data** — the badge is not a substitute for CI-004 behavior, and the list row must still show its real empty cells. Test in Task 3.
4. **The badge must be readable without color** — the accessible name must carry the full label text, so a screen reader and a monochrome display both convey it. Test in Task 2.
5. **The enum must survive codegen** — if `coverage_status` is absent from `apps/web/src/types/generated.ts` the frontend silently drifts from the API contract. Test in Task 1.

---

### Task 1: Coverage status on the country model

**Files:**
- Modify: `packages/schemas/src/atlas_schemas/country.py` (add `CoverageStatus`, add field to `Country`)
- Modify: `apps/api/src/atlas_api/models.py:48` (add column after `tier`)
- Create: `infra/migrations/versions/0019_country_coverage_status.py`
- Modify: `infra/seed/countries.json` (add `"coverage_status": "standard"` to all ten records)
- Modify: `apps/web/src/types/generated.ts` (regenerated, not hand-edited)
- Test: `apps/api/tests/test_countries.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `CoverageStatus` StrEnum with members `FULL = "full"`, `STANDARD = "standard"`, `BENCHMARK = "benchmark"`, `COMING_SOON = "coming_soon"`, importable from `atlas_schemas.country`. `Country.coverage_status: CoverageStatus` on both the Pydantic schema and the ORM model.

- [ ] **Step 1: Write the failing tests**

Add to `apps/api/tests/test_countries.py`. Note `_seed_country` does not pass `coverage_status`, which is what makes the second test meaningful.

```python
def test_country_exposes_coverage_status(client, session):
    _seed_user(session)
    session.add(Country(
        iso3="GHA", name="Ghana", capital="Accra", region="West Africa",
        tags=["SSA"], tier="C", status="restructured", fx_regime="float",
        coverage_status="standard",
    ))
    session.commit()
    _login(client)
    r = client.get("/api/countries/GHA")
    assert r.status_code == 200
    assert r.json()["coverage_status"] == "standard"


def test_country_without_explicit_coverage_defaults_to_coming_soon(client, session):
    _seed_user(session)
    _seed_country(session, "KEN")
    _login(client)
    r = client.get("/api/countries/KEN")
    assert r.status_code == 200
    assert r.json()["coverage_status"] == "coming_soon"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_countries.py -k coverage -v`
Expected: FAIL, `KeyError: 'coverage_status'`

- [ ] **Step 3: Add `CoverageStatus` to `packages/schemas/src/atlas_schemas/country.py`**

A `StrEnum` beside the existing `CountryStatus` and `FxRegime`, with the four members from the Interfaces block. Add `coverage_status: CoverageStatus = CoverageStatus.COMING_SOON` to the `Country` model, placed after `tier`.

- [ ] **Step 4: Add the column to `apps/api/src/atlas_api/models.py`**

```python
coverage_status: Mapped[str] = mapped_column(
    String(16), nullable=False, server_default="coming_soon", default="coming_soon"
)
```

Both `server_default` and `default` are needed: the former for rows inserted by raw SQL and the migration backfill, the latter for rows the ORM constructs without the kwarg, which is the second test.

- [ ] **Step 5: Write the migration `infra/migrations/versions/0019_country_coverage_status.py`**

Follow the docstring-then-constants shape of `0018_report_pdf_bytes.py`. `upgrade()` adds the column with `server_default="coming_soon"` and `nullable=False`, then issues one `op.execute` setting the ten existing rows to `'standard'`. `downgrade()` drops the column.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/test_countries.py -v`
Expected: PASS, including the pre-existing tests in the file

- [ ] **Step 7: Add `"coverage_status": "standard"` to all ten records in `infra/seed/countries.json`**

- [ ] **Step 8: Regenerate the TypeScript types and confirm the field crossed the boundary**

Run: `chflags nohidden .venv/lib/python3.12/site-packages/*.pth 2>/dev/null; pnpm build:types && grep -c "coverage_status" apps/web/src/types/generated.ts`
Expected: a count of at least 1. A count of 0 means Review Focus item 5 has bitten and the schema change did not reach the frontend contract.

- [ ] **Step 9: Run the full API suite to confirm nothing regressed**

Run: `cd apps/api && uv run pytest -q`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add packages/schemas/src/atlas_schemas/country.py apps/api/src/atlas_api/models.py infra/migrations/versions/0019_country_coverage_status.py infra/seed/countries.json apps/web/src/types/generated.ts apps/api/tests/test_countries.py
git commit -m "feat(country): add coverage_status so depth is stated, not implied"
```

---

### Task 2: CoverageBadge primitive

**Files:**
- Create: `packages/design-system/src/primitives/CoverageBadge.tsx`
- Modify: `packages/design-system/src/index.ts`
- Test: `packages/design-system/tests/CoverageBadge.test.tsx`

**Interfaces:**
- Consumes: the four string values from Task 1. The prop is typed locally as a string union rather than importing the Python-generated type, matching how `RiskBadge` keeps `RiskLevel` local.
- Produces: `CoverageBadge` and `CoverageBadgeProps` exported from `@atlas/design-system`. Props: `{ status: string }`. Exported type `CoverageLevel = "full" | "standard" | "benchmark" | "coming_soon"`.

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CoverageBadge } from "../src/primitives/CoverageBadge";

describe("CoverageBadge", () => {
  it("renders the full label for each known status", () => {
    const cases: [string, string][] = [
      ["full", "Full Intelligence"],
      ["standard", "Standard Intelligence"],
      ["benchmark", "Benchmark Data"],
      ["coming_soon", "Coming Soon"],
    ];
    for (const [status, label] of cases) {
      const { unmount } = render(<CoverageBadge status={status} />);
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it("falls back to Unknown for an unrecognised status instead of crashing", () => {
    render(<CoverageBadge status="legacy_value" />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("carries the label in its accessible name so colour is not the only signal", () => {
    render(<CoverageBadge status="benchmark" />);
    expect(screen.getByTitle("Benchmark Data")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/design-system && pnpm vitest run --environment jsdom tests/CoverageBadge.test.tsx`
Expected: FAIL, cannot resolve `../src/primitives/CoverageBadge`

The `--environment jsdom` flag matters: this package's `test` script supplies it and there is no vitest config file, so a bare `vitest run` uses the node environment and every Testing Library render fails with an unrelated error.

- [ ] **Step 3: Implement `CoverageBadge({ status }: CoverageBadgeProps)` in `packages/design-system/src/primitives/CoverageBadge.tsx`**

Mirror `RiskBadge.tsx`: a `LABELS` record and a `COLORS` record keyed by `CoverageLevel`, a lookup that falls back to `"Unknown"` and a neutral `bg-[#21262d] text-ink-400` when the key is absent, and a single `<span>` carrying `title={label}`. Use the same base classes as `RiskBadge` (`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider`) so the badges sit together consistently. Suggested colors, following the existing token vocabulary: full `bg-positive/15 text-positive`, standard `bg-amber-500/15 text-amber-400`, benchmark `bg-[#21262d] text-ink-300`, coming_soon `bg-[#21262d] text-ink-500`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/design-system && pnpm test`
Expected: PASS, 3 new tests plus the 6 pre-existing primitive suites

- [ ] **Step 5: Export from `packages/design-system/src/index.ts`**

Add the `CoverageBadge` value export and the `CoverageBadgeProps` / `CoverageLevel` type exports, following the two-line-per-primitive pattern already in the file.

- [ ] **Step 6: Commit**

```bash
git add packages/design-system/src/primitives/CoverageBadge.tsx packages/design-system/src/index.ts packages/design-system/tests/CoverageBadge.test.tsx
git commit -m "feat(design-system): add CoverageBadge primitive"
```

---

### Task 3: Surface coverage on the country list and country page

**Files:**
- Modify: `apps/web/src/routes/CountriesList.tsx:11` (interface), table head near `:210`, row body near `:254`
- Modify: `apps/web/src/routes/CountryProfile.tsx:241` (header badge row)
- Test: `apps/web/tests/CountriesList.test.tsx`

**Interfaces:**
- Consumes: `CoverageBadge` from `@atlas/design-system` (Task 2); `coverage_status` on the `/api/countries` payload (Task 1).
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/tests/CountriesList.test.tsx`, following the existing mocking style in that file for the `/api/countries` response. Two tests:

```tsx
it("shows the coverage label for each country", async () => {
  // mock /api/countries with one country carrying coverage_status: "standard"
  expect(await screen.findByText("Standard Intelligence")).toBeInTheDocument();
});

it("still renders a coming_soon country's empty cells rather than implying data", async () => {
  // mock one country with coverage_status: "coming_soon" and no risk / spread / ratings
  expect(await screen.findByText("Coming Soon")).toBeInTheDocument();
  expect(screen.queryByText("NaN")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && pnpm vitest run tests/CountriesList.test.tsx`
Expected: FAIL, unable to find text "Standard Intelligence"

- [ ] **Step 3: Add `coverage_status: string;` to the `Country` interface at `CountriesList.tsx:11`**

- [ ] **Step 4: Add the Coverage column to the list table**

A `<th>` labelled `Coverage` between the existing `Region` and `Ratings (Norm.)` headers, matching their class list exactly, and a `<td className="px-4 py-3"><CoverageBadge status={c.coverage_status} /></td>` in the same position in the row body. Bump the loading-skeleton column count from 9 to 10 in both places it appears (`Array.from({ length: 9 })` and `colSpan={9}`).

- [ ] **Step 5: Add the badge to the country page header**

In the `flex items-center gap-3` container at `CountryProfile.tsx:241`, render `<CoverageBadge status={country.coverage_status} />` as the first child so coverage reads before the risk and status chips.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd apps/web && pnpm vitest run`
Expected: PASS, including the pre-existing `CountriesList` and `CountryProfile` tests

- [ ] **Step 7: Typecheck**

Run: `cd apps/web && pnpm typecheck`
Expected: no errors

- [ ] **Step 8: Verify in the browser**

Start the dev server and confirm the Coverage column renders on `/countries` and the badge renders in the `/countries/GHA` header. Screenshot both.

- [ ] **Step 9: Commit**

```bash
git add apps/web/src/routes/CountriesList.tsx apps/web/src/routes/CountryProfile.tsx apps/web/tests/CountriesList.test.tsx
git commit -m "feat(web): show coverage status on the country list and country page"
```

---

### Task 4: Remove the Deal Analysis navigation entry

**Files:**
- Modify: `apps/web/src/components/Sidebar.tsx:57-68`

**Interfaces:**
- Consumes: nothing. Produces: nothing.

§20 puts "Deal Analysis / DCF / IRR recommendation engine" explicitly out of scope. The sidebar currently advertises it as a disabled item with two disabled children, which promises a feature that has been decided against. No test references it, so removing it is a clean deletion.

- [ ] **Step 1: Delete the `Deal Analysis` entry from the `CORE MODULES` section**

Remove the whole object literal at `Sidebar.tsx:57-68`, including its `children` array and `expandKey: "deals"`.

- [ ] **Step 2: Confirm no dangling references**

Run: `cd /Users/bird/Documents/ATLAS/atlas && grep -rn "deals\|Deal Analysis" apps/web/src | grep -v node_modules`
Expected: no output

- [ ] **Step 3: Run the web suite**

Run: `cd apps/web && pnpm vitest run && pnpm typecheck`
Expected: PASS, no errors

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/Sidebar.tsx
git commit -m "chore(web): drop the Deal Analysis nav entry, out of scope per PRD v2"
```

---

## Done when

- `/api/countries` returns `coverage_status` for every country, defaulting to `coming_soon` for rows that do not set it.
- The ten seeded countries read `standard`.
- The country list has a Coverage column and the country page header carries the badge.
- `pnpm vitest run` passes in `apps/web` and `packages/design-system`; `uv run pytest` passes in `apps/api`.
- The Deal Analysis entry is gone from the sidebar.
