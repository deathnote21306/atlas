// packages/design-system/src/primitives/KpiCard.tsx
import type { ReactNode } from "react";

export interface KpiCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  className?: string;
}

export function KpiCard({ label, value, hint, className = "" }: KpiCardProps) {
  return (
    <div className={`rounded-md border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-4 ${className}`}>
      <div className="text-xs uppercase tracking-wide text-ink-400">{label}</div>
      <div className="mt-1 font-mono text-2xl tabular-nums text-ink-100">{value}</div>
      {hint ? <div className="mt-1 text-xs text-ink-400">{hint}</div> : null}
    </div>
  );
}
