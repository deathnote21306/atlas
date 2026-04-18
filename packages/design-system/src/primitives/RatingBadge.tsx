export interface RatingBadgeProps {
  agency: "S&P" | "Moodys" | "Fitch";
  rating: string;
  outlook?: string | null;
}

const DISTRESSED = new Set(["SD", "D", "DD", "DDD", "RD", "C", "Ca"]);

function gradeClass(rating: string): string {
  if (DISTRESSED.has(rating)) return "bg-danger/15 text-danger border-danger/30";
  const first = rating.charAt(0).toUpperCase();
  if (first === "A") return "bg-positive/15 text-positive border-positive/30";
  if (first === "B" && !rating.startsWith("BB")) return "bg-white/[0.04] text-ink-300 border-white/[0.06]";
  if (first === "B") return "bg-warning/15 text-warning border-warning/30";
  if (first === "C") return "bg-danger/15 text-danger border-danger/30";
  return "bg-white/[0.04] text-ink-300 border-white/[0.06]";
}

export function RatingBadge({ agency, rating, outlook }: RatingBadgeProps) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs ${gradeClass(rating)}`}>
      <span className="text-ink-400">{agency}</span>
      <span className="font-mono font-semibold">{rating}</span>
      {outlook ? <span className="text-ink-400 text-[10px]">· {outlook}</span> : null}
    </span>
  );
}
