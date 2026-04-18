export type StalenessState = "missing" | "fresh" | "yellow" | "red";

export interface StalenessChipProps {
  state: StalenessState;
  ageDays: number | null;
}

function formatAge(days: number | null): string {
  if (days === null) return "—";
  if (days <= 90) return `${days}d old`;
  if (days <= 365) return `~${Math.round(days / 30)} months`;
  return `~${Math.round(days / 365)} years`;
}

const PALETTE: Record<StalenessState, string> = {
  missing: "bg-white/[0.04] text-ink-400",
  fresh: "bg-positive/10 text-positive",
  yellow: "bg-warning/10 text-warning",
  red: "bg-danger/10 text-danger",
};

export function StalenessChip({ state, ageDays }: StalenessChipProps) {
  const label = state === "missing" ? "—" : state;
  const age = state === "missing" ? "—" : formatAge(ageDays);
  return (
    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${PALETTE[state]}`}>
      {label !== "—" && <span className="uppercase tracking-wide">{label}</span>}
      <span className="font-mono">{age}</span>
    </span>
  );
}
