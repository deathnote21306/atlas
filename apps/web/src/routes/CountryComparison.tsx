import { useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { RiskGauge } from "@atlas/design-system";
import { api } from "../api/client";
import AppShell from "./AppShell";
import { SkeletonLine } from "../components/Skeleton";

interface Country {
  iso3: string;
  name: string;
  region: string;
  status: string;
  fx_regime: string;
  tier: string;
}

interface MacroTile {
  indicator: string;
  label: string;
  value: number | null;
  period: string | null;
  source: string | null;
  staleness: { state: string; age_days: number | null };
}

interface FxObservation {
  iso3: string;
  ccy: string;
  usd_per_ccy: number;
  observation_date: string;
  source: string;
  ingested_at: string;
}

interface FxDeltas {
  latest: FxObservation;
  delta_1d_pct: number | null;
  delta_7d_pct: number | null;
  delta_30d_pct: number | null;
  delta_ytd_pct: number | null;
}

interface RatingAction {
  iso3: string;
  agency: "S&P" | "Moodys" | "Fitch";
  rating: string;
  outlook: string | null;
  action: string;
  action_date: string;
  source_url: string | null;
}

interface DimensionScore {
  dimension: string;
  score: number;
  rationale: string;
  input_value: number | null;
  is_estimate: boolean;
}

interface CountryBundle {
  country: {
    iso3: string; name: string; capital: string; region: string;
    tags: string[]; tier: string; status: string; fx_regime: string;
    fx_regime_notes: string | null; fx_parallel_premium: number | null;
    composite_risk: { score: number; label: string; trend: string; as_of: string | null } | null;
  };
  macro: MacroTile[];
  fx: FxDeltas | null;
  ratings: {
    latest_per_agency: Record<string, RatingAction>;
    composite_score: number | null;
    history: RatingAction[];
  };
  risk: { composite: number; dimensions: DimensionScore[] };
  synopsis: string | null;
  news_placeholder: boolean;
}

/* ---------- helpers ---------- */

function riskColor(score: number): string {
  if (score <= 25) return "text-positive";
  if (score <= 45) return "text-lime-400";
  if (score <= 60) return "text-warning";
  if (score <= 75) return "text-orange-400";
  return "text-danger";
}

function fmtValue(n: number | null | undefined, decimals = 2): string {
  return n == null ? "\u2014" : n.toFixed(decimals);
}

function fmtPct(n: number | null | undefined): string {
  return n == null ? "\u2014" : `${n.toFixed(1)}%`;
}

function fmtFx(bundle: CountryBundle): string {
  if (!bundle.fx) return "\u2014";
  const { ccy, usd_per_ccy } = bundle.fx.latest;
  // Show inverted rate (local per USD) for readability
  const localPerUsd = 1 / usd_per_ccy;
  return `${ccy} ${localPerUsd >= 10 ? localPerUsd.toFixed(0) : localPerUsd.toFixed(2)}/USD`;
}

function getMacroValue(macro: MacroTile[], indicator: string): number | null {
  return macro.find((m) => m.indicator === indicator)?.value ?? null;
}

function dimensionLabel(d: string): string {
  return d.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ---------- component ---------- */

const MAX_SLOTS = 3;

export default function CountryComparison() {
  const [selected, setSelected] = useState<string[]>([""]);

  const { data: countries, isLoading: countriesLoading } = useQuery<Country[]>({
    queryKey: ["countries"],
    queryFn: () => api<Country[]>("/api/countries"),
    staleTime: 5 * 60 * 1000,
  });

  // Always query for all MAX_SLOTS so hook count stays stable across renders
  const bundleQueries = useQueries({
    queries: Array.from({ length: MAX_SLOTS }, (_, i) => ({
      queryKey: ["country-bundle", selected[i] ?? ""],
      queryFn: () => api<CountryBundle>(`/api/countries/${selected[i]}/bundle`),
      staleTime: 5 * 60 * 1000,
      retry: false,
      enabled: !!selected[i],
    })),
  });

  const bundles = bundleQueries.map((q) => q.data ?? null);
  const anyLoading = bundleQueries.some((q) => q.isLoading && q.fetchStatus !== "idle");
  const activeBundles = bundles.filter((b): b is CountryBundle => b !== null);

  function updateSlot(index: number, value: string) {
    setSelected((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  }

  function addSlot() {
    if (selected.length < MAX_SLOTS) {
      setSelected((prev) => [...prev, ""]);
    }
  }

  function removeSlot(index: number) {
    if (selected.length > 1) {
      setSelected((prev) => prev.filter((_, i) => i !== index));
    }
  }

  /* ---------- indicator rows ---------- */

  const indicatorRows: { label: string; render: (b: CountryBundle) => React.ReactNode }[] = [
    {
      label: "ATLAS Risk Score",
      render: (b) => {
        const score = b.country.composite_risk?.score ?? b.risk.composite;
        return (
          <span className={`font-mono font-semibold ${riskColor(score)}`}>
            {score.toFixed(1)}
          </span>
        );
      },
    },
    {
      label: "GDP Growth",
      render: (b) => <span className="font-mono">{fmtPct(getMacroValue(b.macro, "GDP_GROWTH_PCT"))}</span>,
    },
    {
      label: "Inflation",
      render: (b) => <span className="font-mono">{fmtPct(getMacroValue(b.macro, "INFLATION_PCT"))}</span>,
    },
    {
      label: "Debt/GDP",
      render: (b) => <span className="font-mono">{fmtPct(getMacroValue(b.macro, "PUBLIC_DEBT_PCT_GDP"))}</span>,
    },
    {
      label: "FX Rate",
      render: (b) => <span className="font-mono text-xs">{fmtFx(b)}</span>,
    },
    {
      label: "FX Regime",
      render: (b) => <span className="text-xs">{b.country.fx_regime || "\u2014"}</span>,
    },
    {
      label: "S&P",
      render: (b) => {
        const r = b.ratings.latest_per_agency["S&P"];
        return <span className="font-mono">{r?.rating ?? "\u2014"}</span>;
      },
    },
    {
      label: "Moody's",
      render: (b) => {
        const r = b.ratings.latest_per_agency["Moodys"];
        return <span className="font-mono">{r?.rating ?? "\u2014"}</span>;
      },
    },
    {
      label: "Fitch",
      render: (b) => {
        const r = b.ratings.latest_per_agency["Fitch"];
        return <span className="font-mono">{r?.rating ?? "\u2014"}</span>;
      },
    },
  ];

  /* ---------- collect all risk dimensions ---------- */
  const allDimensions = Array.from(
    new Set(activeBundles.flatMap((b) => b.risk.dimensions.map((d) => d.dimension)))
  );

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-6">
        {/* Header */}
        <header className="mb-6">
          <h1 className="text-2xl font-semibold text-ink-100">Country Comparison</h1>
          <p className="mt-1 text-sm text-ink-500">
            Compare up to {MAX_SLOTS} countries side by side
          </p>
        </header>

        {/* Country selectors */}
        <div className="mb-6 flex flex-wrap items-end gap-3">
          {selected.map((iso3, i) => (
            <div key={i} className="flex items-end gap-1.5">
              <div>
                <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-500">
                  Country {i + 1}
                </label>
                <select
                  value={iso3}
                  onChange={(e) => updateSlot(i, e.target.value)}
                  className="rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-ink-100 focus:border-atlas-500 focus:outline-none focus:ring-1 focus:ring-atlas-500"
                  disabled={countriesLoading}
                >
                  <option value="" className="bg-surface-800 text-ink-300">
                    {countriesLoading ? "Loading..." : "Select country"}
                  </option>
                  {countries?.map((c) => (
                    <option key={c.iso3} value={c.iso3} className="bg-surface-800 text-ink-100">
                      {c.name} ({c.iso3})
                    </option>
                  ))}
                </select>
              </div>
              {selected.length > 1 && (
                <button
                  onClick={() => removeSlot(i)}
                  className="rounded-md px-2 py-2 text-xs text-ink-500 hover:bg-[#1c2129] hover:text-ink-300"
                  title="Remove"
                >
                  &times;
                </button>
              )}
            </div>
          ))}
          {selected.length < MAX_SLOTS && (
            <button
              onClick={addSlot}
              className="rounded-md border border-[#21262d] bg-[#161b22] px-3 py-2 text-sm text-ink-400 hover:bg-[#1c2129] hover:text-ink-200"
            >
              + Add country
            </button>
          )}
        </div>

        {/* Empty state */}
        {activeBundles.length === 0 && !anyLoading && (
          <div className="rounded-lg bg-[#161b22] p-12 text-center">
            <p className="text-ink-400">Select countries above to compare</p>
          </div>
        )}

        {/* Loading skeleton */}
        {anyLoading && activeBundles.length === 0 && (
          <div className="rounded-lg bg-[#161b22] p-4">
            <div className="space-y-3">
              {Array.from({ length: 8 }, (_, i) => (
                <div key={i} className="flex gap-4">
                  <SkeletonLine className="h-5 w-32 shrink-0" />
                  {selected.map((_, j) => (
                    <SkeletonLine key={j} className="h-5 flex-1" />
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Comparison table */}
        {activeBundles.length > 0 && (
          <section className="mb-8">
            <div
              className="overflow-x-auto rounded-lg bg-[#161b22]"
            >
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="bg-[#161b22] px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-ink-400">
                      Indicator
                    </th>
                    {activeBundles.map((b) => (
                      <th
                        key={b.country.iso3}
                        className="bg-[#161b22] px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-ink-400"
                      >
                        {b.country.name}
                        <span className="ml-1.5 font-mono text-ink-500">{b.country.iso3}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {indicatorRows.map((row) => (
                    <tr key={row.label} className="border-t border-[#21262d]">
                      <td className="px-4 py-2.5 text-xs font-medium text-ink-400">{row.label}</td>
                      {activeBundles.map((b) => (
                        <td key={b.country.iso3} className="px-4 py-2.5 text-ink-300">
                          {row.render(b)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Risk Dimensions side-by-side */}
        {activeBundles.length > 0 && allDimensions.length > 0 && (
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-500">
              Risk Dimensions
            </h2>
            <div className={`grid gap-4 ${activeBundles.length === 1 ? "grid-cols-1" : activeBundles.length === 2 ? "grid-cols-2" : "grid-cols-3"}`}>
              {activeBundles.map((b) => (
                <div key={b.country.iso3}>
                  <h3 className="mb-2 text-xs font-medium text-ink-300">{b.country.name}</h3>
                  <div className="space-y-2">
                    {b.risk.dimensions.map((d) => (
                      <RiskGauge
                        key={d.dimension}
                        label={dimensionLabel(d.dimension)}
                        score={d.score}
                        rationale={d.rationale}
                        isEstimate={d.is_estimate}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </AppShell>
  );
}
