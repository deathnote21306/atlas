import { LineChart, Line, ResponsiveContainer } from "recharts";
import type { StalenessState } from "@atlas/design-system";
import { StalenessChip } from "@atlas/design-system";
import { AlertTriangle, ArrowUp, ArrowDown } from "lucide-react";

interface MacroTile {
  indicator: string;
  label: string;
  value: number | null;
  period: string | null;
  source: string | null;
  staleness: { state: StalenessState; age_days: number | null };
}

interface MacroTabProps {
  tiles: MacroTile[];
  annotations: Record<string, string>;
  sparklines: Record<string, number[]>;
}

const DISPLAY_ORDER: { key: string; label: string; unit: string; deltaUnit: string; biggerBetter: boolean }[] = [
  { key: "GDP_GROWTH_PCT", label: "Real GDP Growth", unit: "%", deltaUnit: "pp", biggerBetter: true },
  { key: "INFLATION_PCT", label: "CPI Inflation", unit: "%", deltaUnit: "pp", biggerBetter: false },
  { key: "FISCAL_BALANCE_PCT_GDP", label: "Fiscal Balance", unit: "% GDP", deltaUnit: "pp", biggerBetter: true },
  { key: "FX_RESERVES_MO_IMPORTS", label: "FX Reserves", unit: "months", deltaUnit: "", biggerBetter: true },
  { key: "DEBT_SERVICE_PCT_EXPORTS", label: "Import Cover", unit: "months", deltaUnit: "", biggerBetter: true },
  { key: "EXTERNAL_DEBT_PCT_GNI", label: "External Debt/GDP", unit: "%", deltaUnit: "pp", biggerBetter: false },
];

function stalenessLabel(state: StalenessState): string {
  if (state === "red") return "VERY STALE";
  if (state === "yellow") return "STALE";
  return "FRESH";
}

function stalePillColor(state: StalenessState): string {
  if (state === "red") return "bg-orange-500/10 text-orange-500 border-orange-500/30";
  if (state === "yellow") return "bg-amber-500/10 text-amber-500 border-amber-500/30";
  return "bg-green-500/10 text-green-500 border-green-500/30";
}

function periodLabel(period: string | null): string {
  if (!period) return "\u2014";
  const currentYear = new Date().getFullYear();
  return Number(period) > currentYear ? `${period} (est)` : period;
}

export default function MacroTab({ tiles, annotations, sparklines }: MacroTabProps) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
      {DISPLAY_ORDER.map((def) => {
        const tile = tiles.find((t) => t.indicator === def.key);
        const warning = annotations[def.key];
        const sparkData = sparklines[def.key];

        return (
          <MacroCard
            key={def.key}
            label={def.label}
            value={tile?.value ?? null}
            unit={def.unit}
            staleness={tile?.staleness ?? { state: "fresh" as StalenessState, age_days: null }}
            period={tile?.period ?? null}
            source={tile?.source ?? null}
            warning={warning}
            sparkData={sparkData}
          />
        );
      })}
    </div>
  );
}

interface MacroCardProps {
  label: string;
  value: number | null;
  unit: string;
  staleness: { state: StalenessState; age_days: number | null };
  period: string | null;
  source: string | null;
  warning?: string;
  sparkData?: number[];
}

function MacroCard({ label, value, unit, staleness, period, source, warning, sparkData }: MacroCardProps) {
  const chartData = sparkData?.map((v, i) => ({ i, v }));

  return (
    <div className="rounded-lg bg-[#161b22] p-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <span className="text-[13px] text-ink-400">{label}</span>
        <span
          className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${stalePillColor(staleness.state)}`}
        >
          {stalenessLabel(staleness.state)}
        </span>
      </div>

      {/* Value */}
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-semibold tabular-nums text-ink-100">
          {value != null ? value.toFixed(1) : "\u2014"}
        </span>
        <span className="text-sm text-ink-500">{unit}</span>
      </div>

      {/* Sparkline */}
      {chartData && chartData.length > 1 && (
        <div className="mt-2 h-8">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <Line
                type="monotone"
                dataKey="v"
                stroke="#f59e0b"
                strokeOpacity={0.7}
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Footer */}
      <div className="mt-2 flex items-center justify-between text-[11px] text-ink-500">
        <span>{periodLabel(period)}</span>
        <span>{source ?? ""}</span>
      </div>

      {/* Warning */}
      {warning && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-400">
          <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
          <span>{warning}</span>
        </div>
      )}
    </div>
  );
}
