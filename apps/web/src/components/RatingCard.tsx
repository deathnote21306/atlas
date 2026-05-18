import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface RatingHistoryItem {
  iso3: string;
  agency: string;
  rating: string;
  outlook: string | null;
  action: string;
  action_date: string;
  source_url: string | null;
}

interface RatingCardProps {
  agency: string;
  grade: string;
  outlook: string | null;
  action: string;
  date: string;
  status: string;
  history: RatingHistoryItem[];
}

function gradeColor(grade: string): string {
  const g = grade.toUpperCase().replace(/[+-]/g, "");
  if (g === "AAA" || g === "AA") return "text-positive";
  if (g === "A" || g === "BBB" || g === "BAA") return "text-atlas-400";
  if (g === "BB" || g === "BA" || g === "B" || g === "BA2" || g === "B1") return "text-warning";
  if (["CCC", "CC", "C", "CAA", "CAA1", "CAA3", "CA"].includes(g)) return "text-danger";
  if (["D", "RD", "SD"].includes(g)) return "text-red-700";
  if (g === "NR") return "text-ink-500";
  return "text-ink-300";
}

function statusPillColor(status: string): string {
  switch (status.toUpperCase()) {
    case "DISTRESSED":
      return "bg-red-500/10 text-red-500 border-red-500/30";
    case "UNDER_REVIEW":
      return "bg-amber-500/10 text-amber-500 border-amber-500/30";
    case "STABLE":
      return "bg-green-500/10 text-green-500 border-green-500/30";
    case "POSITIVE":
      return "bg-blue-500/10 text-blue-500 border-blue-500/30";
    case "NEGATIVE":
      return "bg-orange-500/10 text-orange-500 border-orange-500/30";
    default:
      return "bg-ink-700/50 text-ink-400 border-ink-600/30";
  }
}

function formatAgency(agency: string): string {
  if (agency === "Moodys") return "MOODY'S";
  if (agency === "S&P") return "S&P";
  if (agency === "Fitch") return "FITCH";
  return agency.toUpperCase();
}

export default function RatingCard({
  agency,
  grade,
  outlook,
  action,
  date,
  status,
  history,
}: RatingCardProps) {
  const [showHistory, setShowHistory] = useState(false);

  return (
    <div className="rounded-lg border border-[#21262d] bg-[#161b22] p-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-400">
          {formatAgency(agency)}
        </span>
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase ${statusPillColor(status)}`}
        >
          {status.replace(/_/g, " ")}
        </span>
      </div>

      <div className="mt-3">
        <span className={`text-3xl font-bold ${gradeColor(grade)}`}>{grade}</span>
        {outlook && (
          <span className="ml-2 text-sm text-ink-400">{outlook}</span>
        )}
      </div>
      <div className="mt-1 text-xs text-ink-500">{action}</div>

      <div className="mt-3 text-[10px] text-ink-500">{date}</div>

      <button
        type="button"
        onClick={() => setShowHistory(!showHistory)}
        className="mt-2 flex items-center gap-1 text-xs text-ink-400 hover:text-ink-200"
      >
        History
        {showHistory ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {showHistory && history.length > 0 && (
        <div className="mt-2 space-y-1 border-t border-[#21262d] pt-2">
          {history.map((h, i) => (
            <div key={`${h.action_date}-${i}`} className="flex items-center justify-between text-[10px]">
              <span className="text-ink-500">{h.action_date}</span>
              <span className={`font-mono ${gradeColor(h.rating)}`}>{h.rating}</span>
              <span className="text-ink-500">{h.action}</span>
            </div>
          ))}
        </div>
      )}
      {showHistory && history.length === 0 && (
        <p className="mt-2 text-[10px] text-ink-500">No historical data available</p>
      )}
    </div>
  );
}
