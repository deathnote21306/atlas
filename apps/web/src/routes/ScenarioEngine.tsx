import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { toast } from "../components/Toast";
import { RiskBadge } from "@atlas/design-system";
import AppShell from "./AppShell";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ScenarioDeltas {
  debt_gdp: number;
  fiscal_balance: number;
  current_account: number;
}

interface CountryImpact {
  iso3: string;
  name: string;
  status: string;
  baseline_risk: number;
  new_risk: number;
  risk_change: number;
  deltas: ScenarioDeltas;
  distress_probability: number | null;
}

interface ShockVector {
  gdp_shock: number;
  inflation_shock: number;
  fx_depreciation: number;
  rate_shock: number;
  commodity_shock: number;
}

interface SavedScenario {
  id: string;
  iso3: string;
  title?: string;
  description?: string | null;
  shocks: ShockVector;
  created_at: string;
  saved?: boolean;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const DEFAULT_SHOCKS: ShockVector = {
  gdp_shock: 0,
  inflation_shock: 0,
  fx_depreciation: 0,
  rate_shock: 0,
  commodity_shock: 0,
};

const SLIDER_CONFIG: {
  key: keyof ShockVector;
  label: string;
  min: number;
  max: number;
  step: number;
  unit: string;
}[] = [
  { key: "gdp_shock", label: "Global GDP Growth (pp)", min: -5, max: 5, step: 0.1, unit: "pp" },
  { key: "inflation_shock", label: "Inflation Shock (pp)", min: -10, max: 15, step: 0.5, unit: "pp" },
  { key: "fx_depreciation", label: "USD Appreciation (%)", min: -10, max: 30, step: 0.5, unit: "%" },
  { key: "rate_shock", label: "EM Spread Widening (bps / 100)", min: -5, max: 10, step: 0.25, unit: "bps/100" },
  { key: "commodity_shock", label: "Commodity Price Shock (%)", min: -50, max: 50, step: 1, unit: "%" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatAge(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diffMs / 86_400_000);
  if (days < 1) return "just now";
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  return `${months}mo ago`;
}

function hasNonZeroShock(s: ShockVector): boolean {
  return Object.values(s).some((v) => v !== 0);
}

/* ------------------------------------------------------------------ */
/*  ImpactCard                                                         */
/* ------------------------------------------------------------------ */

function getRiskTint(newRisk: number): { bg: string; border: string } {
  if (newRisk < 30) return { bg: "rgba(34,197,94,0.03)", border: "rgba(34,197,94,0.06)" };
  if (newRisk < 45) return { bg: "rgba(132,204,22,0.03)", border: "rgba(132,204,22,0.06)" };
  if (newRisk < 60) return { bg: "rgba(245,158,11,0.03)", border: "rgba(245,158,11,0.06)" };
  if (newRisk < 75) return { bg: "rgba(249,115,22,0.03)", border: "rgba(249,115,22,0.06)" };
  return { bg: "rgba(239,68,68,0.03)", border: "rgba(239,68,68,0.06)" };
}

function getImpactText(impact: CountryImpact): string {
  if (impact.risk_change > 5)
    return `Significant deterioration expected. Risk score increases by ${impact.risk_change.toFixed(1)} points under this scenario.`;
  if (impact.risk_change > 0)
    return "Moderate negative impact. Debt sustainability metrics weaken slightly.";
  if (impact.risk_change < -5)
    return "Notable improvement projected. Fiscal position strengthens under favorable conditions.";
  if (impact.risk_change < 0)
    return "Mild positive effect. Risk metrics improve marginally under this scenario.";
  return "Limited impact. Country fundamentals remain largely unchanged.";
}

function ImpactCard({ impact, fxValue }: { impact: CountryImpact; fxValue: number }) {
  const changeColor =
    impact.risk_change > 0 ? "text-danger" : impact.risk_change < 0 ? "text-positive" : "text-ink-400";
  const sign = impact.risk_change > 0 ? "+" : "";
  const tint = getRiskTint(impact.new_risk);

  return (
    <div
      className="rounded-[10px] border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-4"
      style={{ backgroundColor: tint.bg, borderLeftWidth: 3, borderLeftColor: tint.border }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink-100">{impact.name}</span>
          <RiskBadge score={impact.new_risk} />
        </div>
        <span className={`font-mono font-semibold ${changeColor}`}>
          {sign}{impact.risk_change.toFixed(1)} risk pts
        </span>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
        {[
          { label: "GDP (pp)", v: impact.deltas.debt_gdp },
          { label: "Fiscal (pp)", v: impact.deltas.fiscal_balance },
          { label: "External (pp)", v: impact.deltas.current_account },
          { label: "FX (%)", v: fxValue },
        ].map((cell) => (
          <div key={cell.label}>
            <div className="text-ink-400">{cell.label}</div>
            <div className={`font-mono ${cell.v < 0 ? "text-danger" : "text-positive"}`}>
              {cell.v >= 0 ? "+" : ""}{cell.v.toFixed(1)}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-ink-400 italic">{getImpactText(impact)}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ScenarioLibrary                                                    */
/* ------------------------------------------------------------------ */

function ScenarioLibrary({
  scenarios,
  onSelect,
  onNew,
}: {
  scenarios: SavedScenario[];
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <aside className="w-72 shrink-0 border-r border-white/[0.06] bg-ink-900/50 p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-400">Scenario Library</h2>
      <button
        onClick={onNew}
        className="mt-3 w-full rounded border border-white/[0.06] py-2 text-sm text-ink-300 hover:border-white/[0.12]"
      >
        + New Scenario
      </button>
      <ul className="mt-4 space-y-2">
        {scenarios.map((s) => (
          <li key={s.id}>
            <button
              onClick={() => onSelect(s.id)}
              className="w-full rounded-[10px] border border-white/[0.06] bg-white/[0.03] p-3 text-left hover:border-white/[0.12]"
            >
              <div className="text-sm font-medium text-ink-100">{s.title || "Untitled"}</div>
              <div className="mt-1 flex items-center gap-2 text-[10px] text-ink-400">
                <span className="rounded bg-positive/10 px-1.5 py-0.5 text-positive">saved</span>
                <span>{formatAge(s.created_at)}</span>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function ScenarioEngine() {
  const navigate = useNavigate();

  const [shocks, setShocks] = useState<ShockVector>({ ...DEFAULT_SHOCKS });
  const [debouncedShocks, setDebouncedShocks] = useState<ShockVector>({ ...DEFAULT_SHOCKS });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const [impacts, setImpacts] = useState<CountryImpact[] | null>(null);
  const [impactsLoading, setImpactsLoading] = useState(false);

  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>([]);

  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce shocks by 300ms
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setDebouncedShocks({ ...shocks }), 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [shocks]);

  // Fetch all saved scenarios on mount
  useEffect(() => {
    api<SavedScenario[]>("/api/scenarios")
      .then(setSavedScenarios)
      .catch((err) => toast.error(err instanceof Error ? err.message : "Failed to load scenarios"));
  }, []);

  // Preview-all when debounced shocks change (only if non-zero)
  const fetchPreviewAll = useCallback(async (s: ShockVector) => {
    if (!hasNonZeroShock(s)) {
      setImpacts(null);
      return;
    }
    setImpactsLoading(true);
    setError(null);
    try {
      const result = await api<CountryImpact[]>("/api/scenarios/preview-all", {
        method: "POST",
        body: JSON.stringify({ shocks: s }),
      });
      setImpacts(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setImpactsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPreviewAll(debouncedShocks);
  }, [debouncedShocks, fetchPreviewAll]);

  const handleSlider = (key: keyof ShockVector, value: number) => {
    setShocks((prev) => ({ ...prev, [key]: value }));
    setSavedId(null);
  };

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const result = await api<{ id: string }>("/api/scenarios", {
        method: "POST",
        body: JSON.stringify({ iso3: "ALL", shocks, title: title.trim(), description: description.trim() || null }),
      });
      setSavedId(result.id);
      toast.success("Scenario saved");
      // Refresh sidebar
      const updated = await api<SavedScenario[]>("/api/scenarios");
      setSavedScenarios(updated);
    } catch {
      setError("Failed to save scenario");
      toast.error("Failed to save scenario");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setShocks({ ...DEFAULT_SHOCKS });
    setTitle("");
    setDescription("");
    setSavedId(null);
  };

  const handleSelect = (id: string) => {
    navigate(`/scenarios/${id}`);
  };

  return (
    <AppShell>
      <div className="flex min-h-[calc(100vh-3rem)]">
        {/* Left: Scenario Library */}
        <ScenarioLibrary scenarios={savedScenarios} onSelect={handleSelect} onNew={handleReset} />

        {/* Center: Sliders + save form */}
        <div className="w-96 shrink-0 border-r border-white/[0.06] p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-400">
            Scenario Variables
          </h2>

          {/* Title input */}
          <div className="mb-4">
            <label htmlFor="scenario-title" className="mb-1 block text-xs font-medium text-ink-400">
              Title <span className="text-danger">*</span>
            </label>
            <input
              id="scenario-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Trade War Escalation"
              className="w-full rounded-md border border-white/[0.06] bg-white/[0.04] px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-atlas-600 focus:outline-none"
            />
          </div>

          {/* Sliders */}
          <div className="space-y-4">
            {SLIDER_CONFIG.map((cfg) => (
              <div key={cfg.key} className="rounded-[10px] border border-white/[0.06] bg-white/[0.03] backdrop-blur-xl p-4">
                <div className="flex items-center justify-between">
                  <label htmlFor={cfg.key} className="text-sm font-medium text-ink-300">
                    {cfg.label}
                  </label>
                  <span className="font-mono font-semibold text-ink-100">
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
                <div className="mt-1 flex justify-between text-[10px] text-ink-400">
                  <span>{cfg.min} {cfg.unit}</span>
                  <span>0</span>
                  <span>{cfg.max} {cfg.unit}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Description textarea */}
          <div className="mt-4">
            <label htmlFor="scenario-desc" className="mb-1 block text-xs font-medium text-ink-400">
              Description
            </label>
            <textarea
              id="scenario-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional notes about this scenario..."
              rows={3}
              className="w-full rounded-md border border-white/[0.06] bg-white/[0.04] px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-atlas-600 focus:outline-none"
            />
          </div>

          {/* Actions */}
          <div className="mt-4 flex gap-3">
            <button
              onClick={handleSave}
              disabled={saving || !title.trim()}
              className="rounded-md bg-atlas-600 px-4 py-2 text-sm font-medium text-white hover:bg-atlas-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Scenario"}
            </button>
            <button
              onClick={handleReset}
              className="rounded-md border border-white/[0.06] px-4 py-2 text-sm font-medium text-ink-300 hover:border-white/[0.12]"
            >
              Reset
            </button>
          </div>
          {savedId && (
            <p className="mt-2 text-sm text-positive">
              Saved! <a href={`/scenarios/${savedId}`} className="underline">View saved scenario</a>
            </p>
          )}
          {error && <p className="mt-2 text-sm text-danger">{error}</p>}
        </div>

        {/* Right: Impact Analysis */}
        <div className="flex-1 p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-400">
            Scenario Impact Analysis
          </h2>
          <p className="mt-1 text-xs text-ink-400">
            Deterministic calculation &middot; Live update on slider change
          </p>

          {impactsLoading && <p className="mt-4 text-sm text-ink-400">Computing...</p>}

          {!hasNonZeroShock(shocks) && !impactsLoading && (
            <p className="mt-4 text-sm text-ink-400">
              Move a slider to see impact across all countries.
            </p>
          )}

          {impacts && !impactsLoading && (
            <div className="mt-4 space-y-3">
              {impacts.map((impact) => (
                <ImpactCard key={impact.iso3} impact={impact} fxValue={debouncedShocks.fx_depreciation} />
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
