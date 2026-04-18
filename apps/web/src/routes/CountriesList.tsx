import { useMemo, useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "./AppShell";

/* ── types ──────────────────────────────────────────────────────── */

interface Country {
  iso3: string;
  name: string;
  region: string;
  status: string;
  fx_regime: string;
  tier: string;
}

interface FxObservation {
  iso3: string;
  ccy: string;
  usd_per_ccy: number;
  observation_date: string;
  source: string;
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
  agency: string;
  rating: string;
  outlook: string | null;
  action: string;
  action_date: string;
  source_url: string | null;
}

interface RatingsSection {
  latest_per_agency: Record<string, RatingAction>;
  composite_score: number | null;
  history: RatingAction[];
}

interface RiskScore {
  composite: number;
  dimensions: { name: string; score: number; weight: number }[];
}

interface CountryBundle {
  country: Country;
  macro: unknown[];
  fx: FxDeltas | null;
  ratings: RatingsSection;
  risk: RiskScore;
  synopsis: string | null;
  news_placeholder: boolean;
}

/* ── constants ──────────────────────────────────────────────────── */

const REGIONS = ["All", "West Africa", "East Africa", "Southern Africa", "North Africa"] as const;

type SortKey = "name" | "region" | "risk" | "fx";
type SortDir = "asc" | "desc";

/* ── helpers ────────────────────────────────────────────────────── */

function riskColor(score: number): string {
  if (score < 25) return "#22c55e";
  if (score < 45) return "#84cc16";
  if (score < 60) return "#f59e0b";
  if (score < 75) return "#f97316";
  return "#ef4444";
}

function riskLabel(score: number): string {
  if (score < 25) return "Low";
  if (score < 45) return "Moderate";
  if (score < 60) return "Elevated";
  if (score < 75) return "High";
  return "Critical";
}

function formatFx(fx: FxDeltas | null): string {
  if (!fx) return "\u2014";
  const rate = fx.latest.usd_per_ccy;
  return rate < 0.01 ? rate.toFixed(6) : rate < 1 ? rate.toFixed(4) : rate.toFixed(2);
}

function formatFxDelta(fx: FxDeltas | null): { text: string; color: string } | null {
  if (!fx || fx.delta_30d_pct == null) return null;
  const d = fx.delta_30d_pct;
  const sign = d >= 0 ? "+" : "";
  return {
    text: `${sign}${d.toFixed(1)}%`,
    color: d > 0 ? "#22c55e" : d < 0 ? "#ef4444" : "#9ca3af",
  };
}

function ratingsDisplay(ratings: RatingsSection): string {
  const agencies = Object.entries(ratings.latest_per_agency);
  if (agencies.length === 0) return "\u2014";
  return agencies
    .map(([agency, r]) => `${agency.charAt(0).toUpperCase()}:${r.rating}`)
    .join(" ");
}

/* ── skeleton row ───────────────────────────────────────────────── */

function SkeletonRow() {
  return (
    <tr className="border-b border-white/[0.03]">
      {Array.from({ length: 7 }, (_, i) => (
        <td key={i} className="px-3 py-3">
          <div className="h-3.5 animate-pulse rounded bg-white/[0.06]" style={{ width: `${40 + Math.random() * 40}%` }} />
        </td>
      ))}
    </tr>
  );
}

/* ── sort icon ──────────────────────────────────────────────────── */

function SortIndicator({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="ml-1 text-[10px] opacity-30">\u2195</span>;
  return <span className="ml-1 text-[10px] text-blue-400">{dir === "asc" ? "\u2191" : "\u2193"}</span>;
}

/* ── main component ─────────────────────────────────────────────── */

export default function CountriesList() {
  const navigate = useNavigate();

  /* search / filter state */
  const [q, setQ] = useState("");
  const [region, setRegion] = useState<string>("All");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  /* fetch country list */
  const { data: countries, isLoading, error } = useQuery<Country[]>({
    queryKey: ["countries"],
    queryFn: () => api<Country[]>("/api/countries"),
    staleTime: 5 * 60 * 1000,
  });

  /* fetch each bundle in parallel */
  const bundleQueries = useQueries({
    queries: (countries ?? []).map((c) => ({
      queryKey: ["bundle", c.iso3],
      queryFn: () => api<CountryBundle>(`/api/countries/${c.iso3}/bundle`),
      enabled: !!countries,
      staleTime: 5 * 60 * 1000,
    })),
  });

  const bundleMap = useMemo(() => {
    const map = new Map<string, CountryBundle>();
    bundleQueries.forEach((bq) => {
      if (bq.data) map.set(bq.data.country.iso3, bq.data);
    });
    return map;
  }, [bundleQueries]);

  const bundlesLoading = bundleQueries.some((bq) => bq.isLoading);

  /* filter + sort */
  const rows = useMemo(() => {
    if (!countries) return [];
    let list = countries.filter((c) => {
      if (region !== "All" && c.region !== region) return false;
      if (!q) return true;
      const needle = q.trim().toLowerCase();
      return c.iso3.toLowerCase().includes(needle) || c.name.toLowerCase().includes(needle);
    });

    list = [...list].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "name":
          cmp = a.name.localeCompare(b.name);
          break;
        case "region":
          cmp = a.region.localeCompare(b.region);
          break;
        case "risk": {
          const ra = bundleMap.get(a.iso3)?.risk.composite ?? 999;
          const rb = bundleMap.get(b.iso3)?.risk.composite ?? 999;
          cmp = ra - rb;
          break;
        }
        case "fx": {
          const fa = bundleMap.get(a.iso3)?.fx?.latest.usd_per_ccy ?? 0;
          const fb = bundleMap.get(b.iso3)?.fx?.latest.usd_per_ccy ?? 0;
          cmp = fa - fb;
          break;
        }
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return list;
  }, [countries, q, region, sortKey, sortDir, bundleMap]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  /* ── render ─────────────────────────────────────────────────── */

  return (
    <AppShell>
      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* header */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-[#f3f4f6]">Country Intelligence</h1>
          <button
            onClick={() => navigate("/countries/compare")}
            className="rounded-md border border-[#374151] px-4 py-2 text-sm font-medium text-[#d1d5db] transition hover:border-[#4b5563] hover:text-[#e5e7eb]"
          >
            Compare Countries
          </button>
        </div>

        {/* search + region tabs */}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <input
            type="search"
            placeholder="Search by name or ISO3\u2026"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-60 rounded-md border border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-sm text-[#d1d5db] placeholder-[#6b7280] backdrop-blur-xl outline-none focus:border-[#3b82f6] focus:ring-1 focus:ring-[#3b82f6]"
          />
          <div className="flex items-center gap-1">
            {REGIONS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRegion(r)}
                className={`rounded px-2.5 py-1 text-xs font-medium transition ${
                  region === r
                    ? "bg-[#3b82f6]/15 text-[#60a5fa]"
                    : "text-[#9ca3af] hover:bg-white/[0.04] hover:text-[#d1d5db]"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {/* error */}
        {error && <div className="mt-8 text-[#ef4444]">Failed to load countries.</div>}

        {/* table */}
        <div className="mt-6 overflow-x-auto rounded-[10px] border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl"
          style={{ boxShadow: "0 4px 30px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.04)" }}>
          <table className="w-full text-left">
            <thead>
              <tr className="bg-white/[0.04] text-xs font-medium uppercase tracking-wide text-[#9ca3af]">
                <th className="px-3 py-2.5 font-medium w-10">#</th>
                <th
                  className="px-3 py-2.5 font-medium cursor-pointer select-none"
                  onClick={() => toggleSort("name")}
                >
                  Country
                  <SortIndicator active={sortKey === "name"} dir={sortDir} />
                </th>
                <th
                  className="px-3 py-2.5 font-medium cursor-pointer select-none"
                  onClick={() => toggleSort("region")}
                >
                  Region
                  <SortIndicator active={sortKey === "region"} dir={sortDir} />
                </th>
                <th className="px-3 py-2.5 font-medium">Ratings</th>
                <th
                  className="px-3 py-2.5 font-medium cursor-pointer select-none"
                  onClick={() => toggleSort("fx")}
                >
                  FX Rate
                  <SortIndicator active={sortKey === "fx"} dir={sortDir} />
                </th>
                <th
                  className="px-3 py-2.5 font-medium cursor-pointer select-none"
                  onClick={() => toggleSort("risk")}
                >
                  ATLAS Risk
                  <SortIndicator active={sortKey === "risk"} dir={sortDir} />
                </th>
                <th className="px-3 py-2.5 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 8 }, (_, i) => <SkeletonRow key={i} />)
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-sm text-[#6b7280]">
                    No countries match your search.
                  </td>
                </tr>
              ) : (
                rows.map((c, idx) => {
                  const bundle = bundleMap.get(c.iso3);
                  const risk = bundle?.risk;
                  const fx = bundle?.fx ?? null;
                  const fxDelta = formatFxDelta(fx);
                  const ratings = bundle?.ratings;

                  return (
                    <tr
                      key={c.iso3}
                      onClick={() => navigate(`/countries/${c.iso3}`)}
                      className="cursor-pointer border-b border-white/[0.03] transition-colors hover:bg-white/[0.03]"
                    >
                      {/* # */}
                      <td className="px-3 py-2.5 text-xs tabular-nums text-[#6b7280]">
                        {idx + 1}
                      </td>

                      {/* Country */}
                      <td className="px-3 py-2.5">
                        <div className="text-sm font-medium text-[#f3f4f6]">{c.name}</div>
                        <div className="text-xs text-[#6b7280]">{c.iso3}</div>
                      </td>

                      {/* Region */}
                      <td className="px-3 py-2.5 text-sm text-[#d1d5db]">{c.region}</td>

                      {/* Ratings */}
                      <td className="px-3 py-2.5 text-xs font-mono tabular-nums text-[#d1d5db]">
                        {bundlesLoading && !bundle ? (
                          <div className="h-3.5 w-20 animate-pulse rounded bg-white/[0.06]" />
                        ) : ratings ? (
                          ratingsDisplay(ratings)
                        ) : (
                          "\u2014"
                        )}
                      </td>

                      {/* FX Rate */}
                      <td className="px-3 py-2.5">
                        {bundlesLoading && !bundle ? (
                          <div className="h-3.5 w-16 animate-pulse rounded bg-white/[0.06]" />
                        ) : (
                          <div className="flex items-baseline gap-1.5">
                            <span className="text-sm font-mono tabular-nums text-[#d1d5db]">
                              {formatFx(fx)}
                            </span>
                            {fxDelta && (
                              <span className="text-[10px] font-mono tabular-nums" style={{ color: fxDelta.color }}>
                                {fxDelta.text}
                              </span>
                            )}
                          </div>
                        )}
                      </td>

                      {/* ATLAS Risk */}
                      <td className="px-3 py-2.5">
                        {bundlesLoading && !bundle ? (
                          <div className="h-3.5 w-14 animate-pulse rounded bg-white/[0.06]" />
                        ) : risk ? (
                          <div className="flex items-center gap-2">
                            <span
                              className="inline-block rounded px-2 py-0.5 text-xs font-medium"
                              style={{
                                backgroundColor: `${riskColor(risk.composite)}26`,
                                color: riskColor(risk.composite),
                              }}
                            >
                              {risk.composite.toFixed(0)}
                            </span>
                            <span className="text-[10px] uppercase tracking-wide text-[#6b7280]">
                              {riskLabel(risk.composite)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-sm text-[#6b7280]">{"\u2014"}</span>
                        )}
                      </td>

                      {/* Status */}
                      <td className="px-3 py-2.5">
                        <span className="rounded bg-[#374151] px-2 py-0.5 text-xs font-medium text-[#9ca3af]">
                          {c.status}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </main>
    </AppShell>
  );
}
