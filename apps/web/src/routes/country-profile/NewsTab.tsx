import { useState, useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { X, ExternalLink, Info } from "lucide-react";
import { api } from "../../api/client";
import { SkeletonCard } from "../../components/Skeleton";

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
  body_text: string;
  primary_iso3: string | null;
  event_type: string | null;
  ingested_at: string;
  score: NewsScore | null;
}

interface NewsTabProps {
  iso3: string;
}

function impactToNum(level: string): number {
  if (level === "H") return 80;
  if (level === "M") return 50;
  return 20;
}

function overallImpact(score: NewsScore): number {
  return Math.max(
    impactToNum(score.fiscal_impact),
    impactToNum(score.external_impact),
    impactToNum(score.fx_impact),
    impactToNum(score.political_impact),
  );
}

function impactBadgeColor(score: number): string {
  if (score >= 80) return "bg-red-500/20 text-red-400 border-red-500/30";
  if (score >= 60) return "bg-orange-500/20 text-orange-400 border-orange-500/30";
  if (score >= 40) return "bg-amber-500/20 text-amber-400 border-amber-500/30";
  return "bg-white/[0.04] text-ink-400 border-white/[0.06]";
}

function axisColor(level: string): string {
  if (level === "H") return "text-danger font-semibold";
  if (level === "M") return "text-amber-400";
  return "text-ink-500";
}

function relativeDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const days = Math.floor(diff / 86400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function formatRationale(rationale: any): string {
  if (!rationale) return "";
  if (typeof rationale === "string") return rationale;
  if (typeof rationale === "object") {
    return Object.entries(rationale)
      .map(([k, v]) => `${k}: ${v}`)
      .join(". ");
  }
  return String(rationale);
}

export default function NewsTab({ iso3 }: NewsTabProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [dateRange, setDateRange] = useState<"7d" | "30d" | "90d" | "all">("90d");
  const selectedArticleId = searchParams.get("article");

  const { data: articles, isLoading, error } = useQuery<NewsArticle[]>({
    queryKey: ["country-news", iso3],
    queryFn: () => api<NewsArticle[]>(`/api/news?iso3=${iso3}&limit=100`),
    staleTime: 5 * 60_000,
  });

  const filtered = (articles ?? []).filter((a) => {
    if (dateRange === "all") return true;
    if (!a.published_at) return true;
    const daysAgo = (Date.now() - new Date(a.published_at).getTime()) / 86400_000;
    const limit = dateRange === "7d" ? 7 : dateRange === "30d" ? 30 : 90;
    return daysAgo <= limit;
  });

  const selectedArticle = selectedArticleId
    ? (articles ?? []).find((a) => a.id === selectedArticleId) ?? null
    : null;

  const openArticle = useCallback(
    (id: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("article", id);
        return next;
      });
    },
    [setSearchParams],
  );

  const closePanel = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("article");
      return next;
    });
  }, [setSearchParams]);

  useEffect(() => {
    function handleEsc(e: KeyboardEvent) {
      if (e.key === "Escape") closePanel();
    }
    if (selectedArticle) {
      document.addEventListener("keydown", handleEsc);
      return () => document.removeEventListener("keydown", handleEsc);
    }
  }, [selectedArticle, closePanel]);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }, (_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-8 text-center">
        <p className="text-ink-400">Unable to load news — try again</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs text-ink-500">
          NEWS FEED &middot; {filtered.length} articles &mdash; last {dateRange === "all" ? "all time" : dateRange}
        </span>
        <div className="flex gap-2">
          {(["7d", "30d", "90d", "all"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setDateRange(r)}
              className={`rounded px-2 py-1 text-xs ${
                dateRange === r
                  ? "bg-amber-500/10 text-amber-500"
                  : "text-ink-500 hover:text-ink-300"
              }`}
            >
              {r === "all" ? "All time" : r}
            </button>
          ))}
        </div>
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-8 text-center">
          <p className="text-ink-400">No news articles for this country in the selected time range.</p>
          {dateRange !== "all" && (
            <button
              onClick={() => setDateRange("all")}
              className="mt-2 text-sm text-amber-500 hover:text-amber-400"
            >
              Try &ldquo;All time&rdquo;
            </button>
          )}
        </div>
      )}

      {/* Article list */}
      <div className="space-y-3">
        {filtered.map((article) => {
          const impact = article.score ? overallImpact(article.score) : 0;
          return (
            <button
              key={article.id}
              type="button"
              onClick={() => openArticle(article.id)}
              className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] p-5 text-left transition-colors hover:bg-white/[0.05]"
            >
              <div className="flex gap-4">
                {/* Impact badge */}
                {article.score && (
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded border text-base font-bold tabular-nums ${impactBadgeColor(impact)}`}
                  >
                    {impact}
                  </div>
                )}
                <div className="flex-1 overflow-hidden">
                  <h4 className="text-base font-semibold text-ink-100">{article.title}</h4>
                  <p className="mt-0.5 text-xs text-ink-500">
                    {article.source} &middot; {relativeDate(article.published_at)}
                  </p>
                  {article.body_text && (
                    <p className="mt-2 line-clamp-3 text-[13px] text-ink-400">{article.body_text}</p>
                  )}

                  {/* 4-axis scores */}
                  {article.score && (
                    <div className="mt-3 grid grid-cols-4 gap-2">
                      {(
                        [
                          ["Fiscal", article.score.fiscal_impact],
                          ["External", article.score.external_impact],
                          ["FX", article.score.fx_impact],
                          ["Political", article.score.political_impact],
                        ] as const
                      ).map(([label, level]) => (
                        <div
                          key={label}
                          className="rounded-md border border-white/[0.06] bg-white/[0.02] px-2 py-1.5 text-center"
                        >
                          <div className="text-[10px] uppercase tracking-wider text-ink-500">{label}</div>
                          <div className={`mt-0.5 tabular-nums text-base ${axisColor(level)}`}>
                            {impactToNum(level)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Tags + AI mark */}
                  <div className="mt-3 flex items-center justify-between">
                    <div className="flex flex-wrap gap-1">
                      {article.event_type && (
                        <span className="rounded bg-white/[0.04] px-2 py-0.5 text-xs text-ink-400">
                          {article.event_type}
                        </span>
                      )}
                    </div>
                    {article.score && (
                      <span className="flex items-center gap-1 text-[11px] text-ink-500">
                        {article.score.scorer === "heuristic" ? "Heuristic" : "AI-scored"}{" "}
                        <Info className="h-3 w-3" />
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Side panel */}
      {selectedArticle && (
        <>
          <div className="fixed inset-0 z-50 bg-black/40" onClick={closePanel} />
          <div className="fixed bottom-0 right-0 top-0 z-50 w-[500px] overflow-y-auto border-l border-white/[0.06] bg-ink-900 p-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-ink-100">{selectedArticle.title}</h3>
              <button onClick={closePanel} className="rounded p-1 text-ink-500 hover:text-ink-200">
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="mt-2 text-sm text-ink-500">
              {selectedArticle.source} &middot; {formatDate(selectedArticle.published_at)}
            </p>

            {selectedArticle.body_text && (
              <p className="mt-4 text-sm leading-relaxed text-ink-300">{selectedArticle.body_text}</p>
            )}

            {/* 4-axis scores expanded */}
            {selectedArticle.score && (
              <div className="mt-6">
                <h4 className="mb-3 text-sm font-semibold text-ink-300">Impact Assessment</h4>
                <div className="grid grid-cols-2 gap-3">
                  {(
                    [
                      ["Fiscal", selectedArticle.score.fiscal_impact],
                      ["External", selectedArticle.score.external_impact],
                      ["FX", selectedArticle.score.fx_impact],
                      ["Political", selectedArticle.score.political_impact],
                    ] as const
                  ).map(([label, level]) => (
                    <div key={label} className="rounded-md border border-white/[0.06] bg-white/[0.03] p-3 text-center">
                      <div className="text-[10px] uppercase tracking-wider text-ink-500">{label}</div>
                      <div className={`mt-1 text-xl font-bold tabular-nums ${axisColor(level)}`}>
                        {impactToNum(level)}
                      </div>
                    </div>
                  ))}
                </div>

                {selectedArticle.score.rationale && (
                  <div className="mt-3">
                    <h4 className="mb-1 text-xs font-medium text-ink-400">Scoring Rationale</h4>
                    <p className="text-sm text-ink-400">
                      {formatRationale(selectedArticle.score.rationale)}
                    </p>
                  </div>
                )}
              </div>
            )}

            <a
              href={selectedArticle.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-6 flex items-center gap-2 text-sm text-amber-500 hover:text-amber-400"
            >
              Open original article <ExternalLink className="h-3.5 w-3.5" />
            </a>

            {/* Lineage */}
            {selectedArticle.score && (
              <p className={`mt-6 border-t border-white/[0.06] pt-3 text-[11px] ${
                selectedArticle.score.scorer === "heuristic" ? "text-ink-600" : "text-ink-500"
              }`}>
                {selectedArticle.score.scorer === "heuristic"
                  ? `Scored heuristically \u00b7 ${formatDate(selectedArticle.score.scored_at)}`
                  : `Scored by ${selectedArticle.score.scorer} \u00b7 ${formatDate(selectedArticle.score.scored_at)}`}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
