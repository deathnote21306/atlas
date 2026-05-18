import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import AppShell from "./AppShell";

const C = "rounded-lg bg-[#161b22]";

/* ── Types ── */

interface NewsScore {
  fiscal_impact: string;
  external_impact: string;
  fx_impact: string;
  political_impact: string;
  rationale: any;
  scorer: string;
  scored_at: string;
}

interface NewsArticle {
  id: string;
  url: string;
  title: string;
  source: string;
  published_at: string | null;
  body_text: string | null;
  primary_iso3: string | null;
  event_type: string | null;
  ingested_at: string;
  score?: NewsScore;
}

/* ── Helpers ── */

const AXES = [
  { key: "fiscal_impact" as const, label: "Fiscal" },
  { key: "external_impact" as const, label: "External" },
  { key: "fx_impact" as const, label: "FX" },
  { key: "political_impact" as const, label: "Political" },
];

function impactBadge(level: string) {
  if (level === "H") return "bg-red-500/15 text-red-400";
  if (level === "M") return "bg-amber-500/15 text-amber-400";
  return "bg-blue-500/10 text-blue-400";
}

function hasHighImpact(s: NewsScore) {
  return s.fiscal_impact === "H" || s.external_impact === "H" || s.fx_impact === "H" || s.political_impact === "H";
}

function relTime(d: string) {
  const ms = Date.now() - new Date(d).getTime();
  const m = Math.floor(ms / 60_000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function overallScore(s: NewsScore): number {
  const map: Record<string, number> = { H: 80, M: 50, L: 20 };
  return Math.max(map[s.fiscal_impact] ?? 20, map[s.external_impact] ?? 20, map[s.fx_impact] ?? 20, map[s.political_impact] ?? 20);
}

function scoreColor(v: number) {
  if (v >= 75) return "text-red-500";
  if (v >= 60) return "text-orange-500";
  if (v >= 40) return "text-amber-500";
  return "text-green-500";
}

function dotColor(v: number) {
  if (v >= 75) return "bg-red-500";
  if (v >= 60) return "bg-orange-500";
  if (v >= 40) return "bg-amber-500";
  return "bg-green-500";
}

/* ── Article Card ── */

function ArticleCard({ article }: { article: NewsArticle }) {
  const [expanded, setExpanded] = useState(false);
  const [showRationale, setShowRationale] = useState(false);
  const score = article.score;
  const overall = score ? overallScore(score) : 0;

  return (
    <div className={`${C} p-4`}>
      <div className="flex items-start gap-3">
        {score && <span className={`mt-1 h-2.5 w-2.5 flex-shrink-0 rounded-full ${dotColor(overall)}`} />}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <a href={article.url} target="_blank" rel="noopener noreferrer" className="text-[13px] font-semibold text-ink-100 hover:text-blue-400 leading-snug">
              {article.title}
            </a>
            {score && (
              <span className={`flex-shrink-0 text-[14px] font-bold tabular-nums ${scoreColor(overall)}`}>{overall}</span>
            )}
          </div>

          {score && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {AXES.map((a) => (
                <span key={a.key} className={`rounded px-1.5 py-0.5 text-[10px] font-mono ${impactBadge(score[a.key])}`}>
                  {a.label}: {score[a.key]}
                </span>
              ))}
              <span className={`rounded px-1.5 py-0.5 text-[10px] ${score.scorer.startsWith("claude") ? "bg-blue-500/10 text-blue-400" : "bg-[#21262d] text-ink-400"}`}>
                {score.scorer.startsWith("claude") ? "AI" : "heuristic"}
              </span>
            </div>
          )}

          <div className="mt-2 flex items-center gap-2 text-[11px] text-ink-500">
            <span>{article.source}</span>
            {article.published_at && <span>· {relTime(article.published_at)}</span>}
            {article.primary_iso3 && <span className="rounded bg-[#21262d] px-1.5 py-0.5 text-[10px] font-mono">{article.primary_iso3}</span>}
            {article.event_type && <span className="rounded bg-[#21262d] px-1.5 py-0.5 text-[10px]">{article.event_type}</span>}
          </div>

          {article.body_text && (
            <div className="mt-2">
              <p className={`text-[12px] text-ink-400 leading-relaxed ${expanded ? "" : "line-clamp-3"}`}>{article.body_text}</p>
              <button onClick={() => setExpanded(!expanded)} className="mt-1 text-[11px] text-blue-400 hover:text-blue-300">
                {expanded ? "Show less" : "Show more"}
              </button>
            </div>
          )}

          {score?.rationale && (
            <div className="mt-1">
              {showRationale ? (
                <>
                  <p className="rounded bg-[#0d1117] p-2 text-[11px] text-ink-400 leading-relaxed">
                    {typeof score.rationale === "string" ? score.rationale : Object.entries(score.rationale).map(([k, v]) => `${k}: ${v}`).join(". ")}
                  </p>
                  <button onClick={() => setShowRationale(false)} className="mt-1 text-[11px] text-ink-500 hover:text-ink-400">
                    Hide rationale
                  </button>
                </>
              ) : (
                <button onClick={() => setShowRationale(true)} className="text-[11px] text-ink-500 hover:text-ink-400">
                  Show scoring rationale
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Page ── */

export default function NewsIntelligence() {
  const [tab, setTab] = useState<"feed" | "calendar">("feed");
  const [search, setSearch] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [eventFilter, setEventFilter] = useState("");

  const { data: articles, isLoading } = useQuery<NewsArticle[]>({
    queryKey: ["news-all"],
    queryFn: () => api<NewsArticle[]>("/api/news?limit=100"),
    staleTime: 5 * 60_000,
    retry: false,
  });

  const countries = useMemo(() => {
    if (!articles) return [];
    return Array.from(new Set(articles.filter((a) => a.primary_iso3).map((a) => a.primary_iso3!))).sort();
  }, [articles]);

  const eventTypes = useMemo(() => {
    if (!articles) return [];
    return Array.from(new Set(articles.filter((a) => a.event_type).map((a) => a.event_type!))).sort();
  }, [articles]);

  const filtered = useMemo(() => {
    if (!articles) return [];
    return articles.filter((a) => {
      if (search && !a.title.toLowerCase().includes(search.toLowerCase()) && !(a.body_text ?? "").toLowerCase().includes(search.toLowerCase())) return false;
      if (countryFilter && a.primary_iso3 !== countryFilter) return false;
      if (eventFilter && a.event_type !== eventFilter) return false;
      return true;
    });
  }, [articles, search, countryFilter, eventFilter]);

  const total = filtered.length;
  const highImpact = filtered.filter((a) => a.score && hasHighImpact(a.score)).length;
  const coverageCount = new Set(filtered.filter((a) => a.primary_iso3).map((a) => a.primary_iso3)).size;

  return (
    <AppShell>
      <div className="mx-auto max-w-[1440px] px-6 pb-10">

        {/* Header */}
        <div className="pb-5 pt-4">
          <h1 className="text-[18px] font-semibold text-ink-100">News &amp; Event Intelligence</h1>
        </div>

        {/* Tabs */}
        <div className="mb-4 flex gap-1">
          {(["feed", "calendar"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`rounded-md px-4 py-2 text-sm font-medium ${tab === t ? "bg-blue-500/15 text-blue-400" : "text-ink-500 hover:bg-[#161b22] hover:text-ink-300"}`}>
              {t === "feed" ? "Intelligence Feed" : "Event Calendar"}
            </button>
          ))}
        </div>

        {tab === "calendar" ? (
          <div className={`${C} p-12 text-center`}>
            <p className="text-sm text-ink-400">Coming Soon</p>
            <p className="mt-1 text-[11px] text-ink-500">Event calendar with macro-critical dates, debt maturities, and political milestones.</p>
          </div>
        ) : (
          <>
            {/* KPI strip */}
            <div className="mb-4 grid grid-cols-3 gap-3">
              {[
                { label: "Total Articles", value: total },
                { label: "High Impact", value: highImpact },
                { label: "Countries Covered", value: coverageCount },
              ].map((kpi) => (
                <div key={kpi.label} className={`${C} px-5 py-4`}>
                  <div className="text-[11px] text-ink-500 uppercase tracking-wider">{kpi.label}</div>
                  <div className="mt-1 text-[28px] font-bold tabular-nums text-ink-100">{isLoading ? "—" : kpi.value}</div>
                </div>
              ))}
            </div>

            {/* Search + filters */}
            <div className="mb-4 flex gap-3">
              <input
                type="text"
                placeholder="Search headlines..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-ink-200 placeholder:text-ink-500 focus:border-blue-500/40 focus:outline-none"
              />
              <select value={countryFilter} onChange={(e) => setCountryFilter(e.target.value)} className="rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-ink-200 focus:outline-none">
                <option value="">All Countries</option>
                {countries.map((iso) => <option key={iso} value={iso}>{iso}</option>)}
              </select>
              <select value={eventFilter} onChange={(e) => setEventFilter(e.target.value)} className="rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-ink-200 focus:outline-none">
                <option value="">All Event Types</option>
                {eventTypes.map((et) => <option key={et} value={et}>{et}</option>)}
              </select>
            </div>

            {/* Articles */}
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }, (_, i) => (
                  <div key={i} className={`${C} p-4`}>
                    <div className="h-4 w-3/4 animate-pulse rounded bg-[#21262d]" />
                    <div className="mt-2 h-3 w-full animate-pulse rounded bg-[#21262d]" />
                    <div className="mt-2 h-3 w-1/2 animate-pulse rounded bg-[#21262d]" />
                  </div>
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <div className={`${C} p-8 text-center`}>
                <p className="text-sm text-ink-400">No articles found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filtered.map((a) => <ArticleCard key={a.id} article={a} />)}
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
