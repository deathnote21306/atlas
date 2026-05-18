import { AlertTriangle, Sparkles } from "lucide-react";
import SynopsisCard, { type SynopsisData } from "../../components/SynopsisCard";

interface RiskDimension {
  key: string;
  label: string;
  score: number;
  weight: number;
}

interface OverviewTabProps {
  keyRisks: string[];
  keyOpportunities: string[];
  riskDecomposition: { dimensions: RiskDimension[] } | null;
  synopsisData: SynopsisData | null;
}

function ringColor(score: number): string {
  if (score >= 80) return "#ef4444";
  if (score >= 60) return "#f97316";
  if (score >= 30) return "#f59e0b";
  return "#22c55e";
}

function MiniRiskRing({ score, label, weight }: { score: number; label: string; weight: number }) {
  const r = 22;
  const circumference = 2 * Math.PI * r;
  const progress = (score / 100) * circumference;
  const color = ringColor(score);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="60" height="60" viewBox="0 0 60 60">
        <circle cx="30" cy="30" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
        <circle
          cx="30" cy="30" r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={circumference} strokeDashoffset={circumference - progress}
          strokeLinecap="round" transform="rotate(-90 30 30)"
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
        <text x="30" y="34" textAnchor="middle" className="fill-ink-100 font-semibold" style={{ fontSize: "14px" }}>
          {score}
        </text>
      </svg>
      <span className="text-xs font-medium text-ink-300">{label}</span>
      <span className="text-[10px] text-ink-500">w: {weight}%</span>
    </div>
  );
}

export default function OverviewTab({ keyRisks, keyOpportunities, riskDecomposition, synopsisData }: OverviewTabProps) {
  return (
    <div className="space-y-6">
      {/* Key Risks + Key Opportunities */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Key Risks */}
        <div className="rounded-lg bg-[#161b22] p-6">
          <div className="mb-4 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500" />
            <h3 className="text-base font-semibold text-ink-100">Key Risks</h3>
          </div>
          <ul className="space-y-2">
            {keyRisks.map((risk, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-200">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                {risk}
              </li>
            ))}
          </ul>
          {keyRisks.length === 0 && <p className="text-sm text-ink-500">No key risks available</p>}
        </div>

        {/* Key Opportunities */}
        <div className="rounded-lg bg-[#161b22] p-6">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-positive" />
            <h3 className="text-base font-semibold text-ink-100">Key Opportunities</h3>
          </div>
          <ul className="space-y-2">
            {keyOpportunities.map((opp, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-ink-200">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-positive" />
                {opp}
              </li>
            ))}
          </ul>
          {keyOpportunities.length === 0 && <p className="text-sm text-ink-500">No key opportunities available</p>}
        </div>
      </div>

      {/* Risk Decomposition Overview */}
      {riskDecomposition && riskDecomposition.dimensions.length > 0 && (
        <div className="rounded-lg bg-[#161b22] p-6">
          <h3 className="mb-5 text-base font-semibold text-ink-100">Risk Decomposition Overview</h3>
          <div className="grid grid-cols-3 gap-6 sm:grid-cols-6">
            {riskDecomposition.dimensions.map((d) => (
              <MiniRiskRing key={d.key} score={d.score} label={d.label} weight={d.weight} />
            ))}
          </div>
        </div>
      )}

      {/* Synopsis Detail */}
      <div className="rounded-lg bg-[#161b22] p-6">
        <h3 className="mb-4 text-base font-semibold text-ink-100">Synopsis Detail</h3>
        <SynopsisCard synopsis={synopsisData} />
      </div>
    </div>
  );
}
