export interface RiskGaugeProps {
  label: string;
  score: number;
  rationale: string;
  isEstimate?: boolean;
}

function barClass(score: number): string {
  if (score <= 2) return "bg-positive";
  if (score <= 4) return "bg-positive/60";
  if (score <= 6) return "bg-warning/80";
  if (score <= 8) return "bg-warning";
  return "bg-danger";
}

export function RiskGauge({ label, score, rationale, isEstimate = false }: RiskGaugeProps) {
  const pct = Math.max(0, Math.min(100, (score / 10) * 100));
  return (
    <div className="rounded-md border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-ink-300">{label}</span>
        <span className="font-mono text-sm text-ink-100">{score}/10</span>
      </div>
      <div className="mt-2 h-1.5 w-full rounded-full bg-white/[0.04]">
        <div className={`h-1.5 rounded-full ${barClass(score)}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-1.5 text-[10px] text-ink-400">
        {rationale}
        {isEstimate && <span className="ml-1 italic">(estimate)</span>}
      </div>
    </div>
  );
}
