import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api } from "../api/client";
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

const SLIDER_CONFIG: {
  key: keyof ShockVector;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  { key: "gdp_shock", label: "GDP Growth Shock", min: -20, max: 20, step: 0.5, unit: "pp" },
  { key: "inflation_shock", label: "Inflation Shock", min: -20, max: 20, step: 0.5, unit: "pp" },
  { key: "fx_depreciation", label: "FX Depreciation", min: -50, max: 100, step: 1, unit: "%" },
  { key: "rate_shock", label: "Interest Rate Shock", min: -10, max: 20, step: 0.5, unit: "pp" },
  { key: "commodity_shock", label: "Commodity Price Shock", min: -50, max: 50, step: 1, unit: "%" },
];

function fmtDelta(n: number): string {
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}`;
}

export default function ScenarioEngine() {
  const [params] = useSearchParams();
  const iso3 = (params.get("country") ?? "").toUpperCase();

  const [shocks, setShocks] = useState<ShockVector>({
    gdp_shock: 0,
    inflation_shock: 0,
    fx_depreciation: 0,
    rate_shock: 0,
    commodity_shock: 0,
  });

  const [preview, setPreview] = useState<ScenarioPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPreview = useCallback(
    async (s: ShockVector) => {
      if (!iso3) return;
      setLoading(true);
      setError(null);
      try {
        const result = await api<ScenarioPreview>("/api/scenarios/preview", {
          method: "POST",
          body: JSON.stringify({ iso3, shocks: s }),
        });
        setPreview(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Preview failed");
      } finally {
        setLoading(false);
      }
    },
    [iso3],
  );

  // Debounced preview: 300ms after last slider change
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => fetchPreview(shocks), 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [shocks, fetchPreview]);

  const handleSlider = (key: keyof ShockVector, value: number) => {
    setShocks((prev) => ({ ...prev, [key]: value }));
    setSavedId(null);
  };

  const handleSave = async () => {
    if (!iso3) return;
    setSaving(true);
    try {
      const result = await api<{ id: string }>("/api/scenarios", {
        method: "POST",
        body: JSON.stringify({ iso3, shocks }),
      });
      setSavedId(result.id);
    } catch {
      setError("Failed to save scenario");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setShocks({
      gdp_shock: 0,
      inflation_shock: 0,
      fx_depreciation: 0,
      rate_shock: 0,
      commodity_shock: 0,
    });
    setSavedId(null);
  };

  if (!iso3) {
    return (
      <AppShell>
        <main className="p-8 text-danger">Missing country parameter.</main>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-5xl p-6">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-semibold text-ink-900">Scenario Engine</h1>
            <span className="font-mono text-sm text-ink-500">{iso3}</span>
          </div>
          <p className="mt-1 text-sm text-ink-500">
            Adjust the macro shock sliders to see how the risk profile changes.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Left: Sliders */}
          <section>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-500">
              Shock Vector
            </h2>
            <div className="space-y-4">
              {SLIDER_CONFIG.map((cfg) => (
                <div key={cfg.key} className="rounded-md border border-ink-100 bg-white p-4">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor={cfg.key}
                      className="text-sm font-medium text-ink-700"
                    >
                      {cfg.label}
                    </label>
                    <span className="font-mono text-sm text-ink-900">
                      {shocks[cfg.key] >= 0 ? "+" : ""}
                      {shocks[cfg.key].toFixed(1)} {cfg.unit}
                    </span>
                  </div>
                  <input
                    id={cfg.key}
                    type="range"
                    min={cfg.min}
                    max={cfg.max}
                    step={cfg.step}
                    value={shocks[cfg.key]}
                    onChange={(e) => handleSlider(cfg.key, parseFloat(e.target.value))}
                    className="mt-2 w-full accent-atlas-600"
                  />
                  <div className="mt-1 flex justify-between text-[10px] text-ink-300">
                    <span>{cfg.min} {cfg.unit}</span>
                    <span>0</span>
                    <span>{cfg.max} {cfg.unit}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 flex gap-3">
              <button
                onClick={handleSave}
                disabled={saving || !preview}
                className="rounded-md bg-atlas-600 px-4 py-2 text-sm font-medium text-white hover:bg-atlas-700 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Scenario"}
              </button>
              <button
                onClick={handleReset}
                className="rounded-md border border-ink-200 px-4 py-2 text-sm font-medium text-ink-700 hover:bg-ink-50"
              >
                Reset
              </button>
            </div>
            {savedId && (
              <p className="mt-2 text-sm text-positive">
                Saved!{" "}
                <Link to={`/scenarios/${savedId}`} className="underline">
                  View saved scenario
                </Link>
              </p>
            )}
          </section>

          {/* Right: Results */}
          <section>
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-500">
              Scenario Output
            </h2>

            {loading && <p className="text-sm text-ink-500">Computing...</p>}
            {error && <p className="text-sm text-danger">{error}</p>}

            {preview && !loading && (
              <div className="space-y-4">
                {/* Risk Score comparison */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-md border border-ink-100 bg-white p-4 text-center">
                    <div className="text-xs text-ink-500">Baseline Risk</div>
                    <div className="mt-1 font-mono text-2xl text-ink-900">
                      {preview.baseline_risk_score.toFixed(1)}
                    </div>
                  </div>
                  <div className="rounded-md border border-ink-100 bg-white p-4 text-center">
                    <div className="text-xs text-ink-500">Shocked Risk</div>
                    <div
                      className={`mt-1 font-mono text-2xl ${
                        preview.new_risk_score > preview.baseline_risk_score
                          ? "text-danger"
                          : preview.new_risk_score < preview.baseline_risk_score
                            ? "text-positive"
                            : "text-ink-900"
                      }`}
                    >
                      {preview.new_risk_score.toFixed(1)}
                    </div>
                  </div>
                </div>

                {/* PoD */}
                <div className="rounded-md border border-ink-100 bg-white p-4">
                  <div className="text-xs text-ink-500">Probability of Debt Distress</div>
                  <div className="mt-1 font-mono text-lg text-ink-900">
                    {preview.distress_probability != null
                      ? `${(preview.distress_probability * 100).toFixed(1)}%`
                      : "Not applicable -- country in distressed status"}
                  </div>
                </div>

                {/* Deltas table */}
                <div className="rounded-md border border-ink-100 bg-white p-4">
                  <div className="text-xs text-ink-500 mb-2">Fiscal Deltas</div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-ink-100 text-left text-xs text-ink-500">
                        <th className="pb-1">Metric</th>
                        <th className="pb-1 text-right">Baseline</th>
                        <th className="pb-1 text-right">Shocked</th>
                        <th className="pb-1 text-right">Delta</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      <tr>
                        <td className="py-1 text-ink-700">Debt / GDP</td>
                        <td className="py-1 text-right">{preview.baseline_debt_gdp.toFixed(1)}%</td>
                        <td className="py-1 text-right">{preview.new_debt_gdp.toFixed(1)}%</td>
                        <td className={`py-1 text-right ${preview.deltas.debt_gdp > 0 ? "text-danger" : "text-positive"}`}>
                          {fmtDelta(preview.deltas.debt_gdp)} pp
                        </td>
                      </tr>
                      <tr>
                        <td className="py-1 text-ink-700">Fiscal Balance</td>
                        <td className="py-1 text-right">{preview.baseline_fiscal_balance.toFixed(1)}%</td>
                        <td className="py-1 text-right">{preview.new_fiscal_balance.toFixed(1)}%</td>
                        <td className={`py-1 text-right ${preview.deltas.fiscal_balance < 0 ? "text-danger" : "text-positive"}`}>
                          {fmtDelta(preview.deltas.fiscal_balance)} pp
                        </td>
                      </tr>
                      <tr>
                        <td className="py-1 text-ink-700">Current Account</td>
                        <td className="py-1 text-right">{preview.baseline_current_account.toFixed(1)}%</td>
                        <td className="py-1 text-right">{preview.new_current_account.toFixed(1)}%</td>
                        <td className={`py-1 text-right ${preview.deltas.current_account < 0 ? "text-danger" : "text-positive"}`}>
                          {fmtDelta(preview.deltas.current_account)} pp
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    </AppShell>
  );
}
