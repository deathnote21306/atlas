import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "./AppShell";

/* ── Types ── */

interface Country {
  iso3: string;
  name: string;
  region: string;
  status: string;
}

interface NewsScore {
  fiscal_impact: string;
  external_impact: string;
  fx_impact: string;
  political_impact: string;
}

interface NewsItem {
  id: string;
  title: string;
  source: string;
  published_at: string;
  primary_iso3: string;
  event_type: string;
  score?: NewsScore;
}

/* ── Glass utility classes ── */

const glass =
  "bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-[10px] shadow-[0_4px_30px_rgba(0,0,0,0.2)]";
const glassStrong =
  "bg-white/[0.05] backdrop-blur-2xl border border-white/[0.08] rounded-[10px] shadow-[0_8px_32px_rgba(0,0,0,0.3)]";

/* ── Static / Mock Data ── */

// TODO: integrate real market data feed
const MARKET_INDICATORS = [
  { label: "Brent Crude", value: "$78.42", delta: "\u25BC 1.8%", color: "danger" },
  { label: "US 10Y Yield", value: "4.63%", delta: "\u25B2 12bps", color: "danger" },
  { label: "DXY Index", value: "106.2", delta: "\u25B2 0.4%", color: "danger" },
  { label: "EMBI+ Spread", value: "398bps", delta: "\u25B2 15bps", color: "warning" },
  { label: "Gold", value: "$2,152", delta: "\u25B2 0.6%", color: "positive" },
  { label: "SSA Avg CDS", value: "524bps", delta: "\u25B2 22bps", color: "danger" },
] as const;

// TODO: replace with real API data
const RISK_RANKING = [
  { rank: 1, flag: "\uD83C\uDDEA\uD83C\uDDF9", name: "Ethiopia", iso3: "ETH", score: 72.4, barWidth: 72, gradient: "linear-gradient(90deg, #f97316, #ef4444)", bgTint: "rgba(239,68,68,0.04)", scoreClass: "text-red-500" },
  { rank: 2, flag: "\uD83C\uDDF0\uD83C\uDDEA", name: "Kenya", iso3: "KEN", score: 61.8, barWidth: 62, gradient: "linear-gradient(90deg, #f59e0b, #f97316)", bgTint: "rgba(249,115,22,0.04)", scoreClass: "text-orange-500" },
  { rank: 3, flag: "\uD83C\uDDF3\uD83C\uDDEC", name: "Nigeria", iso3: "NGA", score: 55.3, barWidth: 55, gradient: "#f59e0b", bgTint: "transparent", scoreClass: "text-amber-500" },
  { rank: 4, flag: "\uD83C\uDDEA\uD83C\uDDEC", name: "Egypt", iso3: "EGY", score: 49.1, barWidth: 49, gradient: "#f59e0b", bgTint: "transparent", scoreClass: "text-amber-500" },
  { rank: 5, flag: "\uD83C\uDDEC\uD83C\uDDED", name: "Ghana", iso3: "GHA", score: 44.2, barWidth: 44, gradient: "#84cc16", bgTint: "transparent", scoreClass: "text-lime-500" },
  { rank: 6, flag: "\uD83C\uDDF8\uD83C\uDDF3", name: "Senegal", iso3: "SEN", score: 33.1, barWidth: 33, gradient: "#22c55e", bgTint: "transparent", scoreClass: "text-green-500" },
  { rank: 7, flag: "\uD83C\uDDF7\uD83C\uDDFC", name: "Rwanda", iso3: "RWA", score: 37.2, barWidth: 37, gradient: "#22c55e", bgTint: "transparent", scoreClass: "text-green-500" },
  { rank: 8, flag: "\uD83C\uDDF2\uD83C\uDDE6", name: "Morocco", iso3: "MAR", score: 28.4, barWidth: 28, gradient: "#22c55e", bgTint: "transparent", scoreClass: "text-green-500" },
] as const;

// TODO: replace with real API data
const RATING_ACTIONS = [
  { date: "Apr 15", country: "Kenya", agency: "S&P", action: "\u2193 Down", actionType: "crit" as const, rating: "B-" },
  { date: "Apr 12", country: "Morocco", agency: "Fitch", action: "\u2191 Up", actionType: "ok" as const, rating: "BBB-" },
  { date: "Apr 08", country: "Egypt", agency: "Moody's", action: "\u26A0 Outlook", actionType: "warn" as const, rating: "Neg" },
] as const;

// TODO: replace with real API data
const ALERTS = [
  { severity: "crit" as const, text: "Ethiopia ATLAS Spread > 1,400bps", time: "12 min ago" },
  { severity: "crit" as const, text: "Kenya FX Parallel Premium > 15%", time: "34 min ago" },
  { severity: "warn" as const, text: "Ghana Export Cover < 3 months", time: "1h ago" },
] as const;

// TODO: replace with real API data
const SUMMARY_CARDS = [
  {
    title: "Ethiopia: Birr Under Pressure",
    body: "The National Bank allowed a 2.8% depreciation this week amid declining reserves. IMF has signaled concern over the pace of forex liberalization. Parallel market premium widening to 18%.",
    severity: "crit" as const,
    badges: [
      { label: "Fiscal H", type: "crit" as const },
      { label: "FX H", type: "crit" as const },
    ],
    updated: "2h ago",
  },
  {
    title: "Kenya: Revenue Shortfall Deepens",
    body: "KRA missed Q1 target by KES 45Bn, widening the fiscal gap to 6.2% of GDP. Treasury considering supplementary budget cuts. S&P downgraded to B- citing debt sustainability.",
    severity: "warn" as const,
    badges: [
      { label: "Fiscal H", type: "crit" as const },
      { label: "Ext M", type: "warn" as const },
    ],
    updated: "4h ago",
  },
  {
    title: "Morocco: Green Bond Success",
    body: "Morocco's \u20AC2.1B green bond was 3.2x oversubscribed. Proceeds earmarked for renewable energy and water infrastructure. Fitch upgraded outlook to positive.",
    severity: "ok" as const,
    badges: [
      { label: "Ext L", type: "ok" as const },
      { label: "Fiscal L", type: "ok" as const },
    ],
    updated: "6h ago",
  },
] as const;

/* ── Helpers ── */

const DELTA_COLORS: Record<string, string> = {
  danger: "text-red-500",
  warning: "text-amber-500",
  positive: "text-green-500",
};

const BADGE_STYLES: Record<string, string> = {
  crit: "bg-red-500/[0.12] text-red-500 border border-red-500/[0.15]",
  warn: "bg-amber-500/[0.12] text-amber-500 border border-amber-500/[0.15]",
  info: "bg-blue-500/[0.12] text-blue-400 border border-blue-500/[0.15]",
  ok: "bg-green-500/[0.12] text-green-500 border border-green-500/[0.15]",
};

const DOT_STYLES: Record<string, React.CSSProperties> = {
  crit: { background: "#ef4444", boxShadow: "0 0 8px rgba(239,68,68,0.5), 0 0 20px rgba(239,68,68,0.2)" },
  warn: { background: "#f59e0b", boxShadow: "0 0 8px rgba(245,158,11,0.4)" },
  info: { background: "#3b82f6", boxShadow: "0 0 8px rgba(59,130,246,0.4)" },
};

const BORDER_GLOW: Record<string, React.CSSProperties> = {
  crit: { borderLeft: "3px solid rgba(239,68,68,0.6)" },
  warn: { borderLeft: "3px solid rgba(245,158,11,0.5)" },
};

const SUMMARY_BORDER: Record<string, React.CSSProperties> = {
  crit: { background: "linear-gradient(180deg, #ef4444, rgba(239,68,68,0.3))", boxShadow: "0 0 12px rgba(239,68,68,0.3)" },
  warn: { background: "linear-gradient(180deg, #f59e0b, rgba(245,158,11,0.3))", boxShadow: "0 0 12px rgba(245,158,11,0.3)" },
  ok: { background: "linear-gradient(180deg, #22c55e, rgba(34,197,94,0.3))", boxShadow: "0 0 12px rgba(34,197,94,0.3)" },
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function impactToBadge(level: string): { label: string; type: string } | null {
  if (!level || level === "none") return null;
  const short = level === "high" ? "H" : level === "medium" ? "M" : "L";
  const type = level === "high" ? "crit" : level === "medium" ? "warn" : level === "low" ? "ok" : "info";
  return { label: short, type };
}

function Badge({ label, type }: { label: string; type: string }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-semibold tracking-wide ${BADGE_STYLES[type] ?? BADGE_STYLES.info}`}>
      {label}
    </span>
  );
}

/* ── Dashboard Component ── */

export default function Dashboard() {
  const { data: countries } = useQuery<Country[]>({
    queryKey: ["countries"],
    queryFn: () => api<Country[]>("/api/countries"),
    staleTime: 5 * 60 * 1000,
  });

  const { data: news } = useQuery<NewsItem[]>({
    queryKey: ["news"],
    queryFn: () => api<NewsItem[]>("/api/news?limit=10"),
    staleTime: 2 * 60 * 1000,
  });

  const countryCount = countries?.length ?? 0;

  // TODO: replace with real API data — derive from actual risk scores
  const elevatedCount = 5;
  const portfolioRisk = 59;
  const portfolioRiskDelta = 4.2;
  const activeAlertsCrit = 3;
  const activeAlertsWarn = 5;
  const stalenessIndex = 92;
  const staleIndicators = 2;

  return (
    <AppShell>
      <div className="mx-auto max-w-[1400px]">
        {/* Page title */}
        <h1
          className="mb-5 text-lg font-semibold text-ink-100"
          style={{ textShadow: "0 0 40px rgba(59,130,246,0.15)" }}
        >
          Strategic Command Center
        </h1>

        {/* ── Global Market Indicators ── */}
        <div className={`${glass} mb-4 flex overflow-hidden`}>
          {MARKET_INDICATORS.map((m, i) => (
            <div
              key={m.label}
              className={`flex flex-1 flex-col gap-0.5 px-4 py-2.5 ${i < MARKET_INDICATORS.length - 1 ? "border-r border-white/[0.04]" : ""}`}
            >
              <span className="text-[10px] font-medium uppercase tracking-wide text-white/30">
                {m.label}
              </span>
              <span className="text-[15px] font-bold tabular-nums text-ink-100">
                {m.value}
              </span>
              <span className={`text-[11px] font-medium tabular-nums ${DELTA_COLORS[m.color]}`}>
                {m.delta}
              </span>
            </div>
          ))}
        </div>

        {/* ── KPI Cards ── */}
        <div className="mb-5 grid grid-cols-4 gap-3.5">
          {/* Countries Under Watch */}
          <div className={`${glassStrong} p-5`}>
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/35">
              Countries Under Watch
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span
                className="text-4xl font-bold tabular-nums text-ink-100"
                style={{ textShadow: "0 2px 12px rgba(59,130,246,0.15)" }}
              >
                {countryCount || elevatedCount}
              </span>
              <span className="text-sm text-red-500">of {countryCount || 10} elevated</span>
            </div>
          </div>

          {/* Portfolio Risk */}
          <div className={`${glassStrong} p-5`}>
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/35">
              Portfolio Risk
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span
                className="text-4xl font-bold tabular-nums text-amber-500"
                style={{ textShadow: "0 2px 12px rgba(245,158,11,0.15)" }}
              >
                {portfolioRisk}
              </span>
              <span className="text-sm text-amber-500">{"\u25B2"} {portfolioRiskDelta} pts</span>
            </div>
            <div className="mt-3 h-1 overflow-hidden rounded-sm bg-white/[0.06]">
              <div
                className="h-full rounded-sm"
                style={{
                  width: `${portfolioRisk}%`,
                  background: "linear-gradient(90deg, #22c55e, #84cc16, #f59e0b, #ef4444)",
                }}
              />
            </div>
          </div>

          {/* Active Alerts */}
          <div className={`${glassStrong} p-5`}>
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/35">
              Active Alerts
            </div>
            <div className="mt-2 flex items-baseline gap-3">
              <span
                className="text-4xl font-bold tabular-nums text-red-500"
                style={{ textShadow: "0 2px 12px rgba(239,68,68,0.15)" }}
              >
                {activeAlertsCrit + activeAlertsWarn}
              </span>
              <div>
                <div className="text-xs text-white/50">
                  <span className="text-red-500">{"\u25CF"}</span> {activeAlertsCrit} Critical
                </div>
                <div className="text-xs text-white/50">
                  <span className="text-amber-500">{"\u25CF"}</span> {activeAlertsWarn} Warning
                </div>
              </div>
            </div>
          </div>

          {/* Staleness Index */}
          <div className={`${glassStrong} p-5`}>
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/35">
              Staleness Index
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span
                className="text-4xl font-bold tabular-nums text-green-500"
                style={{ textShadow: "0 2px 12px rgba(34,197,94,0.15)" }}
              >
                {stalenessIndex}%
              </span>
              <span className="text-sm text-green-500">Fresh</span>
            </div>
            <div className="mt-2 text-[11px] text-white/25">
              {staleIndicators} indicators stale &gt; 7d
            </div>
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
              {RISK_RANKING.map((c) => (
                <Link
                  key={c.iso3}
                  to={`/countries/${c.iso3}`}
                  className="flex items-center gap-3 border-b border-white/[0.03] px-4 py-2.5 transition-colors duration-150 last:border-b-0 hover:bg-white/[0.03]"
                  style={{ background: c.bgTint }}
                >
                  <span className="w-[18px] text-right text-xs text-white/25">{c.rank}</span>
                  <span className="text-base">{c.flag}</span>
                  <span className="flex-1 text-[13px] font-medium text-ink-200">{c.name}</span>
                  <div className="h-[5px] w-20 overflow-hidden rounded-sm bg-white/[0.06]">
                    <div
                      className="h-full rounded-sm"
                      style={{ width: `${c.barWidth}%`, background: c.gradient }}
                    />
                  </div>
                  <span className={`w-10 text-right text-[13px] font-semibold tabular-nums ${c.scoreClass}`}>
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
                      <th
                        key={h}
                        className="bg-white/[0.02] px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-white/25"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {RATING_ACTIONS.map((r) => (
                    <tr key={r.date + r.country} className="border-b border-white/[0.03]">
                      <td className="px-3 py-2 font-mono text-[11px] text-white/25">{r.date}</td>
                      <td className="px-3 py-2 text-[13px] text-ink-300">{r.country}</td>
                      <td className="px-3 py-2 text-[13px] text-ink-300">{r.agency}</td>
                      <td className="px-3 py-2">
                        <Badge label={r.action} type={r.actionType} />
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

            {/* Alerts */}
            {ALERTS.map((alert, i) => (
              <div
                key={i}
                className="flex items-start gap-3 border-b border-white/[0.03] px-4 py-3 transition-colors duration-150 hover:bg-white/[0.02]"
                style={BORDER_GLOW[alert.severity]}
              >
                <div
                  className="mt-[5px] h-2 w-2 flex-shrink-0 rounded-full"
                  style={DOT_STYLES[alert.severity]}
                />
                <div>
                  <div className="text-[13px] text-ink-300">
                    <Badge label={alert.severity === "crit" ? "Critical" : "Warning"} type={alert.severity} />
                    <span className="ml-1.5">{alert.text}</span>
                  </div>
                  <div className="mt-0.5 text-[11px] text-white/25">{alert.time}</div>
                </div>
              </div>
            ))}

            {/* Intelligence Feed divider */}
            <div className="border-b border-white/[0.04] border-t border-white/[0.04] bg-white/[0.015] px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-white/20">
              Intelligence Feed
            </div>

            {/* News items from API or fallback */}
            {(news && news.length > 0 ? news.slice(0, 4) : []).map((item) => {
              const badges: { label: string; type: string }[] = [];
              if (item.score) {
                const fiscal = impactToBadge(item.score.fiscal_impact);
                const ext = impactToBadge(item.score.external_impact);
                const fx = impactToBadge(item.score.fx_impact);
                const pol = impactToBadge(item.score.political_impact);
                if (fiscal) badges.push({ label: `Fiscal ${fiscal.label}`, type: fiscal.type });
                if (ext) badges.push({ label: `Ext ${ext.label}`, type: ext.type });
                if (fx) badges.push({ label: `FX ${fx.label}`, type: fx.type });
                if (pol) badges.push({ label: `Pol ${pol.label}`, type: pol.type });
              }
              return (
                <div
                  key={item.id}
                  className="border-b border-white/[0.03] px-4 py-3 transition-colors duration-150 hover:bg-white/[0.02]"
                >
                  <div className="text-[13px] font-medium text-ink-200">{item.title}</div>
                  <div className="mt-1 flex gap-1.5 text-[11px] text-white/25">
                    <span>{item.source}</span>
                    <span>{"\u2022"}</span>
                    <span>{timeAgo(item.published_at)}</span>
                  </div>
                  {badges.length > 0 && (
                    <div className="mt-1.5 flex gap-1">
                      {badges.map((b, j) => (
                        <Badge key={j} label={b.label} type={b.type} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Static fallback when no news loaded */}
            {(!news || news.length === 0) && (
              <>
                {/* TODO: replace with real API data */}
                <div className="border-b border-white/[0.03] px-4 py-3 hover:bg-white/[0.02]">
                  <div className="text-[13px] font-medium text-ink-200">
                    Ethiopia Birr Depreciates 2.8% This Week {"\u2014"} IMF Intervenes
                  </div>
                  <div className="mt-1 flex gap-1.5 text-[11px] text-white/25">
                    <span>Reuters</span><span>{"\u2022"}</span><span>2h ago</span>
                  </div>
                  <div className="mt-1.5 flex gap-1">
                    <Badge label="Fiscal H" type="crit" />
                    <Badge label="FX H" type="crit" />
                    <Badge label="Ext M" type="warn" />
                  </div>
                </div>
                <div className="border-b border-white/[0.03] px-4 py-3 hover:bg-white/[0.02]">
                  <div className="text-[13px] font-medium text-ink-200">
                    Kenya Revenue Authority Misses Q1 Target by KES 45Bn
                  </div>
                  <div className="mt-1 flex gap-1.5 text-[11px] text-white/25">
                    <span>Bloomberg</span><span>{"\u2022"}</span><span>4h ago</span>
                  </div>
                  <div className="mt-1.5 flex gap-1">
                    <Badge label="Fiscal H" type="crit" />
                    <Badge label="Pol L" type="info" />
                  </div>
                </div>
                <div className="px-4 py-3 hover:bg-white/[0.02]">
                  <div className="text-[13px] font-medium text-ink-200">
                    Morocco Signs {"\u20AC"}2.1B Green Bond {"\u2014"} Largest African Issuance
                  </div>
                  <div className="mt-1 flex gap-1.5 text-[11px] text-white/25">
                    <span>FT</span><span>{"\u2022"}</span><span>6h ago</span>
                  </div>
                  <div className="mt-1.5 flex gap-1">
                    <Badge label="Ext L" type="ok" />
                    <Badge label="Fiscal L" type="ok" />
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* ── Summary Intelligence Cards ── */}
        <div className="mt-5 grid grid-cols-3 gap-3">
          {SUMMARY_CARDS.map((card) => (
            <div key={card.title} className={`${glass} relative overflow-hidden p-4`}>
              {/* Glowing left border */}
              <div
                className="absolute bottom-0 left-0 top-0 w-[3px] rounded-l-[10px]"
                style={SUMMARY_BORDER[card.severity]}
              />
              <div className="text-[13px] font-semibold text-ink-100">{card.title}</div>
              <div className="mt-2 text-xs leading-relaxed text-white/45">{card.body}</div>
              <div className="mt-2.5 flex items-center gap-1.5 text-[10px] text-white/25">
                {card.badges.map((b, i) => (
                  <Badge key={i} label={b.label} type={b.type} />
                ))}
                <span>{"\u2022"} Synopsis updated {card.updated}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
