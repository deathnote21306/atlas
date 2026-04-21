interface RiskGaugeCircleProps {
  score: number;
  label: string;
  trend: string;
}

function riskColor(score: number): string {
  if (score >= 80) return "#ef4444";
  if (score >= 60) return "#f97316";
  if (score >= 30) return "#f59e0b";
  return "#22c55e";
}

function trendIcon(trend: string): string {
  if (trend === "deteriorating") return "\u2193";
  if (trend === "improving") return "\u2191";
  return "\u2192";
}

function trendColor(trend: string): string {
  if (trend === "deteriorating") return "text-danger";
  if (trend === "improving") return "text-positive";
  return "text-ink-400";
}

export default function RiskGaugeCircle({ score, label, trend }: RiskGaugeCircleProps) {
  const r = 44;
  const circumference = 2 * Math.PI * r;
  const progress = (score / 100) * circumference;
  const color = riskColor(score);

  return (
    <div className="flex flex-col items-center">
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="8"
        />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          transform="rotate(-90 60 60)"
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
        <text x="60" y="55" textAnchor="middle" className="fill-ink-100 text-2xl font-bold" style={{ fontSize: "28px" }}>
          {score}
        </text>
        <text x="60" y="72" textAnchor="middle" className="fill-ink-500" style={{ fontSize: "12px" }}>
          /100
        </text>
      </svg>
      <div className="mt-1 text-center">
        <span className="text-sm font-medium" style={{ color }}>{label}</span>
        <span className={`ml-2 text-xs ${trendColor(trend)}`}>
          {trendIcon(trend)} {trend}
        </span>
      </div>
    </div>
  );
}
