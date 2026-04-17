export type RiskLevel = "LOW" | "MODERATE" | "ELEVATED" | "HIGH" | "CRITICAL";

export interface RiskBadgeProps {
  score: number;  // 0-100 composite
}

function riskLevel(score: number): RiskLevel {
  if (score <= 25) return "LOW";
  if (score <= 40) return "MODERATE";
  if (score <= 55) return "ELEVATED";
  if (score <= 70) return "HIGH";
  return "CRITICAL";
}

const COLORS: Record<RiskLevel, string> = {
  LOW: "bg-positive/15 text-positive",
  MODERATE: "bg-positive/10 text-ink-700",
  ELEVATED: "bg-warning/15 text-warning",
  HIGH: "bg-warning/20 text-warning",
  CRITICAL: "bg-danger/15 text-danger",
};

export function RiskBadge({ score }: RiskBadgeProps) {
  const level = riskLevel(score);
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${COLORS[level]}`}>
      {level}
    </span>
  );
}
