import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { ApiError, api } from "../api/client";
import AppShell from "./AppShell";

interface ScenarioDeltas {
  debt_gdp: number;
  fiscal_balance: number;
  current_account: number;
}

interface ScenarioPreview {
  baseline_risk_score: number;
  new_risk_score: number;
  distress_probability: number | null;
  deltas: ScenarioDeltas;
  baseline_debt_gdp: number;
  baseline_fiscal_balance: number;
  baseline_current_account: number;
  new_debt_gdp: number;
  new_fiscal_balance: number;
  new_current_account: number;
}

interface ShockVector {
  gdp_shock: number;
  inflation_shock: number;
  fx_depreciation: number;
  rate_shock: number;
  commodity_shock: number;
}

interface ScenarioRunOut {
  id: string;
  iso3: string;
  shocks: ShockVector;
  outputs: ScenarioPreview;
  created_by: string;
  created_at: string;
  saved: boolean;
}

const SHOCK_LABELS: Record<keyof ShockVector, { label: string; unit: string }> = {
  gdp_shock: { label: "GDP Growth Shock", unit: "pp" },
  inflation_shock: { label: "Inflation Shock", unit: "pp" },
  fx_depreciation: { label: "FX Depreciation", unit: "%" },
  rate_shock: { label: "Interest Rate Shock", unit: "pp" },
  commodity_shock: { label: "Commodity Price Shock", unit: "%" },
};

function fmtDelta(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}`;
}

export default function ScenarioView() {
  const { id = "" } = useParams();
  const { data, isLoading, error } = useQuery<ScenarioRunOut>({
    queryKey: ["scenario", id],
    queryFn: () => api<ScenarioRunOut>(`/api/scenarios/${id}`),
    staleTime: 60 * 1000,
    retry: false,
  });

  if (isLoading) {
    return <AppShell><main className="p-8 text-ink-400">Loading...</main></AppShell>;
  }
  if (error) {
    const msg = error instanceof ApiError && error.status === 404
      ? "Scenario not found"
      : "Failed to load scenario";
    return <AppShell><main className="p-8 text-danger">{msg}</main></AppShell>;
  }
  if (!data) return null;

  const { iso3, shocks, outputs, created_at } = data;

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl p-6">
        <header className="mb-6">
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-semibold text-ink-100">Saved Scenario</h1>
            <span className="font-mono text-sm text-ink-400">{iso3}</span>
          </div>
          <p className="mt-1 text-xs text-ink-400">
            Created {new Date(created_at).toLocaleString()}
          </p>
          <div className="mt-2 flex gap-3">
            <Link
              to={`/countries/${iso3}`}
              className="text-sm text-atlas-400 hover:underline"
            >
              Back to country profile
            </Link>
            <Link
              to={`/scenarios/new?country=${iso3}`}
              className="text-sm text-atlas-400 hover:underline"
            >
              Run new scenario
            </Link>
          </div>
        </header>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Inputs */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-400">
              Shock Inputs
            </h2>
            <div className="rounded-[10px] border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-4">
              <table className="w-full text-sm">
                <tbody>
                  {(Object.keys(SHOCK_LABELS) as (keyof ShockVector)[]).map((key) => (
                    <tr key={key} className="border-b border-white/[0.04] last:border-0">
                      <td className="py-2 text-ink-300">{SHOCK_LABELS[key].label}</td>
                      <td className="py-2 text-right font-mono text-ink-100">
                        {shocks[key] >= 0 ? "+" : ""}{shocks[key].toFixed(1)} {SHOCK_LABELS[key].unit}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Outputs */}
          <section>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-400">
              Results
            </h2>
            <div className="space-y-3">
              {/* Risk comparison */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-[10px] border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-3 text-center">
                  <div className="text-xs text-ink-400">Baseline Risk</div>
                  <div className="mt-1 font-mono text-xl text-ink-100">
                    {outputs.baseline_risk_score.toFixed(1)}
                  </div>
                </div>
                <div className="rounded-[10px] border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-3 text-center">
                  <div className="text-xs text-ink-400">Shocked Risk</div>
                  <div
                    className={`mt-1 font-mono text-xl ${
                      outputs.new_risk_score > outputs.baseline_risk_score
                        ? "text-danger"
                        : outputs.new_risk_score < outputs.baseline_risk_score
                          ? "text-positive"
                          : "text-ink-100"
                    }`}
                  >
                    {outputs.new_risk_score.toFixed(1)}
                  </div>
                </div>
              </div>

              {/* PoD */}
              <div className="rounded-[10px] border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-3">
                <div className="text-xs text-ink-400">Probability of Debt Distress</div>
                <div className="mt-1 font-mono text-ink-100">
                  {outputs.distress_probability != null
                    ? `${(outputs.distress_probability * 100).toFixed(1)}%`
                    : "Not applicable -- country in distressed status"}
                </div>
              </div>

              {/* Deltas */}
              <div className="rounded-[10px] border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-3">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06] text-left text-xs text-ink-400">
                      <th className="pb-1">Metric</th>
                      <th className="pb-1 text-right">Baseline</th>
                      <th className="pb-1 text-right">Shocked</th>
                      <th className="pb-1 text-right">Delta</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono text-sm">
                    <tr>
                      <td className="py-1 text-ink-300">Debt / GDP</td>
                      <td className="py-1 text-right">{outputs.baseline_debt_gdp.toFixed(1)}%</td>
                      <td className="py-1 text-right">{outputs.new_debt_gdp.toFixed(1)}%</td>
                      <td className="py-1 text-right">{fmtDelta(outputs.deltas.debt_gdp)} pp</td>
                    </tr>
                    <tr>
                      <td className="py-1 text-ink-300">Fiscal Balance</td>
                      <td className="py-1 text-right">{outputs.baseline_fiscal_balance.toFixed(1)}%</td>
                      <td className="py-1 text-right">{outputs.new_fiscal_balance.toFixed(1)}%</td>
                      <td className="py-1 text-right">{fmtDelta(outputs.deltas.fiscal_balance)} pp</td>
                    </tr>
                    <tr>
                      <td className="py-1 text-ink-300">Current Account</td>
                      <td className="py-1 text-right">{outputs.baseline_current_account.toFixed(1)}%</td>
                      <td className="py-1 text-right">{outputs.new_current_account.toFixed(1)}%</td>
                      <td className="py-1 text-right">{fmtDelta(outputs.deltas.current_account)} pp</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </div>
      </main>
    </AppShell>
  );
}
