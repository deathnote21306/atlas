import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "./AppShell";

/* ── Glass utility classes ── */

const glass =
  "bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-[10px] shadow-[0_4px_30px_rgba(0,0,0,0.2)]";
const glassStrong =
  "bg-white/[0.05] backdrop-blur-2xl border border-white/[0.08] rounded-[10px] shadow-[0_8px_32px_rgba(0,0,0,0.3)]";

const MARKET_LABELS = [
  "Brent Crude", "US 10Y Yield", "DXY Index",
  "EMBI+ Spread", "Gold", "SSA Avg CDS",
];

/* ── Types ── */

interface DashboardSummary {
  countries_under_watch: { elevated_count: number; total_count: number };
  portfolio_risk: { average_score: number; count: number };
  staleness_index: { fresh_pct: number; stale_count: number; very_stale_count: number };
  portfolio_risk_ranking: { rank: number; iso: string; name: string; score: number; label: string; status_tags: string[] }[];
  recent_rating_actions: { date: string; iso: string; country_name: string; agency: string; action: string; rating: string; outlook: string | null; action_type: string }[];
}

interface FeedArticle {
  id: string;
  headline: string;
  source: string;
  published_at: string | null;
  country_iso: string;
  country_name: string;
  tag_highlights: { axis: string; level: string }[];
}

/* ── Helpers ── */

const BADGE_STYLES: Record<string, string> = {
  crit: "bg-red-500/[0.12] text-red-500 border border-red-500/[0.15]",
  warn: "bg-amber-500/[0.12] text-amber-500 border border-amber-500/[0.15]",
  ok: "bg-green-500/[0.12] text-green-500 border border-green-500/[0.15]",
  info: "bg-white/[0.04] text-ink-400 border border-white/[0.06]",
};

function Badge({ label, type }: { label: string; type: string }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-semibold tracking-wide ${BADGE_STYLES[type] ?? BADGE_STYLES.info}`}>
      {label}
    </span>
  );
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-red-500";
  if (score >= 60) return "text-orange-500";
  if (score >= 30) return "text-amber-500";
  return "text-green-500";
}

function barGradient(score: number): string {
  if (score >= 80) return "linear-gradient(90deg, #f97316, #ef4444)";
  if (score >= 60) return "linear-gradient(90deg, #f59e0b, #f97316)";
  if (score >= 30) return "#f59e0b";
  return "#22c55e";
}

function riskTileColor(score: number): string {
  if (score >= 60) return "text-orange-500";
  if (score >= 30) return "text-amber-500";
  return "text-green-500";
}

function stalenessColor(pct: number): string {
  if (pct >= 85) return "text-green-500";
  if (pct >= 70) return "text-amber-500";
  if (pct >= 50) return "text-orange-500";
  return "text-red-500";
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function actionColor(type: string): string {
  if (type === "downgrade") return "crit";
  if (type === "upgrade") return "ok";
  return "info";
}

/* ── Dashboard Component ── */

export default function Dashboard() {
  const { data: summary } = useQuery<DashboardSummary>({
    queryKey: ["dashboard-summary"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/summary"),
    staleTime: 60_000,
  });

  const { data: feed } = useQuery<{ articles: FeedArticle[] }>({
    queryKey: ["dashboard-feed"],
    queryFn: () => api<{ articles: FeedArticle[] }>("/api/dashboard/intelligence-feed?limit=5&min_impact=40&since_days=90"),
    staleTime: 60_000,
  });

  const ranking = summary?.portfolio_risk_ranking ?? [];
  const ratings = summary?.recent_rating_actions ?? [];
  const articles = feed?.articles ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-[1400px]">
        <h1 className="mb-5 text-lg font-semibold text-ink-100" style={{ textShadow: "0 0 40px rgba(59,130,246,0.15)" }}>
          Strategic Command Center
        </h1>

        {/* ── Global Market Indicators (Phase 4b placeholders) ── */}
        <div className={`${glass} mb-4 flex overflow-hidden`}>
          {MARKET_LABELS.map((label, i) => (
            <div
              key={label}
              className={`flex flex-1 flex-col gap-0.5 px-4 py-2.5 ${i < MARKET_LABELS.length - 1 ? "border-r border-white/[0.04]" : ""}`}
            >
              <span className="text-[10px] font-medium uppercase tracking-wide text-white/30">{label}</span>
              <span className="text-[15px] font-bold tabular-nums text-ink-500">&mdash;</span>
              <span className="text-[10px] text-ink-600">Data pending &middot; Phase 4b</span>
            </div>
          ))}
        </div>

        {/* ── KPI Cards ── */}
        <div className="mb-5 grid grid-cols-4 gap-3.5">
          {/* Countries Under Watch */}
          <div className={`${glassStrong} p-5`}>
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/35">Countries Under Watch</div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-4xl font-bold tabular-nums text-ink-100" style={{ textShadow: "0 2px 12px rgba(59,130,246,0.15)" }}>
                {summary?.countries_under_watch.elevated_count ?? "\u2014"}
              </span>
              <span className="text-sm text-red-500">
                of {summary?.countries_under_watch.total_count ?? 10} elevated
              </span>
            </div>
          </div>

          {/* Portfolio Risk */}
          <div className={`${glassStrong} p-5`}>
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/35">Portfolio Risk</div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className={`text-4xl font-bold tabular-nums ${riskTileColor(summary?.portfolio_risk.average_score ?? 0)}`} style={{ textShadow: "0 2px 12px rgba(245,158,11,0.15)" }}>
                {summary?.portfolio_risk.average_score ?? "\u2014"}
              </span>
            </div>
            {summary && (
              <div className="mt-3 h-1 overflow-hidden rounded-sm bg-white/[0.06]">
                <div className="h-full rounded-sm" style={{ width: `${summary.portfolio_risk.average_score}%`, background: "linear-gradient(90deg, #22c55e, #84cc16, #f59e0b, #ef4444)" }} />
              </div>
            )}
          </div>

          {/* Active Alerts (Phase 4c placeholder) */}
          <div className={`${glassStrong} p-5`}>
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/35">Active Alerts</div>
            <div className="mt-2">
              <span className="text-4xl font-bold tabular-nums text-ink-500">&mdash;</span>
            </div>
            <div className="mt-2 text-[10px] text-ink-600">Alerts service pending &middot; Phase 4c</div>
          </div>

          {/* Staleness Index */}
          <div className={`${glassStrong} p-5`}>
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/35">Staleness Index</div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className={`text-4xl font-bold tabular-nums ${stalenessColor(summary?.staleness_index.fresh_pct ?? 0)}`} style={{ textShadow: "0 2px 12px rgba(34,197,94,0.15)" }}>
                {summary ? `${summary.staleness_index.fresh_pct}%` : "\u2014"}
              </span>
              <span className={`text-sm ${stalenessColor(summary?.staleness_index.fresh_pct ?? 0)}`}>Fresh</span>
            </div>
            {summary && (summary.staleness_index.stale_count + summary.staleness_index.very_stale_count) > 0 && (
              <div className="mt-2 text-[11px] text-white/25">
                {summary.staleness_index.stale_count + summary.staleness_index.very_stale_count} indicators stale &gt; 7d
              </div>
            )}
          </div>
        </div>

        {/* ── Two-column: Risk Ranking + Alerts ── */}
        <div className="grid grid-cols-2 gap-4">
          {/* Left column */}
          <div className="flex flex-col gap-3.5">
            {/* Portfolio Risk Ranking */}
            <div className={glassStrong}>
              <div className="border-b border-white/[0.05] px-4 py-3.5 text-[11px] font-semibold uppercase tracking-wider text-white/40">
                Portfolio Risk Ranking
              </div>
              {ranking.map((c) => (
                <Link
                  key={c.iso}
                  to={`/countries/${c.iso}`}
                  className="flex items-center gap-3 border-b border-white/[0.03] px-4 py-2.5 transition-colors duration-150 last:border-b-0 hover:bg-white/[0.03]"
                >
                  <span className="w-[18px] text-right text-xs text-white/25">{c.rank}</span>
                  <span className="flex h-6 w-8 items-center justify-center rounded bg-ink-700 text-[9px] font-semibold text-ink-300">
                    {c.iso}
                  </span>
                  <span className="flex-1 text-[13px] font-medium text-ink-200">{c.name}</span>
                  <div className="h-[5px] w-20 overflow-hidden rounded-sm bg-white/[0.06]">
                    <div className="h-full rounded-sm" style={{ width: `${c.score}%`, background: barGradient(c.score) }} />
                  </div>
                  <span className={`w-10 text-right text-[13px] font-semibold tabular-nums ${scoreColor(c.score)}`}>
                    {c.score}
                  </span>
                </Link>
              ))}
            </div>

            {/* Recent Rating Actions */}
            <div className={glassStrong}>
              <div className="border-b border-white/[0.05] px-4 py-3.5 text-[11px] font-semibold uppercase tracking-wider text-white/40">
                Recent Rating Actions
              </div>
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    {["Date", "Country", "Agency", "Action", "Rating"].map((h) => (
                      <th key={h} className="bg-white/[0.02] px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-white/25">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ratings.slice(0, 8).map((r, i) => (
                    <tr key={`${r.date}-${r.iso}-${r.agency}-${i}`} className="border-b border-white/[0.03]">
                      <td className="px-3 py-2 font-mono text-[11px] text-white/25">{formatDate(r.date)}</td>
                      <td className="px-3 py-2 text-[13px] text-ink-300">{r.country_name}</td>
                      <td className="px-3 py-2 text-[13px] text-ink-300">{r.agency}</td>
                      <td className="px-3 py-2">
                        <Badge label={r.action} type={actionColor(r.action_type)} />
                      </td>
                      <td className="px-3 py-2 font-mono text-[13px] text-ink-300">{r.rating}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right column: Alerts & Intelligence */}
          <div className={glassStrong}>
            <div className="border-b border-white/[0.05] px-4 py-3.5 text-[11px] font-semibold uppercase tracking-wider text-white/40">
              Alerts & Intelligence
            </div>

            {/* Alerts placeholder */}
            <div className="border-b border-white/[0.04] px-4 py-6 text-center">
              <p className="text-xs text-ink-500">Alerts and intelligence service coming in Phase 4c</p>
            </div>

            {/* Intelligence Feed divider */}
            <div className="border-b border-white/[0.04] bg-white/[0.015] px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-white/20">
              Intelligence Feed
            </div>

            {/* Real news from API */}
            {articles.map((item) => (
              <Link
                key={item.id}
                to={`/countries/${item.country_iso}?tab=news&article=${item.id}`}
                className="block border-b border-white/[0.03] px-4 py-3 transition-colors duration-150 hover:bg-white/[0.02]"
              >
                <div className="text-[13px] font-medium text-ink-200">{item.headline}</div>
                <div className="mt-1 flex gap-1.5 text-[11px] text-white/25">
                  <span>{item.source}</span>
                  <span>&bull;</span>
                  <span>{timeAgo(item.published_at)}</span>
                </div>
                {item.tag_highlights.length > 0 && (
                  <div className="mt-1.5 flex gap-1">
                    {item.tag_highlights.map((t) => (
                      <Badge
                        key={t.axis}
                        label={`${t.axis.charAt(0).toUpperCase() + t.axis.slice(1)} ${t.level}`}
                        type={t.level === "H" ? "crit" : "warn"}
                      />
                    ))}
                  </div>
                )}
              </Link>
            ))}

            {articles.length === 0 && (
              <div className="px-4 py-6 text-center text-xs text-ink-500">
                No high-impact articles in the last 90 days
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
