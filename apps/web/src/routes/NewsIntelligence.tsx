import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import AppShell from "./AppShell";
import { SkeletonLine } from "../components/Skeleton";

/* ------------------------------------------------------------------ */
/*  Types matching the API response from GET /api/news                */
/* ------------------------------------------------------------------ */

interface NewsScore {
  fiscal_impact: string;
  external_impact: string;
  fx_impact: string;
  political_impact: string;
  rationale: string;
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

/* ------------------------------------------------------------------ */
/*  Small presentational helpers                                      */
/* ------------------------------------------------------------------ */

const IMPACT_AXES = [
  { key: "fiscal_impact", label: "Fiscal" },
  { key: "external_impact", label: "External" },
  { key: "fx_impact", label: "FX" },
  { key: "political_impact", label: "Political" },
] as const;

function impactColor(level: string) {
  switch (level) {
    case "H":
      return "bg-red-500/[0.12] text-red-400 border border-red-500/[0.15]";
    case "M":
      return "bg-amber-500/[0.12] text-amber-400 border border-amber-500/[0.15]";
    default:
      return "bg-blue-500/[0.10] text-blue-400 border border-blue-500/[0.12]";
  }
}

function ImpactBadge({ label, level }: { label: string; level: string }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono leading-none ${impactColor(level)}`}
    >
      {label}: {level}
    </span>
  );
}

function ScorerBadge({ scorer }: { scorer: string }) {
  const isAI = scorer.startsWith("claude");
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] leading-none ${
        isAI
          ? "bg-blue-500/[0.12] text-blue-400 border border-blue-500/[0.15]"
          : "bg-white/[0.06] text-ink-400 border border-white/[0.08]"
      }`}
    >
      {isAI ? "AI" : "heuristic"}
    </span>
  );
}

function hasHighImpact(score: NewsScore): boolean {
  return (
    score.fiscal_impact === "H" ||
    score.external_impact === "H" ||
    score.fx_impact === "H" ||
    score.political_impact === "H"
  );
}

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/* ------------------------------------------------------------------ */
/*  Glass card wrapper                                                */
/* ------------------------------------------------------------------ */

function GlassCard({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`bg-white/[0.03] backdrop-blur-xl border border-white/[0.06] rounded-[10px] shadow-[0_4px_30px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.04)] ${className}`}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Single article card                                               */
/* ------------------------------------------------------------------ */

function ArticleCard({ article }: { article: NewsArticle }) {
  const [expanded, setExpanded] = useState(false);
  const [showRationale, setShowRationale] = useState(false);
  const score = article.score;

  return (
    <GlassCard className="p-4">
      {/* Headline row */}
      <div className="flex items-start justify-between gap-3">
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-semibold text-ink-100 hover:text-blue-400 transition-colors duration-150 leading-snug"
        >
          {article.title}
        </a>
        {score && <ScorerBadge scorer={score.scorer} />}
      </div>

      {/* Impact badges */}
      {score && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {IMPACT_AXES.map((axis) => (
            <ImpactBadge
              key={axis.key}
              label={axis.label}
              level={score[axis.key]}
            />
          ))}
        </div>
      )}

      {/* Source + timestamp + event type */}
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-ink-400">
        <span>{article.source}</span>
        {article.published_at && (
          <span>{relativeTime(article.published_at)}</span>
        )}
        {article.event_type && (
          <span className="rounded bg-white/[0.06] border border-white/[0.08] px-1.5 py-0.5 text-[10px]">
            {article.event_type}
          </span>
        )}
        {article.primary_iso3 && (
          <span className="rounded bg-white/[0.06] border border-white/[0.08] px-1.5 py-0.5 font-mono text-[10px]">
            {article.primary_iso3}
          </span>
        )}
      </div>

      {/* Body preview */}
      {article.body_text && (
        <div className="mt-2">
          <p
            className={`text-xs text-ink-300 leading-relaxed ${
              expanded ? "" : "line-clamp-3"
            }`}
          >
            {article.body_text}
          </p>
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1 text-[11px] text-blue-400 hover:text-blue-300 transition-colors duration-150"
          >
            {expanded ? "Show less" : "Read more"}
          </button>
        </div>
      )}

      {/* Scoring rationale toggle */}
      {score?.rationale && (
        <div className="mt-2">
          <button
            onClick={() => setShowRationale(!showRationale)}
            className="text-[11px] text-ink-400 hover:text-ink-300 transition-colors duration-150"
          >
            {showRationale ? "Hide scoring rationale" : "Show scoring rationale"}
          </button>
          {showRationale && (
            <p className="mt-1 rounded bg-white/[0.03] border border-white/[0.05] p-2 text-xs text-ink-300 leading-relaxed">
              {score.rationale}
            </p>
          )}
        </div>
      )}
    </GlassCard>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                              */
/* ------------------------------------------------------------------ */

export default function NewsIntelligence() {
  const [activeTab, setActiveTab] = useState<"feed" | "calendar">("feed");
  const [search, setSearch] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [eventFilter, setEventFilter] = useState("");

  const { data: articles, isLoading } = useQuery<NewsArticle[]>({
    queryKey: ["news-all"],
    queryFn: () => api<NewsArticle[]>("/api/news?limit=100"),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  /* Derived data */
  const countries = useMemo(() => {
    if (!articles) return [] as string[];
    const set = new Set<string>();
    articles.forEach((a) => {
      if (a.primary_iso3) set.add(a.primary_iso3);
    });
    return Array.from(set).sort();
  }, [articles]);

  const eventTypes = useMemo(() => {
    if (!articles) return [] as string[];
    const set = new Set<string>();
    articles.forEach((a) => {
      if (a.event_type) set.add(a.event_type);
    });
    return Array.from(set).sort();
  }, [articles]);

  const filtered = useMemo(() => {
    if (!articles) return [];
    return articles.filter((a) => {
      if (
        search &&
        !a.title.toLowerCase().includes(search.toLowerCase()) &&
        !(a.body_text ?? "").toLowerCase().includes(search.toLowerCase())
      ) {
        return false;
      }
      if (countryFilter && a.primary_iso3 !== countryFilter) return false;
      if (eventFilter && a.event_type !== eventFilter) return false;
      return true;
    });
  }, [articles, search, countryFilter, eventFilter]);

  /* KPI values */
  const totalArticles = filtered.length;
  const highImpactCount = filtered.filter(
    (a) => a.score && hasHighImpact(a.score)
  ).length;
  const countriesCovered = new Set(
    filtered.filter((a) => a.primary_iso3).map((a) => a.primary_iso3)
  ).size;

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-6">
        {/* Header */}
        <header className="mb-6">
          <h1 className="text-xl font-semibold text-ink-100">
            News &amp; Event Intelligence
          </h1>
        </header>

        {/* Tabs */}
        <div className="mb-6 flex gap-1">
          <button
            onClick={() => setActiveTab("feed")}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors duration-150 ${
              activeTab === "feed"
                ? "bg-blue-500/[0.15] text-blue-400 border border-blue-500/[0.2]"
                : "text-ink-400 hover:text-ink-200 hover:bg-white/[0.04]"
            }`}
          >
            Intelligence Feed
          </button>
          <button
            onClick={() => setActiveTab("calendar")}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors duration-150 ${
              activeTab === "calendar"
                ? "bg-blue-500/[0.15] text-blue-400 border border-blue-500/[0.2]"
                : "text-ink-400 hover:text-ink-200 hover:bg-white/[0.04]"
            }`}
          >
            Event Calendar
          </button>
        </div>

        {activeTab === "calendar" ? (
          /* Calendar placeholder */
          <GlassCard className="p-12 text-center">
            <p className="text-sm text-ink-400">Coming Soon</p>
            <p className="mt-1 text-xs text-ink-500">
              Event calendar with macro-critical dates, debt maturities, and
              political milestones.
            </p>
          </GlassCard>
        ) : (
          <>
            {/* KPI strip */}
            <div className="mb-6 grid grid-cols-3 gap-3">
              {[
                { label: "Total Articles", value: totalArticles },
                { label: "High Impact", value: highImpactCount },
                { label: "Countries Covered", value: countriesCovered },
              ].map((kpi) => (
                <GlassCard key={kpi.label} className="p-4">
                  <div className="text-xs text-ink-400 uppercase tracking-wide">
                    {kpi.label}
                  </div>
                  <div className="mt-1 font-mono text-2xl font-semibold text-ink-100 tabular-nums">
                    {isLoading ? (
                      <SkeletonLine className="h-7 w-12" />
                    ) : (
                      kpi.value
                    )}
                  </div>
                </GlassCard>
              ))}
            </div>

            {/* Search + filters */}
            <div className="mb-6 flex flex-wrap gap-3">
              <input
                type="text"
                placeholder="Search headlines..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 min-w-[200px] rounded-md bg-white/[0.04] border border-white/[0.08] px-3 py-2 text-sm text-ink-200 placeholder:text-ink-500 focus:outline-none focus:border-blue-500/[0.4] transition-colors duration-150"
              />
              <select
                value={countryFilter}
                onChange={(e) => setCountryFilter(e.target.value)}
                className="rounded-md bg-white/[0.04] border border-white/[0.08] px-3 py-2 text-sm text-ink-200 focus:outline-none focus:border-blue-500/[0.4] transition-colors duration-150"
              >
                <option value="">All Countries</option>
                {countries.map((iso3) => (
                  <option key={iso3} value={iso3}>
                    {iso3}
                  </option>
                ))}
              </select>
              <select
                value={eventFilter}
                onChange={(e) => setEventFilter(e.target.value)}
                className="rounded-md bg-white/[0.04] border border-white/[0.08] px-3 py-2 text-sm text-ink-200 focus:outline-none focus:border-blue-500/[0.4] transition-colors duration-150"
              >
                <option value="">All Event Types</option>
                {eventTypes.map((et) => (
                  <option key={et} value={et}>
                    {et}
                  </option>
                ))}
              </select>
            </div>

            {/* Articles list */}
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }, (_, i) => (
                  <GlassCard key={i} className="p-4 space-y-3">
                    <SkeletonLine className="h-4 w-3/4" />
                    <SkeletonLine className="h-3 w-full" />
                    <SkeletonLine className="h-3 w-1/2" />
                  </GlassCard>
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <GlassCard className="p-8 text-center">
                <p className="text-sm text-ink-400">No articles found</p>
                <p className="mt-1 text-xs text-ink-500">
                  {search || countryFilter || eventFilter
                    ? "Try adjusting your search or filters."
                    : "No news articles have been ingested yet."}
                </p>
              </GlassCard>
            ) : (
              <div className="space-y-3">
                {filtered.map((article) => (
                  <ArticleCard key={article.id} article={article} />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </AppShell>
  );
}
