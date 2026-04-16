// packages/design-system/src/primitives/KpiCard.tsx
import type { ReactNode } from "react";

export interface KpiCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
}

export function KpiCard({ label, value, hint }: KpiCardProps) {
  return (
    <div className="rounded-md border border-ink-100 bg-white p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-1 font-mono text-2xl text-ink-900">{value}</div>
      {hint ? <div className="mt-1 text-xs text-ink-300">{hint}</div> : null}
    </div>
  );
}
