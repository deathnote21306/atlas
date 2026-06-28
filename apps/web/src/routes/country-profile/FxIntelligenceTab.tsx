import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, XAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../../api/client";

function sourceLabel(source: string): string {
  switch (source) {
    case "imf_eer": return "IMF EER";
    case "imf_ifs": return "IMF IFS";
    case "bis_broad": return "BIS broad";
    case "bis_narrow": return "BIS narrow";
    case "seed": return "ATLAS estimate";
    default: return source;
  }
}

function formatMonthYear(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

interface FxIntel {
  pair: string;
  regime: string | null;
  regime_label: string | null;
  change_ladder: {
    "1d": number | null;
    "1w": number | null;
    "1m": number | null;
    "3m": number | null;
    as_of: string | null;
  };
  implied_vol: { value: number | null; note: string | null };
  parallel_premium: { value_pct: number | null; severity: string };
  reer_deviation: { value_pct: number | null; label: string; as_of: string | null; source?: string; base_period?: string };
  reserves_usd_bn: number | null;
  last_bc_intervention: string | null;
}

interface FxHistoryResponse {
  pair: string;
  start: string;
  end: string;
  primary_source: string;
  has_synthetic_data: boolean;
  points: { date: string; value: number; source?: string }[];
}

interface FxIntelligenceTabProps {
  iso3: string;
  fxIntel: FxIntel | null;
  spotRate: number | null;
  spotAsOf: string | null;
  staleness: string;
}

function changeLadderColor(val: number | null): string {
  if (val == null) return "text-ink-500";
  if (val > 0) return "text-danger";
  if (val < 0) return "text-positive";
  return "text-ink-400";
}

function formatChange(val: number | null): string {
  if (val == null) return "\u2014";
  return `${val >= 0 ? "+" : ""}${val.toFixed(1)}`;
}

function stalePillColor(state: string): string {
  if (state === "VERY STALE") return "bg-orange-500/10 text-orange-500 border-orange-500/30";
  if (state === "STALE") return "bg-amber-500/10 text-amber-500 border-amber-500/30";
  return "bg-green-500/10 text-green-500 border-green-500/30";
}

function severityPillColor(severity: string): string {
  switch (severity) {
    case "CRITICAL": return "bg-red-500/10 text-red-500 border-red-500/30";
    case "ELEVATED": return "bg-orange-500/10 text-orange-500 border-orange-500/30";
    case "NOTABLE": return "bg-amber-500/10 text-amber-500 border-amber-500/30";
    default: return "bg-[#21262d] text-ink-400 border-[#21262d]";
  }
}

function reerLabelColor(label: string): string {
  if (label === "extreme undervaluation") return "text-danger";
  if (label === "undervalued") return "text-amber-500";
  if (label === "overvalued") return "text-orange-500";
  return "text-ink-400";
}

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function interventionAge(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400_000);
  if (days > 180) return "(6+ months ago)";
  return "";
}

export default function FxIntelligenceTab({ iso3, fxIntel, spotRate, spotAsOf, staleness }: FxIntelligenceTabProps) {
  const { data: history } = useQuery<FxHistoryResponse>({
    queryKey: ["fx-history", iso3],
    queryFn: () => api<FxHistoryResponse>(`/api/countries/${iso3}/fx-history?window=12m`),
    staleTime: 30 * 60_000,
  });

  if (!fxIntel) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-[#161b22] py-16">
        <p className="text-sm text-ink-500">No FX intelligence data available</p>
      </div>
    );
  }

  const ladder = fxIntel.change_ladder;

  return (
    <div className="space-y-6">
      {/* Title row */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-ink-100">{fxIntel.pair} &mdash; FX Intelligence</h3>
        <span className={`rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider ${stalePillColor(staleness)}`}>
          {staleness}
        </span>
      </div>

      {/* Main card */}
      <div className="rounded-lg bg-[#161b22] p-6">
        {/* Top section: spot + change ladder */}
        <div className="flex items-start gap-8">
          {/* Spot level */}
          <div className="w-2/5">
            <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Spot Level</p>
            <p className="mt-1 text-4xl font-semibold tabular-nums text-ink-100">
              {spotRate != null ? spotRate.toFixed(2) : "\u2014"}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Regime</span>
              {fxIntel.regime_label ? (
                <span className="rounded-full bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-500">
                  {fxIntel.regime_label}
                </span>
              ) : (
                <span className="text-xs text-ink-500">&mdash;</span>
              )}
            </div>
          </div>

          {/* Change ladder */}
          <div className="grid w-3/5 grid-cols-4 gap-3">
            {(["1d", "1w", "1m", "3m"] as const).map((window) => (
              <div key={window} className="rounded-md border border-[#21262d] bg-[#131920] px-3 py-3 text-center">
                <div className="text-[11px] uppercase tracking-wider text-ink-500">{window.toUpperCase()}</div>
                <div className={`mt-1 text-lg font-semibold tabular-nums ${changeLadderColor(ladder[window])}`}>
                  {formatChange(ladder[window])}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Divider */}
        <div className="my-5 border-t border-[#21262d]" />

        {/* Indicator table */}
        <div className="space-y-0">
          {/* Implied Volatility */}
          <div className="flex items-center justify-between border-b border-[#21262d] py-3">
            <span className="text-sm text-ink-400">Implied Volatility</span>
            <span className="text-sm tabular-nums text-ink-200">
              {fxIntel.implied_vol.value != null
                ? `${fxIntel.implied_vol.value.toFixed(1)}%`
                : <span className="text-ink-500">N/A {fxIntel.implied_vol.note ? `(${fxIntel.implied_vol.note})` : ""}</span>
              }
            </span>
          </div>

          {/* Parallel Market Premium */}
          <div className="flex items-center justify-between border-b border-[#21262d] py-3">
            <span className="text-sm text-ink-400">Parallel Market Premium</span>
            <div className="flex items-center gap-2">
              <span className="text-sm tabular-nums text-ink-200">
                {fxIntel.parallel_premium.value_pct != null
                  ? `${fxIntel.parallel_premium.value_pct.toFixed(1)}%`
                  : "\u2014"
                }
              </span>
              {fxIntel.parallel_premium.severity !== "TIGHT" && fxIntel.parallel_premium.severity !== "—" && (
                <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase ${severityPillColor(fxIntel.parallel_premium.severity)}`}>
                  {fxIntel.parallel_premium.severity}
                </span>
              )}
            </div>
          </div>

          {/* REER Deviation */}
          <div className="border-b border-[#21262d] py-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-ink-400">REER Deviation</span>
              <div className="flex items-center gap-2">
                <span className="text-sm tabular-nums text-ink-200">
                  {fxIntel.reer_deviation.value_pct != null
                    ? `${fxIntel.reer_deviation.value_pct > 0 ? "+" : ""}${fxIntel.reer_deviation.value_pct.toFixed(1)}%`
                    : "\u2014"
                  }
                </span>
                <span className={`text-xs ${reerLabelColor(fxIntel.reer_deviation.label)}`}>
                  {fxIntel.reer_deviation.label}
                </span>
              </div>
            </div>
            {fxIntel.reer_deviation.source && (
              <div className="mt-1 text-right">
                <span className={`text-[11px] ${fxIntel.reer_deviation.source === "seed" ? "text-amber-500/70" : "text-ink-500"}`}>
                  {fxIntel.reer_deviation.source === "seed"
                    ? "ATLAS estimate \u00b7 pending real-source fetch"
                    : `${sourceLabel(fxIntel.reer_deviation.source)} \u00b7 base ${fxIntel.reer_deviation.base_period ?? "2010"} \u00b7 ${formatMonthYear(fxIntel.reer_deviation.as_of)}`
                  }
                </span>
              </div>
            )}
          </div>

          {/* FX Reserves */}
          <div className="flex items-center justify-between border-b border-[#21262d] py-3">
            <span className="text-sm text-ink-400">FX Reserves</span>
            <span className="text-sm tabular-nums text-ink-200">
              {fxIntel.reserves_usd_bn != null
                ? `USD ${fxIntel.reserves_usd_bn.toFixed(1)} bn`
                : "\u2014"
              }
            </span>
          </div>

          {/* Last BC Intervention */}
          <div className="flex items-center justify-between py-3">
            <span className="text-sm text-ink-400">Last BC Intervention</span>
            <span className="text-sm text-ink-200">
              {fxIntel.last_bc_intervention
                ? <>{formatDate(fxIntel.last_bc_intervention)} <span className="text-[10px] text-ink-500">{interventionAge(fxIntel.last_bc_intervention)}</span></>
                : <span className="text-ink-500" title="No recorded interventions">&mdash;</span>
              }
            </span>
          </div>
        </div>
      </div>

      {/* FX History chart card */}
      {history && history.points.length > 1 && (
        <div className="rounded-lg bg-[#161b22] p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-ink-200">{fxIntel.pair} &mdash; 12-month history</h4>
              {history.has_synthetic_data && (
                <span className="text-[11px] text-amber-500/70" title="Some historical values are seed approximations pending real-source backfill.">
                  &#x26A0; Contains approximated data
                </span>
              )}
              {!history.has_synthetic_data && history.primary_source === "cfa_computed" && (
                <span className="text-[11px] text-amber-500/70">
                  &#x2726; Derived from EUR/USD &times; CFA peg
                </span>
              )}
            </div>
            <span className="text-[11px] text-ink-500">
              {history.start} &rarr; {history.end}
            </span>
          </div>
          <div className="mt-4 h-36">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.points}>
                <XAxis
                  dataKey="date"
                  tickFormatter={(d: string) => new Date(d).toLocaleDateString("en-US", { month: "short" })}
                  tick={{ fontSize: 10, fill: "#6b7280" }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0b1220",
                    border: "1px solid rgba(255,255,255,0.06)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  labelFormatter={(d) => new Date(String(d)).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })}
                  formatter={(v) => [Number(v).toFixed(2), fxIntel.pair]}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#f59e0b"
                  strokeWidth={1.5}
                  dot={false}
                  activeDot={{ r: 3, fill: "#f59e0b" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
