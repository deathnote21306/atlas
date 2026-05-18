import { AlertTriangle } from "lucide-react";

interface Input {
  key: string;
  value: any;
  source: string;
  provenance: string;
}

interface Dimension {
  key: string;
  label: string;
  score: number;
  weight: number;
  edge_case: boolean;
  description: string;
  sub_drivers: string[];
  warning: string | null;
  inputs: Input[];
  computed_at: string;
}

interface RiskDecomp {
  composite_score: number;
  composite_label: string;
  methodology_version: string;
  pod_override_active: boolean;
  pod_override_reason: string | null;
  dimensions: Dimension[];
}

interface RiskDecompositionTabProps {
  data: RiskDecomp | null;
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-red-500";
  if (score >= 60) return "text-orange-500";
  if (score >= 30) return "text-amber-500";
  return "text-green-500";
}

function barColor(score: number): string {
  if (score >= 80) return "bg-red-500";
  if (score >= 60) return "bg-orange-500";
  if (score >= 30) return "bg-amber-500";
  return "bg-green-500";
}

function compositeColor(score: number): string {
  if (score >= 80) return "text-red-500";
  if (score >= 60) return "text-orange-500";
  if (score >= 30) return "text-amber-500";
  return "text-green-500";
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3600_000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function RiskDecompositionTab({ data }: RiskDecompositionTabProps) {
  if (!data) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-[#161b22] py-16">
        <p className="text-sm text-ink-500">Risk decomposition not yet computed for this country</p>
      </div>
    );
  }

  const sorted = [...data.dimensions].sort((a, b) => b.weight - a.weight);

  return (
    <div className="space-y-4">
      {/* Methodology header */}
      <div className="rounded-lg bg-[#161b22] p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">ATLAS Composite Risk Score</p>
            <div className="mt-2 flex items-baseline gap-3">
              <span className={`text-5xl font-bold tabular-nums ${compositeColor(data.composite_score)}`}>
                {data.composite_score}
              </span>
              <span className={`text-lg font-semibold ${compositeColor(data.composite_score)}`}>
                {data.composite_label}
              </span>
            </div>
            <p className="mt-1 text-xs text-ink-500">Composite of {data.dimensions.length} dimensions</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">
              Deterministic model {data.methodology_version} &middot; Weighted average
            </p>
            <p className="mt-2 text-[10px] uppercase tracking-[0.14em] text-ink-500">Scoring Logic</p>
            <p className="mt-0.5 font-mono text-xs text-amber-500/70">
              Score = &Sigma;(dim_score &times; weight) / &Sigma;(weights)
            </p>
            {data.pod_override_active && data.pod_override_reason && (
              <p className="mt-2 text-[11px] text-amber-500/70">
                PoD override active &mdash; {data.pod_override_reason}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Dimension cards */}
      {sorted.map((dim) => {
        const realCount = dim.inputs.filter((i) => i.provenance === "real").length;
        const seededCount = dim.inputs.filter((i) => i.provenance === "seeded").length;
        const computedCount = dim.inputs.filter((i) => i.provenance === "computed").length;
        const hasSeeded = seededCount > 0 || dim.inputs.some((i) => i.provenance === "missing");

        return (
          <div key={dim.key} className="rounded-lg bg-[#161b22] p-6">
            {/* Header row */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold text-ink-100">{dim.label} Risk</h3>
                <span className="text-[11px] text-ink-500">weight: {dim.weight}%</span>
                {dim.edge_case && (
                  <span className="rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-500">
                    Edge Case
                  </span>
                )}
              </div>
              <span className={`text-2xl font-semibold tabular-nums ${scoreColor(dim.score)}`}>
                {dim.score}
              </span>
            </div>

            {/* Divider */}
            <div className="my-3 border-t border-[#21262d]" />

            {/* Progress bar */}
            <div className="h-1.5 rounded-full bg-[#21262d]">
              <div
                className={`h-full rounded-full ${barColor(dim.score)} transition-all duration-500`}
                style={{ width: `${dim.score}%` }}
              />
            </div>

            {/* Description */}
            {dim.description && (
              <p className="mt-3 max-w-prose text-sm leading-relaxed text-ink-300">{dim.description}</p>
            )}

            {/* Sub-driver pills */}
            {dim.sub_drivers.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {dim.sub_drivers.map((sd) => (
                  <span
                    key={sd}
                    className="rounded-md border border-[#21262d] bg-[#21262d] px-2.5 py-1 text-xs text-ink-300"
                  >
                    {sd}
                  </span>
                ))}
              </div>
            )}

            {/* Warning banner */}
            {dim.warning && (
              <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-500/90">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                <span>{dim.warning}</span>
              </div>
            )}

            {/* Provenance footer */}
            <div className="mt-4 border-t border-[#21262d] pt-3">
              <span className={`text-[11px] ${hasSeeded ? "text-amber-500/70" : "text-ink-500"}`}>
                Inputs: {realCount} real{seededCount > 0 ? `, ${seededCount} seeded` : ""}
                {computedCount > 0 ? `, ${computedCount} computed` : ""}
                {" "}&middot; Recomputed {relativeTime(dim.computed_at)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
