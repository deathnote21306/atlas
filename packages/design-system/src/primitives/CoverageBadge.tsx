export type CoverageLevel = "full" | "standard" | "benchmark" | "coming_soon";

export interface CoverageBadgeProps {
  /** Raw value from the API. Typed as string on purpose: a legacy or hand-edited
   *  row must render a fallback rather than crash the page. */
  status: string;
}

const LABELS: Record<CoverageLevel, string> = {
  full: "Full Intelligence",
  standard: "Standard Intelligence",
  benchmark: "Benchmark Data",
  coming_soon: "Coming Soon",
};

const COLORS: Record<CoverageLevel, string> = {
  full: "bg-positive/15 text-positive",
  standard: "bg-amber-500/15 text-amber-400",
  benchmark: "bg-[#21262d] text-ink-300",
  // ink-400 (5.99:1 on #21262d), not ink-500 (3.15:1), which fails WCAG AA at
  // this 10px size. coming_soon is the default for every new country.
  coming_soon: "bg-[#21262d] text-ink-400",
};

const FALLBACK_LABEL = "Unknown";
const FALLBACK_COLOR = "bg-[#21262d] text-ink-400";

export function CoverageBadge({ status }: CoverageBadgeProps) {
  const known = status in LABELS ? (status as CoverageLevel) : null;
  const label = known ? LABELS[known] : FALLBACK_LABEL;
  const color = known ? COLORS[known] : FALLBACK_COLOR;
  return (
    <span
      title={label}
      className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${color}`}
    >
      {label}
    </span>
  );
}
