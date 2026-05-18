import { useMemo, useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "./AppShell";

const C = "rounded-lg bg-[#161b22]";

/* ── Types ── */

interface Country { iso3: string; name: string; region: string; status: string; fx_regime: string; tier: string; }
interface FxObs { iso3: string; ccy: string; usd_per_ccy: number; observation_date: string; source: string; }
interface FxDeltas { latest: FxObs; delta_1d_pct: number | null; delta_7d_pct: number | null; delta_30d_pct: number | null; delta_ytd_pct: number | null; }
interface RatingAction { iso3: string; agency: string; rating: string; outlook: string | null; action: string; action_date: string; source_url: string | null; }
interface RatingsSection { latest_per_agency: Record<string, RatingAction>; composite_score: number | null; history: RatingAction[]; }
interface RiskScore { composite: number; dimensions: { name: string; score: number; weight: number }[]; }
interface CountryBundle {
  country: Country & { atlas_spread_bps?: number; imf_program_code?: string; imf_program_status?: string; status_tags?: string[]; capital?: string; };
  macro: unknown[]; fx: FxDeltas | null; ratings: RatingsSection; risk: RiskScore; synopsis: string | null; news_placeholder: boolean;
}

/* ── Constants ── */

const REGIONS = ["All", "SSA", "MENA", "GCC", "EM-Asia", "EM-LatAm", "EM-Europe"] as const;

const REGION_MAP: Record<string, string> = {
  "West Africa": "SSA", "East Africa": "SSA", "Southern Africa": "SSA",
  "North Africa": "MENA", "Gulf": "GCC",
};

const CAPITALS: Record<string, string> = {
  ETH: "Addis Ababa", GHA: "Accra", ZAF: "Pretoria", SEN: "Dakar",
  EGY: "Cairo", KEN: "Nairobi", MAR: "Rabat", NGA: "Abuja",
  RWA: "Kigali", CIV: "Yamoussoukro", ZMB: "Lusaka", TZA: "Dodoma",
  SAU: "Riyadh",
};

type SortKey = "name" | "risk" | "spread";
type SortDir = "asc" | "desc";

/* ── Helpers ── */

function riskBarColor(s: number) {
  if (s >= 75) return "#ef4444";
  if (s >= 60) return "#f97316";
  if (s >= 45) return "#f59e0b";
  if (s >= 25) return "#84cc16";
  return "#22c55e";
}
function riskLabel(s: number) {
  if (s >= 75) return "Critical";
  if (s >= 60) return "High";
  if (s >= 45) return "Elevated";
  if (s >= 25) return "Moderate";
  return "Low";
}
function riskLabelColor(s: number) {
  if (s >= 75) return "text-red-400";
  if (s >= 60) return "text-orange-400";
  if (s >= 45) return "text-amber-400";
  if (s >= 25) return "text-green-400";
  return "text-green-400";
}
function ratingPill(rating: string) {
  const r = rating.toUpperCase();
  if (r.startsWith("A")) return "bg-green-500/20 text-green-400 border-green-500/30";
  if (r.startsWith("BB") || r.startsWith("BA")) return "bg-amber-500/20 text-amber-400 border-amber-500/30";
  if (r.startsWith("B")) return "bg-orange-500/20 text-orange-400 border-orange-500/30";
  if (r.startsWith("C") || r.startsWith("CA") || r.startsWith("SD") || r.startsWith("NR")) return "bg-red-500/20 text-red-400 border-red-500/30";
  return "bg-[#21262d] text-ink-400 border-[#30363d]";
}
function statusDot(status: string) {
  if (status === "selective_default" || status === "default") return "bg-red-500";
  if (status === "restructured") return "bg-amber-500";
  return "bg-green-500";
}
function flagBadge(tag: string) {
  if (tag === "RESTRUCTURING") return { label: "RST", cls: "bg-red-500/15 text-red-400" };
  if (tag === "DISTRESSED") return { label: "RST", cls: "bg-red-500/15 text-red-400" };
  if (tag === "OIL" || tag === "COMMODITY") return { label: "OIL", cls: "bg-amber-500/15 text-amber-400" };
  if (tag === "REFORM") return null;
  if (tag === "GROWTH") return null;
  return null;
}
function imfBadge(code: string) {
  if (code === "ECF") return "bg-blue-500/15 text-blue-400";
  if (code === "EFF") return "bg-emerald-500/15 text-emerald-400";
  if (code === "PCI") return "bg-purple-500/15 text-purple-400";
  return "bg-[#21262d] text-ink-400";
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="ml-1 text-ink-600">↕</span>;
  return <span className="ml-1 text-blue-400">{dir === "asc" ? "↑" : "↓"}</span>;
}

/* ── Main ── */

export default function CountriesList() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [region, setRegion] = useState("All");
  const [sortKey, setSortKey] = useState<SortKey>("risk");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const { data: countries, isLoading, error } = useQuery<Country[]>({
    queryKey: ["countries"],
    queryFn: () => api<Country[]>("/api/countries"),
    staleTime: 5 * 60_000,
  });

  const bundleQueries = useQueries({
    queries: (countries ?? []).map((c) => ({
      queryKey: ["bundle", c.iso3],
      queryFn: () => api<CountryBundle>(`/api/countries/${c.iso3}/bundle`),
      enabled: !!countries,
      staleTime: 5 * 60_000,
    })),
  });

  const bundles = useMemo(() => {
    const m = new Map<string, CountryBundle>();
    bundleQueries.forEach((bq) => { if (bq.data) m.set(bq.data.country.iso3, bq.data); });
    return m;
  }, [bundleQueries]);

  const loading = bundleQueries.some((bq) => bq.isLoading);

  const rows = useMemo(() => {
    if (!countries) return [];
    let list = countries.filter((c) => {
      if (region !== "All") {
        const mapped = REGION_MAP[c.region] ?? c.region;
        if (mapped !== region) return false;
      }
      if (!q) return true;
      const n = q.trim().toLowerCase();
      return c.iso3.toLowerCase().includes(n) || c.name.toLowerCase().includes(n);
    });
    list = [...list].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "name") cmp = a.name.localeCompare(b.name);
      else if (sortKey === "risk") cmp = (bundles.get(a.iso3)?.risk.composite ?? 0) - (bundles.get(b.iso3)?.risk.composite ?? 0);
      else if (sortKey === "spread") {
        const sa = (bundles.get(a.iso3)?.country as any)?.atlas_spread?.value_bps ?? 0;
        const sb = (bundles.get(b.iso3)?.country as any)?.atlas_spread?.value_bps ?? 0;
        cmp = sa - sb;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return list;
  }, [countries, q, region, sortKey, sortDir, bundles]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("desc"); }
  }

  const totalCount = countries?.length ?? 0;

  return (
    <AppShell>
      <div className="mx-auto max-w-[1440px] px-6 pb-10">

        {/* Header */}
        <div className="pb-4 pt-4">
          <div className="text-[11px] text-ink-500">ATLAS <span className="mx-1 text-ink-600">›</span> Country Intelligence</div>
          <h1 className="mt-0.5 text-[18px] font-semibold text-ink-100">Country Intelligence</h1>
        </div>

        {/* Search + Region pills + Filters */}
        <div className="mb-4 flex items-center gap-3">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              type="search"
              placeholder="Search countries, regions, ISO codes..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-72 rounded-md border border-[#30363d] bg-[#0d1117] py-2 pl-9 pr-3 text-sm text-ink-200 placeholder:text-ink-500 focus:border-blue-500/40 focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-0.5">
            <span className="mr-1 text-[11px] text-ink-500">Region:</span>
            {REGIONS.map((r) => (
              <button
                key={r}
                onClick={() => setRegion(r)}
                className={`rounded-md px-2.5 py-1.5 text-[11px] font-medium transition ${
                  region === r
                    ? "bg-blue-500/20 text-blue-400"
                    : "text-ink-500 hover:bg-[#161b22] hover:text-ink-300"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
          <div className="ml-auto text-[12px] text-ink-500">{totalCount} countries</div>
        </div>

        {error && <div className="mb-4 text-sm text-red-400">Failed to load countries.</div>}

        {/* Table */}
        <div className={C}>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-[#21262d]">
                <th className="w-8 px-4 py-3" />
                <th className="cursor-pointer select-none px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-ink-500" onClick={() => toggleSort("name")}>
                  Country<SortIcon active={sortKey === "name"} dir={sortDir} />
                </th>
                <th className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-ink-500">Region</th>
                <th className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-ink-500">Ratings (Norm.)</th>
                <th className="cursor-pointer select-none px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-ink-500" onClick={() => toggleSort("risk")}>
                  ATLAS Risk<SortIcon active={sortKey === "risk"} dir={sortDir} />
                </th>
                <th className="cursor-pointer select-none px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-ink-500" onClick={() => toggleSort("spread")}>
                  ATLAS Spread<SortIcon active={sortKey === "spread"} dir={sortDir} />
                </th>
                <th className="px-3 py-3 text-[10px] font-semibold uppercase tracking-wider text-ink-500">Trend</th>
                <th className="px-3 py-3 text-[10px] font-semibold uppercase tracking-wider text-ink-500">IMF</th>
                <th className="px-3 py-3 text-[10px] font-semibold uppercase tracking-wider text-ink-500">Flags</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 8 }, (_, i) => (
                  <tr key={i} className="border-b border-[#21262d]">
                    {Array.from({ length: 9 }, (_, j) => (
                      <td key={j} className="px-4 py-4"><div className="h-3.5 animate-pulse rounded bg-[#21262d]" style={{ width: `${40 + Math.random() * 40}%` }} /></td>
                    ))}
                  </tr>
                ))
              ) : rows.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-sm text-ink-500">No countries match your search.</td></tr>
              ) : (
                rows.map((c) => {
                  const b = bundles.get(c.iso3);
                  const risk = b?.risk;
                  const ratings = b?.ratings;
                  const spread = (b?.country as any)?.atlas_spread?.value_bps as number | undefined;
                  const imf = (b?.country as any)?.imf_program?.code as string | undefined;
                  const tags = ((b?.country as any)?.status_tags ?? []) as string[];
                  const agencies = ratings ? Object.entries(ratings.latest_per_agency) : [];
                  const regionShort = REGION_MAP[c.region] ?? c.region;
                  const capital = CAPITALS[c.iso3] ?? "";
                  const score = risk?.composite ?? 0;
                  const flags = tags.map(flagBadge).filter(Boolean) as { label: string; cls: string }[];

                  return (
                    <tr
                      key={c.iso3}
                      onClick={() => navigate(`/countries/${c.iso3}`)}
                      className="cursor-pointer border-b border-[#21262d] transition-colors last:border-b-0 hover:bg-[#1c2129]"
                    >
                      {/* Checkbox placeholder */}
                      <td className="px-4 py-3">
                        <div className="h-4 w-4 rounded border border-[#30363d]" />
                      </td>

                      {/* Country */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-7 w-7 items-center justify-center rounded-full border border-[#30363d] text-[9px] font-bold text-ink-400">{c.iso3.substring(0, 2)}</span>
                          <div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-[13px] font-medium text-ink-200">{c.name}</span>
                              <span className={`h-1.5 w-1.5 rounded-full ${statusDot(c.status)}`} />
                            </div>
                            <div className="text-[10px] text-ink-500">{capital}</div>
                          </div>
                        </div>
                      </td>

                      {/* Region */}
                      <td className="px-4 py-3">
                        <div className="text-[12px] text-ink-300">{regionShort}</div>
                        <div className="text-[10px] text-ink-500">{c.region}</div>
                      </td>

                      {/* Ratings */}
                      <td className="px-4 py-3">
                        {loading && !b ? (
                          <div className="h-3.5 w-24 animate-pulse rounded bg-[#21262d]" />
                        ) : (
                          <div className="flex gap-1">
                            {agencies.map(([, r]) => (
                              <span key={r.agency} className={`rounded border px-1.5 py-0.5 text-[9px] font-bold ${ratingPill(r.rating)}`}>
                                {r.rating}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>

                      {/* ATLAS Risk */}
                      <td className="px-4 py-3">
                        {loading && !b ? (
                          <div className="h-3.5 w-20 animate-pulse rounded bg-[#21262d]" />
                        ) : risk ? (
                          <div className="flex items-center gap-2.5">
                            <div className="h-2 w-16 overflow-hidden rounded-full bg-[#21262d]">
                              <div className="h-full rounded-full" style={{ width: `${score}%`, background: riskBarColor(score) }} />
                            </div>
                            <span className="text-[14px] font-bold tabular-nums" style={{ color: riskBarColor(score) }}>{score}</span>
                            <span className={`text-[10px] ${riskLabelColor(score)}`}>{riskLabel(score)}</span>
                          </div>
                        ) : <span className="text-ink-500">—</span>}
                      </td>

                      {/* ATLAS Spread */}
                      <td className="px-4 py-3">
                        {spread != null ? (
                          <span className="text-[13px] font-semibold tabular-nums text-orange-400">{spread >= 1000 ? `${Math.floor(spread / 1000)}\u2009${String(spread % 1000).padStart(3, "0")}` : spread}bps</span>
                        ) : <span className="text-ink-500">—</span>}
                      </td>

                      {/* Trend */}
                      <td className="px-3 py-3">
                        {score > 0 ? (
                          <svg className={`h-4 w-4 ${score >= 55 ? "text-red-400" : "text-green-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            {score >= 55 ? (
                              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6L9 12.75l4.286-4.286a11.948 11.948 0 014.306 6.43l.776 2.898" />
                            ) : (
                              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22" />
                            )}
                          </svg>
                        ) : <span className="text-ink-500">—</span>}
                      </td>

                      {/* IMF */}
                      <td className="px-3 py-3">
                        {imf ? (
                          <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${imfBadge(imf)}`}>{imf}</span>
                        ) : <span className="text-ink-500">—</span>}
                      </td>

                      {/* Flags */}
                      <td className="px-3 py-3">
                        <div className="flex gap-1">
                          {flags.map((f, i) => (
                            <span key={i} className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${f.cls}`}>{f.label}</span>
                          ))}
                          {flags.length === 0 && <span className="text-ink-500">—</span>}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="mt-3 text-center text-[10px] text-ink-600">
          ATLAS Coverage Universe · Data vintage: Q1 2026 · Sources: IMF, World Bank, Central Banks, Rating Agencies · Risk scores: deterministic composite model v2.0
        </div>
      </div>
    </AppShell>
  );
}
