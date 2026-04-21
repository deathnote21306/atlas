import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { SkeletonCard } from "../../components/Skeleton";

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
  score: any;
}

interface EventsTabProps {
  iso3: string;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  IMF: "IMF REVIEW",
  Rating: "RATING ACTION",
  Monetary: "MONETARY",
  Fiscal: "FISCAL",
  Political: "POLITICAL",
  External: "EXTERNAL",
  Market: "MARKET",
};

function typePillColor(_type: string): string {
  return "bg-amber-500/10 text-amber-500 border-amber-500/30";
}

function parseDate(iso: string | null): { month: string; day: string; year: string } | null {
  if (!iso) return null;
  const d = new Date(iso);
  return {
    month: d.toLocaleDateString("en-US", { month: "short" }).toUpperCase(),
    day: String(d.getDate()),
    year: String(d.getFullYear()),
  };
}

export default function EventsTab({ iso3 }: EventsTabProps) {
  const [range, setRange] = useState<"upcoming" | "past_30d" | "all">("all");

  const { data: articles, isLoading, error } = useQuery<NewsArticle[]>({
    queryKey: ["country-events", iso3],
    queryFn: () => api<NewsArticle[]>(`/api/news?iso3=${iso3}&limit=100`),
    staleTime: 5 * 60_000,
  });

  const events = (articles ?? []).filter((a) => a.event_type != null && a.event_type !== "Market");

  const filtered = events.filter((a) => {
    if (range === "all") return true;
    if (!a.published_at) return true;
    const daysAgo = (Date.now() - new Date(a.published_at).getTime()) / 86400_000;
    if (range === "upcoming") return daysAgo <= 0;
    if (range === "past_30d") return daysAgo <= 30;
    return true;
  });

  const displayEvents = range === "upcoming" && filtered.length === 0 ? events.slice(0, 10) : filtered;

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
        <p className="text-ink-400">Unable to load events — try again</p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs text-ink-500">
          EVENTS CALENDAR &middot; {displayEvents.length} events
        </span>
        <div className="flex gap-2">
          {(["upcoming", "past_30d", "all"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`rounded px-2 py-1 text-xs ${
                range === r ? "bg-amber-500/10 text-amber-500" : "text-ink-500 hover:text-ink-300"
              }`}
            >
              {r === "upcoming" ? "Upcoming" : r === "past_30d" ? "Past 30d" : "All"}
            </button>
          ))}
        </div>
      </div>

      {/* Empty state */}
      {displayEvents.length === 0 && (
        <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-8 text-center">
          <p className="text-ink-400">No events for this country.</p>
          {range !== "all" && (
            <button
              onClick={() => setRange("all")}
              className="mt-2 text-sm text-amber-500 hover:text-amber-400"
            >
              Show all events
            </button>
          )}
        </div>
      )}

      {/* Event cards */}
      <div className="space-y-3">
        {displayEvents.map((event) => {
          const date = parseDate(event.published_at);
          return (
            <div
              key={event.id}
              className="flex gap-4 rounded-lg border border-white/[0.06] bg-white/[0.03] p-5"
            >
              {/* Date block */}
              {date && (
                <div className="flex w-14 shrink-0 flex-col items-center">
                  <span className="text-xs font-bold text-amber-500">{date.month}</span>
                  <span className="text-2xl font-semibold text-ink-100">{date.day}</span>
                  <span className="text-[11px] text-ink-500">{date.year}</span>
                </div>
              )}

              <div className="flex-1">
                <div className="flex items-center gap-2">
                  {event.event_type && (
                    <span
                      className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider ${typePillColor(event.event_type)}`}
                    >
                      {EVENT_TYPE_LABELS[event.event_type] ?? event.event_type}
                    </span>
                  )}
                </div>
                <h4 className="mt-1.5 text-[15px] font-semibold text-ink-100">{event.title}</h4>
                {event.body_text && (
                  <p className="mt-1.5 line-clamp-3 text-[13px] text-ink-400">{event.body_text}</p>
                )}
                <p className="mt-2 text-[11px] text-ink-500">{event.source}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
