import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "./AppShell";

/* ── Card style — flat, no border, no glass ── */

const C = "rounded-lg bg-[#1b2235]";

const THEMATIC_BORDER: Record<string, string> = {
  amber:  "border-l-amber-500/70",
  purple: "border-l-purple-500/70",
  cyan:   "border-l-cyan-500/70",
  green:  "border-l-green-500/70",
};

/* ── Types ── */

interface RankedCountry {
  iso: string;
  name: string;
  score: number;
  region: string;
  spread_bps: number | null;
}

interface Alert {
  severity: string;
  iso3: string;
  country: string;
  message: string;
}

interface ThematicCard {
  title: string;
  color: string;
  countries: string[];
  description: string;
}

interface DashboardSummary {
  as_of: string;
  countries_under_watch: { elevated_count: number; total_count: number };
  portfolio_risk: { average_score: number; count: number };
  imf_program_count: number;
  staleness_index: { fresh_pct: number; stale_count: number; very_stale_count: number };
  alerts: Alert[];
  top_deteriorating: RankedCountry[];
  top_improving: RankedCountry[];
  portfolio_risk_ranking: { rank: number; iso: string; name: string; score: number; label: string; status_tags: string[] }[];
  recent_rating_actions: { date: string; iso: string; country_name: string; agency: string; action: string; rating: string; outlook: string | null; action_type: string }[];
  thematic_intelligence: ThematicCard[];
  coverage_risk_map: { iso: string; score: number }[];
}

interface FeedArticle {
  id: string;
  headline: string;
  source: string;
  published_at: string | null;
  country_iso: string;
  country_name: string;
  overall_impact: number;
  tag_highlights: { axis: string; level: string }[];
}

/* ── Market data (static until ingester is wired) ── */

const MARKET_DATA = [
  { label: "VIX", value: "18.2", delta: "-1.4", negative: true },
  { label: "EM SPREAD (EMBI)", value: "398bps", delta: "+12bps", negative: false },
  { label: "BRENT", value: "USD 72.4", delta: "-0.8", negative: true },
  { label: "DXY", value: "104.2", delta: "+0.3", negative: false },
  { label: "UST 10Y", value: "4.52%", delta: "-3bps", negative: true },
  { label: "GOLD", value: "USD 2,312", delta: "+18", negative: false },
];

/* ── Helpers ── */

function scoreColor(s: number) {
  if (s >= 80) return "text-red-500";
  if (s >= 60) return "text-orange-500";
  if (s >= 40) return "text-amber-500";
  return "text-green-500";
}
function barColor(s: number) {
  if (s >= 80) return "#ef4444";
  if (s >= 60) return "#f97316";
  if (s >= 40) return "#f59e0b";
  return "#22c55e";
}
function dotColor(s: number) {
  if (s >= 75) return "bg-red-500";
  if (s >= 60) return "bg-orange-500";
  if (s >= 40) return "bg-amber-500";
  return "bg-green-500";
}
function fmtDate(iso: string) { return new Date(iso).toLocaleDateString("en-CA"); }
function fmtShort(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.toLocaleDateString("en-US", { month: "short" })} ${d.getDate()}`;
}
function actionBadge(t: string) {
  if (t === "downgrade") return "bg-red-500/20 text-red-400";
  if (t === "upgrade") return "bg-green-500/20 text-green-400";
  if (t === "affirm") return "bg-[#1e2b42] text-ink-400";
  return "bg-amber-500/20 text-amber-400";
}
function outlookClr(o: string | null) {
  if (!o) return "text-ink-500";
  const l = o.toLowerCase();
  if (l.includes("negative")) return "text-red-400";
  if (l.includes("positive")) return "text-green-400";
  return "text-ink-400";
}

/* ── Icons ── */

const Globe = () => (
  <svg className="h-6 w-6 text-emerald-500/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5a17.92 17.92 0 01-8.716-2.247m0 0A9 9 0 013 12c0-1.605.42-3.113 1.157-4.418" />
  </svg>
);
const AlertTri = () => (
  <svg className="h-6 w-6 text-amber-500/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
  </svg>
);
const Chart = () => (
  <svg className="h-6 w-6 text-blue-500/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
  </svg>
);
const TrendUp = () => (
  <svg className="h-6 w-6 text-emerald-500/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
  </svg>
);
const TrendDown = () => (
  <svg className="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6L9 12.75l4.286-4.286a11.948 11.948 0 014.306 6.43l.776 2.898m0 0l3.182-5.511m-3.182 5.51l-5.511-3.181" />
  </svg>
);
const TrendUpSm = () => (
  <svg className="h-4 w-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
  </svg>
);

/* ── Dashboard ── */

export default function Dashboard() {
  const [alertIdx, setAlertIdx] = useState(0);

  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/summary"),
    staleTime: 60_000,
  });
  const { data: feed } = useQuery<{ articles: FeedArticle[] }>({
    queryKey: ["dashboard-feed"],
    queryFn: () => api<{ articles: FeedArticle[] }>("/api/dashboard/intelligence-feed?limit=6&min_impact=40&since_days=90"),
    staleTime: 60_000,
  });

  const ratings = summary?.recent_rating_actions ?? [];
  const articles = feed?.articles ?? [];
  const alerts = summary?.alerts ?? [];
  const det = summary?.top_deteriorating ?? [];
  const imp = summary?.top_improving ?? [];
  const thematic = summary?.thematic_intelligence ?? [];
  const riskMap = summary?.coverage_risk_map ?? [];
  const feat = alerts[alertIdx];

  return (
    <AppShell>
      <div className="mx-auto max-w-[1440px] px-6 pb-10">

        {/* ── Header ── */}
        <div className="flex items-center justify-between pb-5 pt-4">
          <div>
            <div className="text-[11px] text-ink-500">ATLAS <span className="mx-1 text-ink-600">&rsaquo;</span> Dashboard</div>
            <h1 className="mt-0.5 text-[16px] font-normal text-ink-100">Strategic Command Center</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <input type="text" placeholder="Search countries..." className="w-56 rounded-md border border-[#2a3a52] bg-[#131929] py-2 pl-9 pr-3 text-sm text-ink-200 placeholder:text-ink-500 focus:border-blue-500/40 focus:outline-none" />
            </div>
            <button className="flex items-center gap-2 rounded-md border border-red-500/40 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-500/10">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" /></svg>
              {alerts.length} Active
              <span className="h-2 w-2 rounded-full bg-red-500" />
            </button>
          </div>
        </div>

        {/* ── Market Indicators ── */}
        <div className={`${C} mb-3 px-5 py-3`}>
          <div className="mb-2 flex items-center gap-2">
            <span className="text-sm text-amber-500">⚡</span>
            <span className="text-[10px] font-normal uppercase tracking-wider text-ink-500">Global Market Indicators · Static Reference Data</span>
          </div>
          <div className="flex items-baseline gap-8">
            {MARKET_DATA.map((m) => (
              <div key={m.label} className="flex flex-col">
                <span className="text-[10px] text-ink-500">{m.label}</span>
                <span className="text-[14px] font-medium tabular-nums text-ink-100">{m.value}</span>
                <span className={`text-[11px] font-medium tabular-nums ${m.negative ? "text-red-400" : "text-green-400"}`}>{m.delta}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── KPI Cards ── */}
        <div className="mb-3 grid grid-cols-4 gap-3">
          <div className={`${C} flex items-start justify-between px-5 py-4`}>
            <div>
              <div className="text-[12px] text-ink-400">Countries Under Watch</div>
              <div className="mt-2 text-[30px] font-semibold leading-none tabular-nums text-ink-100">{summary?.countries_under_watch.elevated_count ?? "—"}</div>
            </div>
            <Globe />
          </div>
          <div className={`${C} flex items-start justify-between px-5 py-4`}>
            <div>
              <div className="text-[12px] text-ink-400">Active Alerts</div>
              <div className="mt-2 text-[30px] font-semibold leading-none tabular-nums text-ink-100">{alerts.length || "—"}</div>
            </div>
            <AlertTri />
          </div>
          <div className={`${C} flex items-start justify-between px-5 py-4`}>
            <div>
              <div className="text-[12px] text-ink-400">Avg Coverage Risk</div>
              <div className="mt-2 text-[30px] font-semibold leading-none tabular-nums text-ink-100">{summary?.portfolio_risk.average_score ?? "—"}</div>
            </div>
            <Chart />
          </div>
          <div className={`${C} flex items-start justify-between px-5 py-4`}>
            <div>
              <div className="text-[12px] text-ink-400">In IMF Programs</div>
              <div className="mt-2 text-[30px] font-semibold leading-none tabular-nums text-ink-100">{summary?.imf_program_count ?? "—"}</div>
            </div>
            <TrendUp />
          </div>
        </div>

        {/* ══════════════════════════════════════════════════════ */}
        {/* ── TWO-COLUMN LAYOUT: Left ~2/3 + Right ~1/3 ── */}
        {/* ══════════════════════════════════════════════════════ */}
        <div className="grid grid-cols-[1fr_400px] gap-3">

          {/* ── LEFT COLUMN ── */}
          <div className="flex flex-col gap-3">

            {/* Deteriorating + Improving side by side */}
            <div className="grid grid-cols-2 gap-3">
              <div className={`${C} px-5 py-4`}>
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2"><TrendDown /><span className="text-[13px] font-medium text-ink-200">Top Deteriorating</span></div>
                  <Link to="/countries" className="text-[11px] font-medium text-blue-400">View all</Link>
                </div>
                {det.length === 0 ? (
                  <div className="py-4 text-center text-[12px] text-ink-500">No high-risk countries</div>
                ) : det.map((c) => (
                  <Link key={c.iso} to={`/countries/${c.iso}`} className="flex items-center gap-3 py-2.5 hover:opacity-80">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full border border-[#2a3a52] text-[9px] font-bold text-ink-400">{c.iso}</span>
                    <div className="flex-1">
                      <div className="text-[13px] font-medium text-ink-200">{c.name}</div>
                      <div className="text-[10px] text-ink-500">{c.region}</div>
                    </div>
                    <div className="text-right">
                      <span className={`text-[15px] font-semibold tabular-nums ${scoreColor(c.score)}`}>{c.score}</span>
                      {c.spread_bps != null && <div className="text-[10px] text-ink-500">{c.spread_bps}bps</div>}
                    </div>
                  </Link>
                ))}
              </div>
              <div className={`${C} px-5 py-4`}>
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex items-center gap-2"><TrendUpSm /><span className="text-[13px] font-medium text-ink-200">Top Improving</span></div>
                  <Link to="/countries" className="text-[11px] font-medium text-blue-400">View all</Link>
                </div>
                {imp.length === 0 ? (
                  <div className="py-4 text-center text-[12px] text-ink-500">No low-risk countries</div>
                ) : imp.map((c) => (
                  <Link key={c.iso} to={`/countries/${c.iso}`} className="flex items-center gap-3 py-2.5 hover:opacity-80">
                    <span className="flex h-7 w-7 items-center justify-center rounded-full border border-[#2a3a52] text-[9px] font-bold text-ink-400">{c.iso}</span>
                    <div className="flex-1">
                      <div className="text-[13px] font-medium text-ink-200">{c.name}</div>
                      <div className="text-[10px] text-ink-500">{c.region}</div>
                    </div>
                    <div className="text-right">
                      <span className={`text-[15px] font-semibold tabular-nums ${scoreColor(c.score)}`}>{c.score}</span>
                      <div className="flex items-center gap-0.5 text-[10px] text-green-400">↗ improving</div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>

            {/* Recent Rating Actions */}
            <div className="flex items-center justify-between">
              <span className="text-[14px] font-medium text-ink-200">Recent Rating Actions</span>
              <span className="text-[11px] uppercase tracking-wider text-ink-500">Last 6 Months</span>
            </div>
            <div className={C}>
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-[#1e2b42]">
                    {["Date", "Country", "Agency", "Action", "From", "To", "Outlook"].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-left text-[10px] font-medium uppercase tracking-wider text-ink-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ratings.length === 0 ? (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-[12px] text-ink-500">No recent rating actions</td></tr>
                  ) : ratings.slice(0, 8).map((r, i) => {
                    const prev = i < ratings.length - 1 ? ratings[i + 1] : null;
                    const from = prev?.iso === r.iso && prev?.agency === r.agency ? prev.rating : "—";
                    return (
                      <tr key={`${r.date}-${r.iso}-${r.agency}-${i}`} className="border-b border-[#1e2b42] last:border-b-0">
                        <td className="px-4 py-3 font-mono text-[12px] text-ink-500">{fmtDate(r.date)}</td>
                        <td className="px-4 py-3 text-[13px] font-medium text-ink-200">{r.country_name}</td>
                        <td className="px-4 py-3 text-[13px] text-ink-400">{r.agency}</td>
                        <td className="px-4 py-3"><span className={`inline-block rounded px-2.5 py-0.5 text-[10px] font-semibold ${actionBadge(r.action_type)}`}>{r.action}</span></td>
                        <td className="px-4 py-3 font-mono text-[13px] text-ink-400">{from}{r.outlook && from !== "—" ? ` ${r.outlook}` : ""}</td>
                        <td className="px-4 py-3 font-mono text-[13px] font-semibold text-ink-200">{r.rating}</td>
                        <td className={`px-4 py-3 text-[13px] ${outlookClr(r.outlook)}`}>{r.outlook ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Thematic Intelligence 2×2 */}
            {thematic.length > 0 && (
              <div className="grid grid-cols-2 gap-3">
                {thematic.map((card) => (
                  <div key={card.title} className={`${C} border-l-2 ${THEMATIC_BORDER[card.color] ?? "border-l-slate-500/70"} p-4`}>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="text-[13px] font-medium text-ink-200">{card.title}</span>
                      <div className="flex flex-shrink-0 gap-1">
                        {card.countries.map((iso) => (
                          <span key={iso} className="rounded bg-[#1e2b42] px-1.5 py-0.5 text-[9px] font-semibold text-ink-400">{iso}</span>
                        ))}
                      </div>
                    </div>
                    <p className="text-[11px] leading-[1.6] text-ink-500">{card.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── RIGHT COLUMN (continuous) ── */}
          <div className="flex flex-col gap-3">

            {/* Live Alerts */}
            <div className={`${C} px-5 py-4`}>
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-red-500" />
                  <span className="text-[13px] font-medium text-ink-200">Live Alerts</span>
                </div>
                <span className="cursor-pointer text-[11px] font-medium text-blue-400">Manage</span>
              </div>
              {alerts.length === 0 ? (
                <div className="py-4 text-center text-[12px] text-ink-500">No active alerts</div>
              ) : (
                <>
                  {feat && (
                    <div className="mb-3 rounded-lg border border-red-500/20 bg-red-500/[0.06] px-3 py-3">
                      <div className="flex items-center gap-2">
                        <svg className="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>
                        <span className="rounded bg-red-500/30 px-1.5 py-0.5 text-[9px] font-bold uppercase text-red-300">{feat.severity === "CRITICAL" ? "Critical" : "High"}</span>
                        <span className="text-[10px] text-ink-400">{feat.country}</span>
                        <div className="ml-auto flex items-center gap-1.5">
                          <button onClick={() => setAlertIdx((i) => (i - 1 + alerts.length) % alerts.length)} className="rounded p-0.5 text-ink-500 hover:text-ink-300">‹</button>
                          <span className="text-[10px] text-ink-500">{alertIdx + 1}/{alerts.length}</span>
                          <button onClick={() => setAlertIdx((i) => (i + 1) % alerts.length)} className="rounded p-0.5 text-ink-500 hover:text-ink-300">›</button>
                        </div>
                      </div>
                      <div className="mt-2 text-[12px] font-medium text-ink-200">{feat.message}</div>
                    </div>
                  )}
                  {alerts.filter((_, i) => i !== alertIdx).slice(0, 4).map((a, i) => (
                    <div key={i} className="flex items-start gap-2.5 py-2">
                      <span className={`mt-1.5 h-2 w-2 flex-shrink-0 rounded-full ${a.severity === "CRITICAL" ? "bg-red-500" : "bg-amber-500"}`} />
                      <div>
                        <div className="text-[12px] font-medium text-ink-200">{a.message}</div>
                        <div className="text-[10px] text-ink-500">{a.country}</div>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>

            {/* Intelligence Feed */}
            <div className={C}>
              <div className="flex items-center justify-between border-b border-[#1e2b42] px-4 py-3">
                <span className="text-[13px] font-medium text-ink-200">Intelligence Feed</span>
                <Link to="/news" className="text-[11px] font-medium text-blue-400">Full feed</Link>
              </div>
              {articles.map((item) => (
                <Link key={item.id} to={`/countries/${item.country_iso}?tab=news&article=${item.id}`} className="flex items-start gap-3 border-b border-[#1e2b42] px-4 py-2.5 last:border-b-0 hover:bg-[#1e2840]">
                  <span className={`mt-1.5 h-2.5 w-2.5 flex-shrink-0 rounded-full ${dotColor(item.overall_impact)}`} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[12px] font-medium leading-snug text-ink-200">{item.headline}</div>
                    <div className="mt-0.5 text-[10px] text-ink-500">{item.source} · {fmtShort(item.published_at)}</div>
                  </div>
                  <span className={`flex-shrink-0 text-[13px] font-semibold tabular-nums ${scoreColor(item.overall_impact)}`}>{item.overall_impact}</span>
                </Link>
              ))}
              {articles.length === 0 && <div className="px-4 py-6 text-center text-[11px] text-ink-500">No high-impact articles in the last 90 days</div>}
            </div>

            {/* Coverage Risk Map */}
            <div className={C}>
              <div className="border-b border-[#1e2b42] px-4 py-3">
                <span className="text-[13px] font-medium text-ink-200">Coverage Risk Map</span>
              </div>
              <div className="px-4 py-3">
                {riskMap.map((c) => (
                  <div key={c.iso} className="mb-2 flex items-center gap-3 last:mb-0">
                    <span className="w-6 text-[11px] font-medium text-ink-400">{c.iso}</span>
                    <div className="h-[14px] flex-1 overflow-hidden rounded-sm bg-[#1e2b42]">
                      <div className="h-full rounded-sm" style={{ width: `${c.score}%`, background: barColor(c.score) }} />
                    </div>
                    <span className={`w-8 text-right text-[12px] font-semibold tabular-nums ${scoreColor(c.score)}`}>{c.score}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
