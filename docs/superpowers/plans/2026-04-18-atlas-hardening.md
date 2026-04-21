# Atlas Plan 6: Hardening — Error Handling, Resilience & Demo Readiness

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the prototype demo-safe and production-adjacent. Every API error surfaces a clear message in the UI instead of a silent failure or console crash. External calls have timeouts. Configuration validates on startup. The app degrades gracefully when backends are slow or unavailable. Security defaults are tightened for non-dev environments. Frontend gains an error boundary, toast notifications, and loading skeletons.

**Architecture:** This plan touches every layer but adds no new features — it hardens existing ones. Backend: startup config validation, connection pool tuning, CORS tightening, secure cookie env-awareness, Claude API timeout, ISO3 input validation. Frontend: React error boundary, toast notification system, mutation error feedback in AdminSynopses, loading skeletons for list views, scenario library error handling. Tests: cover the new error paths.

**Tech Stack:** Existing stack only — no new deps except `react-hot-toast` (lightweight, zero-config toast library, ~5KB gzipped).

---

## File Structure

Files created (C) or modified (M):

```
atlas/
├── apps/api/src/atlas_api/
│   ├── config.py                              (M) startup validation, env-aware secure cookie
│   ├── main.py                                (M) CORS tightening, startup validation call
│   ├── db.py                                  (M) pool_size + max_overflow
│   ├── routers/
│   │   ├── auth.py                            (M) env-aware secure cookie flag
│   │   ├── news.py                            (M) ISO3 validation
│   │   ├── scenarios.py                       (M) ISO3 validation
│   │   └── synopses.py                        (M) ISO3 validation
│   └── services/ai/
│       └── provider.py                        (M) request timeout on Claude calls
│
├── apps/api/tests/
│   ├── test_config_validation.py              (C) startup validation tests
│   ├── test_iso3_validation.py                (C) ISO3 format rejection tests
│   └── test_auth.py                           (M) secure cookie env-awareness test
│
├── apps/web/
│   ├── package.json                           (M) add react-hot-toast
│   └── src/
│       ├── App.tsx                             (M) wrap with ErrorBoundary + Toaster
│       ├── components/
│       │   ├── ErrorBoundary.tsx               (C) catch render crashes
│       │   ├── Toast.tsx                       (C) re-export configured Toaster + toast helpers
│       │   ├── Skeleton.tsx                    (C) reusable skeleton loading primitives
│       │   └── SynopsisCard.tsx                (M) loading skeleton variant
│       └── routes/
│           ├── AdminSynopses.tsx               (M) mutation error toasts, error state, loading skeleton
│           ├── CountriesList.tsx               (M) loading skeleton
│           ├── CountryProfile.tsx              (M) loading skeleton
│           └── ScenarioEngine.tsx              (M) sidebar error handling, toast on save fail
│
└── apps/web/tests/
    ├── ErrorBoundary.test.tsx                  (C) error boundary tests
    └── AdminSynopses.test.tsx                  (C) mutation error feedback tests
```

---

## Tasks

### Task 1: Backend — Startup config validation

**Why:** If `ANTHROPIC_API_KEY` is empty while AI features are relied upon, or `JWT_SECRET` is still the default in a non-dev environment, the app should fail fast at startup instead of silently misbehaving.

**File:** `apps/api/src/atlas_api/config.py`

- [ ] **Step 1.** Add a `validate_for_production` method to `Settings`:
  ```python
  def validate_for_production(self) -> list[str]:
      """Return warnings for dangerous defaults. Called at startup."""
      warnings: list[str] = []
      if self.jwt_secret == "dev-secret-change-me":
          warnings.append("JWT_SECRET is still the default — set a real secret")
      if self.anthropic_api_key == "" and self.news_poll_enabled:
          warnings.append("ANTHROPIC_API_KEY is empty but news polling is enabled — AI scoring will fall back to heuristic")
      if self.demo_user_password == "change-me":
          warnings.append("DEMO_USER_PASSWORD is still the default")
      return warnings
  ```
- [ ] **Step 2.** Add an `is_production` property:
  ```python
  environment: str = "development"

  @property
  def is_production(self) -> bool:
      return self.environment == "production"
  ```
- [ ] **Step 3.** In `main.py`, add a startup validation call inside the lifespan, after scheduler setup:
  ```python
  import logging
  logger = logging.getLogger("atlas")

  # Inside lifespan, before yield:
  for warning in settings.validate_for_production():
      if settings.is_production:
          raise RuntimeError(f"Production config error: {warning}")
      logger.warning("CONFIG: %s", warning)
  ```

**Tests file:** `apps/api/tests/test_config_validation.py`

- [ ] **Step 4.** Test that default dev config returns expected warnings (jwt_secret, demo_user_password).
- [ ] **Step 5.** Test that production environment with default jwt_secret raises RuntimeError.
- [ ] **Step 6.** Test that properly configured production settings returns no warnings.

**Commit:** `feat(api): startup config validation with fail-fast in production`

---

### Task 2: Backend — Connection pool tuning

**Why:** Default SQLAlchemy pool has `pool_size=5, max_overflow=10`. For a prototype this is fine, but making it explicit prevents surprises and documents the choice.

**File:** `apps/api/src/atlas_api/db.py`

- [ ] **Step 1.** Add explicit pool parameters to `create_engine`:
  ```python
  engine = create_engine(
      settings.database_url,
      pool_pre_ping=True,
      pool_size=5,
      max_overflow=10,
      pool_recycle=1800,  # recycle connections after 30 min
      future=True,
  )
  ```

**No new tests** — this is config, not logic. Existing tests exercise the engine.

**Commit:** `chore(api): explicit connection pool parameters`

---

### Task 3: Backend — CORS tightening & env-aware secure cookie

**Why:** `allow_methods=["*"]` and `allow_headers=["*"]` is overly permissive. The secure cookie flag should be `True` in production.

**Files:** `apps/api/src/atlas_api/main.py`, `apps/api/src/atlas_api/routers/auth.py`

- [ ] **Step 1.** In `main.py`, replace wildcard CORS methods/headers:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
      allow_credentials=True,
      allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
      allow_headers=["Content-Type", "Authorization"],
  )
  ```
- [ ] **Step 2.** In `auth.py`, make the secure cookie flag env-aware:
  ```python
  response.set_cookie(
      key=COOKIE_NAME,
      value=token,
      httponly=True,
      samesite="lax",
      secure=settings.is_production,
      max_age=settings.jwt_expires_minutes * 60,
      path="/",
  )
  ```
- [ ] **Step 3.** Same for `delete_cookie` in logout:
  ```python
  response.delete_cookie(
      key=COOKIE_NAME,
      path="/",
      samesite="lax",
      secure=settings.is_production,
  )
  ```

**Tests file:** `apps/api/tests/test_auth.py`

- [ ] **Step 4.** Add a test that verifies `Set-Cookie` has `Secure` flag when `environment=production` (monkeypatch settings).

**Commit:** `fix(api): tighten CORS methods/headers, env-aware secure cookie`

---

### Task 4: Backend — ISO3 input validation

**Why:** Several endpoints accept an `iso3` path/query parameter but only uppercase it without checking format. A regex guard rejects nonsense early with a clear 400.

**Files:** `apps/api/src/atlas_api/routers/news.py`, `apps/api/src/atlas_api/routers/scenarios.py`, `apps/api/src/atlas_api/routers/synopses.py`

- [ ] **Step 1.** Create a shared ISO3 validation dependency in `apps/api/src/atlas_api/deps.py`:
  ```python
  import re
  from typing import Annotated
  from fastapi import Path, Query, HTTPException, status

  _ISO3_RE = re.compile(r"^[A-Za-z]{3}$")

  def validate_iso3_path(iso3: Annotated[str, Path()]) -> str:
      if not _ISO3_RE.match(iso3):
          raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ISO3 code: {iso3}")
      return iso3.upper()

  def validate_iso3_query(iso3: Annotated[str, Query()]) -> str:
      if not _ISO3_RE.match(iso3):
          raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid ISO3 code: {iso3}")
      return iso3.upper()

  ValidIso3Path = Annotated[str, Depends(validate_iso3_path)]
  ValidIso3Query = Annotated[str, Depends(validate_iso3_query)]
  ```
- [ ] **Step 2.** Replace raw `iso3` params in `news.py`, `scenarios.py`, and `synopses.py` with `ValidIso3Path` / `ValidIso3Query` as appropriate. Remove any inline `.upper()` calls on those params.
- [ ] **Step 3.** In `scenarios.py` preview-all, the body's `iso3` field (if present) should also be validated — add a `@field_validator` on the Pydantic schema or validate in the endpoint.

**Tests file:** `apps/api/tests/test_iso3_validation.py`

- [ ] **Step 4.** Test that `GET /api/news?iso3=INVALID` returns 400.
- [ ] **Step 5.** Test that `GET /api/news?iso3=123` returns 400.
- [ ] **Step 6.** Test that `GET /api/news?iso3=nga` returns 200 (lowercase accepted, uppercased internally).

**Commit:** `fix(api): strict ISO3 validation on all endpoints`

---

### Task 5: Backend — Claude API timeout

**Why:** If Claude's API hangs, the synopsis/scoring endpoint blocks indefinitely. A 60s timeout prevents cascade stalls.

**File:** `apps/api/src/atlas_api/services/ai/provider.py`

- [ ] **Step 1.** Add a `timeout` parameter to the `anthropic.Anthropic` client instantiation (or to each `messages.create` call). The `anthropic` SDK supports `timeout=httpx.Timeout(60.0)`:
  ```python
  import httpx
  self._client = anthropic.Anthropic(
      api_key=settings.anthropic_api_key,
      timeout=httpx.Timeout(60.0, connect=10.0),
  )
  ```
- [ ] **Step 2.** Catch `httpx.TimeoutException` in the `call_tool` method and raise a clear error or return a fallback indicator so the pipeline can degrade to heuristic scoring.

**Tests file:** `apps/api/tests/test_ai_provider.py`

- [ ] **Step 3.** Add a test that mocks a timeout and verifies the provider raises or returns the expected fallback.

**Commit:** `fix(api): 60s timeout on Claude API calls with graceful fallback`

---

### Task 6: Frontend — Error boundary

**Why:** Any uncaught render error currently crashes the entire app with a white screen. An error boundary catches it and shows a recovery UI.

**File:** `apps/web/src/components/ErrorBoundary.tsx` (C)

- [ ] **Step 1.** Create a class component `ErrorBoundary` that:
  - Catches render errors via `componentDidCatch`
  - Shows a centered card with "Something went wrong", the error message, and a "Reload" button that calls `window.location.reload()`
  - Uses Tailwind classes consistent with the design system (ink-*, atlas-* palette)

**File:** `apps/web/src/App.tsx` (M)

- [ ] **Step 2.** Wrap the `RouterProvider` (or top-level `<Routes>`) with `<ErrorBoundary>`.

**Tests file:** `apps/web/tests/ErrorBoundary.test.tsx` (C)

- [ ] **Step 3.** Test that a child component throwing an error renders the fallback UI instead of crashing.

**Commit:** `feat(web): React error boundary with recovery UI`

---

### Task 7: Frontend — Toast notification system

**Why:** Mutations in AdminSynopses fail silently. The ScenarioEngine shows inline errors but they're easy to miss. A toast system provides consistent, dismissible feedback across the app.

**File:** `apps/web/package.json` (M)

- [ ] **Step 1.** `pnpm add react-hot-toast --filter atlas-web`

**File:** `apps/web/src/components/Toast.tsx` (C)

- [ ] **Step 2.** Create a thin wrapper that re-exports `toast` and a configured `<Toaster>`:
  ```tsx
  import { Toaster } from "react-hot-toast";
  export { toast } from "react-hot-toast";

  export function AppToaster() {
    return (
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: { fontSize: "0.875rem" },
          success: { iconTheme: { primary: "#16a34a", secondary: "#fff" } },
          error: { iconTheme: { primary: "#dc2626", secondary: "#fff" } },
        }}
      />
    );
  }
  ```

**File:** `apps/web/src/App.tsx` (M)

- [ ] **Step 3.** Add `<AppToaster />` inside the app root (inside ErrorBoundary, outside router).

**Commit:** `feat(web): toast notification system with react-hot-toast`

---

### Task 8: Frontend — AdminSynopses error feedback

**Why:** Approve/reject mutations fail silently — no error displayed, no success confirmation.

**File:** `apps/web/src/routes/AdminSynopses.tsx` (M)

- [ ] **Step 1.** Import `toast` from `../components/Toast`.
- [ ] **Step 2.** Add `onError` callbacks to both mutations:
  ```tsx
  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      api(`/api/admin/synopses/${id}/approve`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-synopses"] });
      toast.success("Synopsis approved");
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Approve failed"),
  });
  ```
  Same pattern for `rejectMutation` with "Synopsis rejected" / "Reject failed".
- [ ] **Step 3.** Add `isError` and `error` handling from the `useQuery` call — show an error banner if the synopsis list fails to load.
- [ ] **Step 4.** Show a loading skeleton (from Task 10) instead of plain "Loading..." text.

**Tests file:** `apps/web/tests/AdminSynopses.test.tsx` (C)

- [ ] **Step 5.** Test that a failed mutation shows the error toast (mock `api` to reject, assert toast text appears).
- [ ] **Step 6.** Test that successful approve shows success toast.

**Commit:** `fix(web): AdminSynopses mutation error toasts + query error state`

---

### Task 9: Frontend — ScenarioEngine error handling

**Why:** Sidebar scenario fetch fails silently (`.catch(() => {})`). Save failures show inline text that's easy to miss.

**File:** `apps/web/src/routes/ScenarioEngine.tsx` (M)

- [ ] **Step 1.** Import `toast` from `../components/Toast`.
- [ ] **Step 2.** Replace the sidebar fetch silent catch with a toast:
  ```tsx
  useEffect(() => {
    api<SavedScenario[]>("/api/scenarios")
      .then(setSavedScenarios)
      .catch((err) => toast.error(err instanceof Error ? err.message : "Failed to load scenarios"));
  }, []);
  ```
- [ ] **Step 3.** In `handleSave` catch block, replace `setError(...)` with `toast.error(...)` (or keep both — inline + toast).
- [ ] **Step 4.** Add a toast on successful save: `toast.success("Scenario saved")`.

**Commit:** `fix(web): ScenarioEngine toast feedback for load/save errors`

---

### Task 10: Frontend — Loading skeletons

**Why:** "Loading..." plain text looks unfinished. Skeleton placeholders give visual structure while data loads.

**File:** `apps/web/src/components/Skeleton.tsx` (C)

- [ ] **Step 1.** Create reusable skeleton primitives:
  ```tsx
  export function SkeletonLine({ className = "" }: { className?: string }) {
    return <div className={`animate-pulse rounded bg-ink-100 ${className}`} />;
  }

  export function SkeletonCard() {
    return (
      <div className="rounded-md border border-ink-100 bg-white p-4 space-y-3">
        <SkeletonLine className="h-4 w-1/3" />
        <SkeletonLine className="h-3 w-full" />
        <SkeletonLine className="h-3 w-2/3" />
      </div>
    );
  }
  ```

**Files:** `apps/web/src/routes/CountriesList.tsx`, `CountryProfile.tsx`, `AdminSynopses.tsx` (M)

- [ ] **Step 2.** In `CountriesList.tsx`, replace "Loading..." with 10 `<SkeletonCard />` elements.
- [ ] **Step 3.** In `CountryProfile.tsx`, replace "Loading..." with a profile-shaped skeleton (header line + 3 card skeletons).
- [ ] **Step 4.** In `AdminSynopses.tsx`, replace "Loading..." with 3 `<SkeletonCard />` elements.

**Commit:** `feat(web): loading skeleton components for list and profile views`

---

### Task 11: Integration verification

**Why:** Confirm everything works together — all tests pass, app starts, demo flow works.

- [ ] **Step 1.** Run full backend test suite: `cd /Users/bird/Documents/ATLAS/atlas && .venv/bin/python -m pytest apps/api/tests/ -x -q`
- [ ] **Step 2.** Run full frontend test suite: `pnpm --filter atlas-web test && pnpm --filter @atlas/design-system test`
- [ ] **Step 3.** Run ruff + mypy: `.venv/bin/ruff check apps/api/src/ && .venv/bin/mypy apps/api/src/`
- [ ] **Step 4.** Start the dev server and verify:
  - Login page loads, login works
  - Countries list shows loading skeletons → then data
  - Country profile shows loading skeleton → then bundle
  - Scenario engine sidebar loads scenarios (or toasts error if API down)
  - Admin synopses page shows error toast on failed mutation
  - Breaking a component intentionally triggers error boundary (dev-only check)
- [ ] **Step 5.** If any failures, fix and re-run.

**Commit:** any fixes from integration testing

---

## Execution Notes

- **Task ordering:** Tasks 1-5 (backend) are independent of each other. Tasks 6-7 (error boundary + toast) must come before Tasks 8-9 (which use toasts). Task 10 (skeletons) is independent. Task 11 is last.
- **Parallel groups:** Tasks 1-5 can run in parallel. Tasks 6+7 can run in parallel. Tasks 8+9 can run in parallel after 7. Task 10 is independent. Task 11 is sequential last.
- **No new features:** This plan adds zero new endpoints, pages, or data flows. It only hardens existing ones.
- **Test count target:** ~10-15 new tests across backend + frontend, bringing total from 219 to ~230+.
