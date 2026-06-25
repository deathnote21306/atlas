import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

interface FxQuote {
  pair: string;
  value: number;
  change_pct: number;
}

interface FxTickerData {
  as_of: string;
  indicative: boolean;
  quotes: FxQuote[];
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }) + " " + d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export default function FxTicker() {
  const { data } = useQuery<FxTickerData>({
    queryKey: ["fx-ticker"],
    queryFn: () => api<FxTickerData>("/api/fx/ticker"),
    refetchInterval: 60_000,
    staleTime: 55_000,
  });

  if (!data || !data.quotes) return null;

  return (
    <div className="flex h-8 items-center border-b border-[#1e2b42] bg-[#0e1523] px-4 text-xs">
      <span className="mr-3 flex items-center gap-1 text-[10px] uppercase tracking-wider text-ink-500">
        FX Quotes
        <svg className="h-3 w-3" viewBox="0 0 12 12" fill="currentColor">
          <path d="M3 5l3-2.5L9 5M3 7l3 2.5L9 7" />
        </svg>
      </span>

      <div className="flex items-center gap-0 overflow-x-auto">
        {data.quotes.map((q, i) => (
          <div key={q.pair} className="flex items-center">
            {i > 0 && <div className="mx-3 h-3 w-px bg-[#2a3a52]" />}
            <span className="text-ink-500">{q.pair}</span>
            <span className="ml-1.5 font-medium tabular-nums text-ink-100">
              {q.value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span
              className={`ml-1.5 tabular-nums ${
                q.change_pct > 0
                  ? "text-positive"
                  : q.change_pct < 0
                    ? "text-danger"
                    : "text-ink-500"
              }`}
            >
              {q.change_pct >= 0 ? "+" : ""}
              {q.change_pct.toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-2 pl-4 text-[10px] text-ink-500">
        <span>{formatTimestamp(data.as_of)}</span>
        {data.indicative && (
          <span className="rounded bg-[#1e2b42] px-1.5 py-0.5">Indicative</span>
        )}
      </div>
    </div>
  );
}
