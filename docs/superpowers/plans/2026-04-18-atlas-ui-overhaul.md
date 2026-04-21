# Atlas Plan 7: UI Overhaul — Dark Theme, Sidebar Nav, Dashboard & Missing Pages

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the prototype UI from a functional light-themed app with a top nav into the mockup's dark-themed, sidebar-navigated intelligence platform. Add the Dashboard ("Strategic Command Center"), Country Comparison page, and News & Event Intelligence page. Rework the Country Intelligence table and Scenario Engine to match mockup fidelity. No backend changes — all data comes from existing endpoints.

**Design reference:** Screenshots in `/Users/bird/Desktop/Atlas UI/` show 5 pages:
1. **Dashboard** — KPI row, Top Deteriorating/Improving lists, Live Alerts, Recent Rating Actions, Intelligence Feed
2. **Country Intelligence** — rich sortable table with rating stars, FX, ATLAS Risk/Alert scores
3. **Country Comparison** — side-by-side 2-3 country comparison with all indicators
4. **Scenario Engine** — dark theme, named presets, impact cards
5. **News & Event Intelligence** — Intelligence Feed + Event Calendar tabs, scored articles

**Architecture:** This is a frontend-only plan. All data comes from existing API endpoints (`/api/countries`, `/api/countries/:iso3/bundle`, `/api/scenarios/*`, `/api/news`, `/api/synopses/*`). No new backend endpoints needed — the Dashboard aggregates data client-side from existing endpoints.

**Tech stack additions:** None — existing React + Tailwind + TanStack Query stack is sufficient. The dark theme is a Tailwind color palette swap in the design-system preset.

---

## File Structure

Files created (C) or modified (M):

```
atlas/
├── packages/design-system/
│   ├── tailwind.preset.cjs                          (M) dark theme colors
│   └── src/primitives/
│       ├── KpiCard.tsx                              (M) dark theme support
│       ├── RatingBadge.tsx                           (M) dark theme support
│       ├── RiskBadge.tsx                             (M) dark theme support
│       ├── RiskGauge.tsx                             (M) dark theme support
│       ├── StalenessChip.tsx                         (M) dark theme support
│       ├── InstitutionalTable.tsx                    (M) dark theme support
│       ├── AlertBadge.tsx                            (C) alert severity badge
│       └── index.ts                                 (M) export new components
│
├── apps/web/src/
│   ├── index.css                                    (M) dark body background
│   ├── App.tsx                                      (M) new routes
│   ├── components/
│   │   ├── TopNav.tsx                               (DELETED — replaced by Sidebar)
│   │   ├── Sidebar.tsx                              (C) collapsible left sidebar
│   │   ├── SynopsisCard.tsx                         (M) dark theme
│   │   ├── NewsItemCard.tsx                         (M) dark theme
│   │   ├── Skeleton.tsx                             (M) dark theme
│   │   └── ErrorBoundary.tsx                        (M) dark theme
│   └── routes/
│       ├── AppShell.tsx                             (M) sidebar layout instead of top nav
│       ├── Home.tsx → Dashboard.tsx                  (M) full Strategic Command Center
│       ├── CountriesList.tsx                         (M) rich table view
│       ├── CountryComparison.tsx                     (C) side-by-side comparison
│       ├── CountryProfile.tsx                        (M) dark theme
│       ├── ScenarioEngine.tsx                        (M) dark theme + presets
│       ├── ScenarioView.tsx                          (M) dark theme
│       ├── NewsIntelligence.tsx                      (C) dedicated news page
│       ├── AdminSynopses.tsx                         (M) dark theme
│       └── Login.tsx                                 (M) dark theme
│
└── apps/web/tests/
    └── (existing tests updated for dark theme class changes)
```

---

## Tasks

### Task 1: Dark theme — Tailwind preset & global styles

**Why:** The mockup uses a dark navy/charcoal theme throughout. This is the foundation that everything else builds on.

**File:** `packages/design-system/tailwind.preset.cjs`

- [ ] **Step 1.** Replace the `ink` color scale with dark theme values:
  ```js
  ink: {
    950: "#030712",   // deepest background
    900: "#0b1220",   // sidebar/card background
    800: "#111827",   // main content background
    700: "#1f2937",   // elevated surfaces (cards, inputs)
    600: "#374151",   // borders, dividers
    500: "#6b7280",   // secondary text
    400: "#9ca3af",   // muted text, placeholders
    300: "#d1d5db",   // primary text on dark
    200: "#e5e7eb",   // emphasized text
    100: "#f3f4f6",   // headings, bright text
  }
  ```
- [ ] **Step 2.** Update semantic colors for better contrast on dark:
  ```js
  positive: "#22c55e",   // brighter green for dark bg
  warning: "#f59e0b",    // brighter amber
  danger: "#ef4444",     // brighter red
  accent: "#3b82f6",     // brighter blue
  ```
- [ ] **Step 3.** Add `atlas` brand color scale:
  ```js
  atlas: {
    400: "#60a5fa",
    500: "#3b82f6",
    600: "#2563eb",
    700: "#1d4ed8",
  }
  ```

**File:** `apps/web/src/index.css`

- [ ] **Step 4.** Add dark body background:
  ```css
  @layer base {
    body {
      @apply bg-ink-800 text-ink-300;
    }
  }
  ```

**Commit:** `feat(design): dark theme color palette`

---

### Task 2: Sidebar navigation

**Why:** The mockup has a collapsible left sidebar with hierarchical navigation, replacing the current top nav bar.

**File:** `apps/web/src/components/Sidebar.tsx` (C)

- [ ] **Step 1.** Create a sidebar component with:
  - Fixed left position, full height, `w-56` (collapsed: `w-14`)
  - Dark background: `bg-ink-900`
  - Atlas logo/brand at top
  - Navigation sections with icons (use simple SVG or Unicode symbols):
    - **Dashboard** → `/`
    - **Country Intelligence** → `/countries` (with sub-items: Country Comparison → `/countries/compare`)
    - **Scenario Engine** → `/scenarios/new`
    - **News & Events** → `/news`
    - **Reports** → (disabled/coming soon badge)
  - Active state: left border accent + `bg-ink-800` highlight
  - Collapse toggle button at bottom
  - Grayed-out items for deferred features (Deal Analysis, Live Monitoring, Reports) with "Soon" badge

**File:** `apps/web/src/routes/AppShell.tsx` (M)

- [ ] **Step 2.** Replace top nav layout with sidebar layout:
  ```tsx
  <div className="flex min-h-screen">
    <Sidebar />
    <main className="flex-1 overflow-auto p-6">
      {children}
    </main>
  </div>
  ```

**File:** `apps/web/src/components/TopNav.tsx` (delete or keep as inner header)

- [ ] **Step 3.** Either delete TopNav or convert it to a thin inner header bar showing current page title + user info on the right side. The mockup shows a small header inside the content area with breadcrumbs and user avatar — implement that as a `PageHeader` component inside AppShell.

**Commit:** `feat(web): sidebar navigation replacing top nav`

---

### Task 3: Dashboard — Strategic Command Center

**Why:** The mockup's home page is a rich dashboard, not a simple welcome screen. It aggregates data from existing endpoints.

**File:** `apps/web/src/routes/Dashboard.tsx` (rename from Home.tsx)

- [ ] **Step 1.** Top KPI row — 4-5 cards showing:
  - Countries Under Watch (count from `/api/countries`)
  - Countries at Risk (count where risk > threshold)
  - Active Alerts (count of high-impact news)
  - Average ATLAS Risk Score
  - Data Freshness / Staleness indicator
  Fetch from `/api/countries` and aggregate client-side.

- [ ] **Step 2.** Two-column layout below KPIs:
  **Left column:**
  - **Top Deteriorating** — 3-5 countries sorted by worst risk change, showing flag emoji + name + risk badge + trend arrow
  - **Top Improving** — 3-5 countries sorted by best risk change
  - **Recent Rating Actions** — table with date, country, agency, action (upgrade/downgrade), rating. Pull from country bundles' rating history.

  **Right column:**
  - **Live Alerts** — scrollable list of critical/warning alerts. Each alert shows severity badge (Critical/Warning/Info), message text, timestamp. Derive from high-scoring news items via `/api/news`.
  - **Intelligence Feed** — latest 5-10 news items with impact scores, similar to mockup's right panel. Fetch from `/api/news` without country filter.

- [ ] **Step 3.** Wire up navigation — clicking a country name navigates to `/countries/:iso3`, clicking a news item navigates to the news page.

- [ ] **Step 4.** Update `App.tsx` route: change `/` from `Home` to `Dashboard`.

**Commit:** `feat(web): Dashboard — Strategic Command Center`

---

### Task 4: Country Intelligence — rich table view

**Why:** The mockup shows a dense sortable table with inline rating stars, FX rates, ATLAS Risk/Alert scores, and progress bars — not a card grid.

**File:** `apps/web/src/routes/CountriesList.tsx` (M)

- [ ] **Step 1.** Replace the card grid with a table layout. Table columns (matching mockup):
  | # | Country | Region | Ratings (S&P/Moody's/Fitch) | FX Rate | ATLAS Risk | ATLAS Alert | AI Progress | Staleness |
  Each row fetches summary data from the countries list endpoint. For ratings/FX/risk, fetch bundles for each country or add a lightweight summary endpoint if needed (check if `/api/countries` already returns enough).

- [ ] **Step 2.** Table features:
  - Search bar (keep existing)
  - Filter tabs: All, SSA, MENA, High Risk, Watch List
  - Sortable columns (click header to sort)
  - Row click navigates to `/countries/:iso3`
  - Rating display: colored dots or stars per agency (green/yellow/red based on grade)
  - Risk score: colored badge (green < 30, yellow 30-60, red > 60)

- [ ] **Step 3.** If the current `/api/countries` endpoint doesn't return enough data for the table (ratings, FX, risk scores), either:
  (a) Fetch each country's bundle in parallel (acceptable for 10 countries), or
  (b) Note this as a backend follow-up for a summary endpoint

- [ ] **Step 4.** Add a "Country Comparison" sub-nav link or button that navigates to `/countries/compare`.

**Commit:** `feat(web): Country Intelligence rich table view`

---

### Task 5: Country Comparison page

**Why:** The mockup shows a side-by-side comparison of 2-3 countries with all indicators lined up.

**File:** `apps/web/src/routes/CountryComparison.tsx` (C)

- [ ] **Step 1.** Country selector at top — dropdown or searchable multi-select to pick 2-3 countries. Default to no selection with prompt "Select countries to compare."

- [ ] **Step 2.** Comparison table — one column per country, rows for each indicator:
  - ATLAS Risk Score (with badge)
  - ATLAS Alert Score
  - GDP Growth (%)
  - Inflation
  - Debt/GDP
  - Current Account
  - FX Rate + regime
  - S&P / Moody's / Fitch ratings
  - Fiscal Balance
  - FX Reserves
  - Parallel Premium
  Fetch each country's bundle via `/api/countries/:iso3/bundle`.

- [ ] **Step 3.** "Risk Dimensions Comparison" section below the table — side-by-side risk gauges for each dimension (Macro, Fiscal, External, Political, Institutional).

- [ ] **Step 4.** Add route `/countries/compare` in `App.tsx`.

**Commit:** `feat(web): Country Comparison page`

---

### Task 6: News & Event Intelligence page

**Why:** The mockup has a dedicated news page with richer presentation than the inline news on country profiles.

**File:** `apps/web/src/routes/NewsIntelligence.tsx` (C)

- [ ] **Step 1.** Two tabs at top: "Intelligence Feed" (active by default) | "Event Calendar" (placeholder/coming soon).

- [ ] **Step 2.** Intelligence Feed:
  - Search bar + country filter dropdown + event type filter
  - Each article card shows:
    - Headline (bold, clickable to source)
    - Impact scores: 4 colored badges (Fiscal/External/FX/Political — H/M/L)
    - Source + timestamp
    - Body preview (2-3 lines, expandable)
    - "Show scoring rationale" toggle that reveals the AI scoring explanation
  - Fetch from `/api/news` with optional `iso3` query param

- [ ] **Step 3.** Summary KPIs at top of feed:
  - Total articles (count)
  - High impact (count where any axis is H)
  - Countries covered (distinct iso3 count)

- [ ] **Step 4.** Add route `/news` in `App.tsx`.

**Commit:** `feat(web): News & Event Intelligence page`

---

### Task 7: Design system components — dark theme update

**Why:** All existing design system components use light-theme colors (white backgrounds, light borders). They need to work on dark backgrounds.

**Files:** All primitives in `packages/design-system/src/primitives/`

- [ ] **Step 1.** Update `KpiCard` — change `bg-white` to `bg-ink-700`, `text-ink-900` to `text-ink-100`, `border-ink-100` to `border-ink-600`.
- [ ] **Step 2.** Update `RatingBadge` — ensure badge colors contrast on dark.
- [ ] **Step 3.** Update `RiskBadge` — ensure green/yellow/red contrast on dark.
- [ ] **Step 4.** Update `RiskGauge` — dark background, lighter text.
- [ ] **Step 5.** Update `StalenessChip` — dark-safe colors.
- [ ] **Step 6.** Update `InstitutionalTable` — dark table rows, borders.
- [ ] **Step 7.** Create `AlertBadge` component for Dashboard alerts:
  ```tsx
  // severity: "critical" | "warning" | "info"
  // Shows colored dot + label
  ```
- [ ] **Step 8.** Update design system tests to pass with new class names.

**Commit:** `feat(design): dark theme for all primitives + AlertBadge`

---

### Task 8: Existing pages — dark theme pass

**Why:** All existing pages need their hardcoded light colors swapped to dark equivalents.

**Files:** All route components + web components

- [ ] **Step 1.** `Login.tsx` — dark card on dark background.
- [ ] **Step 2.** `CountryProfile.tsx` — all card backgrounds `bg-ink-700`, text colors inverted.
- [ ] **Step 3.** `ScenarioEngine.tsx` — dark sidebar, dark slider cards, dark impact cards.
- [ ] **Step 4.** `ScenarioView.tsx` — dark theme.
- [ ] **Step 5.** `AdminSynopses.tsx` — dark cards, dark badges.
- [ ] **Step 6.** `SynopsisCard.tsx` — dark card.
- [ ] **Step 7.** `NewsItemCard.tsx` — dark card.
- [ ] **Step 8.** `Skeleton.tsx` — dark skeleton pulse color (`bg-ink-600` instead of `bg-ink-100`).
- [ ] **Step 9.** `ErrorBoundary.tsx` — dark error card.
- [ ] **Step 10.** Update all existing tests that assert on class names.

**Commit:** `feat(web): dark theme pass on all existing pages`

---

### Task 9: Test updates & integration verification

- [ ] **Step 1.** Run full frontend test suite, fix any broken tests from class name changes.
- [ ] **Step 2.** Run design system tests, fix any failures.
- [ ] **Step 3.** Run ruff + mypy on backend (should be unaffected).
- [ ] **Step 4.** Start dev server, walk through every page:
  - Login → Dashboard → Country Intelligence table → Country Profile → Country Comparison → Scenario Engine → News Intelligence → Admin Synopses
- [ ] **Step 5.** Verify sidebar navigation works, collapse/expand, active states.
- [ ] **Step 6.** Check responsive behavior at common breakpoints.

**Commit:** any fixes from verification

---

## Execution Notes

- **Task ordering:** Task 1 (dark theme colors) MUST come first — everything depends on it. Task 2 (sidebar) should come second as it restructures the layout. Task 7 (design system dark) can run in parallel with Task 2. Tasks 3-6 (new/reworked pages) can run after Tasks 1+2+7 are done. Task 8 (existing pages dark pass) can run in parallel with 3-6. Task 9 is last.
- **Dependency chain:** 1 → 2 + 7 (parallel) → 3 + 4 + 5 + 6 + 8 (parallel) → 9
- **No backend changes:** All new pages use existing API endpoints. The Dashboard aggregates client-side.
- **10 prototype countries:** Table and comparison views only need to handle 10 rows — no pagination needed.
- **Deferred nav items:** Deal Analysis, Live Monitoring, Reports appear in sidebar as disabled/greyed with "Soon" badge.
