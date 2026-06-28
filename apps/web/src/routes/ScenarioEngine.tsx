import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { toast } from "../components/Toast";
import AppShell from "./AppShell";

const C = "rounded-lg bg-[#161b22]";

/* ── Types ── */

interface ScenarioDeltas { debt_gdp: number; fiscal_balance: number; current_account: number; }
interface CountryImpact { iso3: string; name: string; status: string; baseline_risk: number; new_risk: number; risk_change: number; deltas: ScenarioDeltas; distress_probability: number | null; }
interface ShockVector { gdp_shock: number; inflation_shock: number; fx_depreciation: number; rate_shock: number; commodity_shock: number; }
interface SavedScenario { id: string; iso3: string; title?: string; description?: string | null; shocks: ShockVector; created_at: string; saved?: boolean; }

/* ── Slider config ── */

const DEFAULT_SHOCKS: ShockVector = { gdp_shock: 0, inflation_shock: 0, fx_depreciation: 0, rate_shock: 0, commodity_shock: 0 };

const SLIDERS: { key: keyof ShockVector; label: string; sub: string; min: number; max: number; step: number; unit: string; valueFn?: (v: number) => string }[] = [
  { key: "commodity_shock", label: "Brent Crude Price", sub: "USD per barrel spot price", min: -50, max: 50, step: 1, unit: "USD/bbl", valueFn: (v) => `${(70 + (v * 70) / 100).toFixed(0)}` },
  { key: "gdp_shock", label: "Global GDP Growth", sub: "IMF global growth forecast delta", min: -3, max: 2, step: 0.1, unit: "pp" },
  { key: "rate_shock", label: "EM Spread Widening", sub: "Average EM sovereign spread increase", min: 0, max: 3, step: 0.25, unit: "bps", valueFn: (v) => `${(v * 100).toFixed(0)}` },
  { key: "fx_depreciation", label: "USD Appreciation", sub: "USD DXY index change", min: -10, max: 20, step: 0.5, unit: "%" },
  { key: "inflation_shock", label: "Global Trade Volume Delta", sub: "Change in global trade volumes", min: -10, max: 5, step: 0.5, unit: "pp" },
];

/* ── Helpers ── */

function formatAge(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (d < 1) return "just now";
  if (d < 7) return `${d}d ago`;
  return `${Math.floor(d / 7)}w ago`;
}
function hasNonZero(s: ShockVector) { return Object.values(s).some((v) => v !== 0); }

function severityBadge(risk: number) {
  if (risk >= 75) return { label: "CRITICAL", cls: "bg-red-500/20 text-red-400" };
  if (risk >= 60) return { label: "HIGH", cls: "bg-orange-500/20 text-orange-400" };
  if (risk >= 45) return { label: "MEDIUM", cls: "bg-amber-500/20 text-amber-400" };
  return { label: "LOW", cls: "bg-green-500/20 text-green-400" };
}
function changeColor(v: number) { return v > 0 ? "text-red-400" : v < 0 ? "text-green-400" : "text-ink-400"; }
function metricColor(v: number) { return v < 0 ? "text-red-400" : v > 0 ? "text-green-400" : "text-ink-400"; }

function categoryOf(title: string): { label: string; color: string } {
  const t = (title ?? "").toLowerCase();
  if (t.includes("oil") || t.includes("brent") || t.includes("commodity")) return { label: "COMMODITY SHOCK", color: "bg-green-500" };
  if (t.includes("capital") || t.includes("fx") || t.includes("flow")) return { label: "FX / CAPITAL FLOW", color: "bg-blue-500" };
  if (t.includes("tariff") || t.includes("rate") || t.includes("trade")) return { label: "RATES / TARIFF", color: "bg-purple-500" };
  return { label: "SCENARIO", color: "bg-amber-500" };
}

function impactNarrative(impact: CountryImpact): string {
  const { name, risk_change, deltas } = impact;
  const s = (v: number) => v >= 0 ? "+" : "";
  const f = `${s(deltas.fiscal_balance)}${deltas.fiscal_balance.toFixed(1)}pp`;
  const e = `${s(deltas.current_account)}${deltas.current_account.toFixed(1)}pp`;
  const d = `${s(deltas.debt_gdp)}${deltas.debt_gdp.toFixed(1)}pp`;
  const fiscalVerb = deltas.fiscal_balance >= 0 ? "improves" : "deteriorates";
  const debtVerb = deltas.debt_gdp <= 0 ? "declines" : "rises";

  if (risk_change > 10) return `${name} severely impacted. Fiscal balance ${fiscalVerb} ${f}, external position ${e}. Debt-to-GDP ${debtVerb} ${d}. Without compensatory policy action, debt sustainability deteriorates materially and financing costs are likely to spike.`;
  if (risk_change > 5) return `${name} significantly impacted — fiscal balance ${fiscalVerb} ${f}, external ${e}. Debt ratio ${debtVerb} ${d}. Existing buffers partially absorb the shock but fiscal discipline weakens under sustained pressure.`;
  if (risk_change > 0) return `${name} moderately affected. Fiscal balance ${fiscalVerb} ${f}, external ${e}. Debt-to-GDP ${debtVerb} ${d}. Macro fundamentals absorb some of the shock but risk profile edges higher.`;
  if (risk_change < -5) {
    if (deltas.fiscal_balance >= 0) return `${name} benefits materially — fiscal balance ${fiscalVerb} ${f}, external ${e}. Debt ratio ${debtVerb} ${d}. Improved terms of trade reinforce a positive fiscal trajectory.`;
    return `${name} sees overall risk reduction despite fiscal headwinds. Fiscal balance ${fiscalVerb} ${f}, external ${e}. Debt ${debtVerb} ${d}. Risk decline driven by external and monetary stabilisation rather than fiscal improvement.`;
  }
  if (risk_change < 0) {
    if (deltas.fiscal_balance >= 0) return `${name} sees mild improvement. Fiscal balance ${fiscalVerb} ${f}, external ${e}. Net positive effect on public finances under this scenario.`;
    return `${name} sees mild overall improvement despite fiscal pressure of ${f}. External and debt dynamics partially offset the headwind.`;
  }
  return `Limited impact on ${name}. Fiscal ${f}, external ${e}. Country fundamentals remain largely unchanged under this scenario.`;
}

/* ── Impact Card ── */

function ImpactCard({ impact, fxValue, shocks, aiNarrative, aiLoading }: {
  impact: CountryImpact; fxValue: number; shocks: ShockVector;
  aiNarrative: string | null; aiLoading: boolean;
}) {
  const badge = severityBadge(impact.new_risk);
  const sign = impact.risk_change > 0 ? "+" : "";

  return (
    <div className={`${C} p-4`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[14px] font-semibold text-ink-100">{impact.name}</span>
          <span className={`rounded px-1.5 py-0.5 text-[9px] font-bold ${badge.cls}`}>{badge.label}</span>
        </div>
        <span className={`text-[14px] font-bold tabular-nums ${changeColor(impact.risk_change)}`}>
          {sign}{impact.risk_change.toFixed(1)} risk pts
        </span>
      </div>
      <div className="mt-3 grid grid-cols-4 gap-3 text-center">
        {[
          { label: "GDP (pp)", v: impact.deltas.debt_gdp },
          { label: "Fiscal (pp)", v: impact.deltas.fiscal_balance },
          { label: "External (pp)", v: impact.deltas.current_account },
          { label: "FX (%)", v: fxValue },
        ].map((cell) => (
          <div key={cell.label}>
            <div className="text-[10px] text-ink-500">{cell.label}</div>
            <div className={`text-[14px] font-bold tabular-nums ${metricColor(cell.v)}`}>
              {cell.v >= 0 ? "+" : ""}{cell.v.toFixed(1)}
            </div>
          </div>
        ))}
      </div>
      {aiLoading && !aiNarrative ? (
        <p className="mt-3 text-[11px] text-ink-600 italic animate-pulse">Generating analyst note...</p>
      ) : aiNarrative ? (
        <div className="mt-3">
          <p className="text-[11px] leading-relaxed text-ink-400">{aiNarrative}</p>
          <span className="mt-1 inline-block text-[9px] text-indigo-500/60">✦ AI</span>
        </div>
      ) : (
        <p className="mt-3 text-[11px] leading-relaxed text-ink-500">{impactNarrative(impact)}</p>
      )}
    </div>
  );
}

/* ── Scenario Library Sidebar ── */

function Library({ scenarios, activeId, onSelect, onNew }: { scenarios: SavedScenario[]; activeId: string | null; onSelect: (id: string) => void; onNew: () => void }) {
  const groups = new Map<string, SavedScenario[]>();
  for (const s of scenarios) {
    const cat = categoryOf(s.title ?? "").label;
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat)!.push(s);
  }

  return (
    <aside className="w-64 shrink-0 border-r border-[#21262d] bg-[#0d1117] p-4 overflow-y-auto">
      <h2 className="text-[10px] font-semibold uppercase tracking-wider text-ink-500">Scenario Library</h2>
      <button onClick={onNew} className="mt-3 w-full rounded-md border border-[#30363d] py-2.5 text-sm text-ink-300 hover:bg-[#161b22]">
        + New Scenario
      </button>
      <div className="mt-4 space-y-4">
        {Array.from(groups.entries()).map(([cat, items]) => {
          const catInfo = categoryOf(items[0].title ?? "");
          return (
            <div key={cat}>
              <div className="mb-2 flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${catInfo.color}`} />
                <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-500">{cat}</span>
              </div>
              {items.map((s) => (
                <button
                  key={s.id}
                  onClick={() => onSelect(s.id)}
                  className={`mb-1 w-full rounded-lg p-3 text-left transition ${activeId === s.id ? "bg-[#1c2535] border border-blue-500/30" : "hover:bg-[#161b22]"}`}
                >
                  <div className="text-[12px] font-medium text-ink-200 truncate">{s.title || "Untitled"}</div>
                  <div className="mt-1 flex items-center gap-2 text-[10px]">
                    <span className="rounded bg-green-500/10 px-1.5 py-0.5 text-green-400">saved</span>
                    <span className="text-ink-500">{formatAge(s.created_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </aside>
  );
}

/* ── Main ── */

export default function ScenarioEngine() {
  const navigate = useNavigate();
  const [shocks, setShocks] = useState<ShockVector>({ ...DEFAULT_SHOCKS });
  const [debouncedShocks, setDebouncedShocks] = useState<ShockVector>({ ...DEFAULT_SHOCKS });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [impacts, setImpacts] = useState<CountryImpact[] | null>(null);
  const [impactsLoading, setImpactsLoading] = useState(false);
  const [aiNarratives, setAiNarratives] = useState<Record<string, string> | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>([]);
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>(null);
  const [mode, setMode] = useState<"manual" | "ai">("manual");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setDebouncedShocks({ ...shocks }), 300);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [shocks]);

  useEffect(() => {
    api<SavedScenario[]>("/api/scenarios").then(setSavedScenarios).catch(() => {});
  }, []);

  const fetchPreview = useCallback(async (s: ShockVector) => {
    if (!hasNonZero(s)) { setImpacts(null); setAiNarratives(null); return; }
    setImpactsLoading(true);
    setAiNarratives(null);
    try {
      const result = await api<CountryImpact[]>("/api/scenarios/preview-all", { method: "POST", body: JSON.stringify({ shocks: s }) });
      setImpacts(result);
    } catch { /* ignore */ } finally { setImpactsLoading(false); }
  }, []);

  const fetchAiNarratives = useCallback(async (s: ShockVector, imp: CountryImpact[]) => {
    setAiLoading(true);
    try {
      const result = await api<Record<string, string>>("/api/scenarios/narratives", {
        method: "POST",
        body: JSON.stringify({ shocks: s, impacts: imp }),
      });
      setAiNarratives(result);
    } catch { toast.error("AI narratives unavailable"); } finally { setAiLoading(false); }
  }, []);

  useEffect(() => { fetchPreview(debouncedShocks); }, [debouncedShocks, fetchPreview]);

  // Auto-fetch AI narratives when switching to AI mode if impacts already loaded
  useEffect(() => {
    if (mode === "ai" && impacts && !aiNarratives && !aiLoading) {
      fetchAiNarratives(debouncedShocks, impacts);
    }
  }, [mode, impacts, aiNarratives, aiLoading, debouncedShocks, fetchAiNarratives]);

  const handleSlider = (key: keyof ShockVector, value: number) => { setShocks((p) => ({ ...p, [key]: value })); setSavedId(null); setAiNarratives(null); };

  const handleSave = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const result = await api<{ id: string }>("/api/scenarios", { method: "POST", body: JSON.stringify({ iso3: "ALL", shocks, title: title.trim(), description: description.trim() || null }) });
      setSavedId(result.id);
      toast.success("Scenario saved");
      const updated = await api<SavedScenario[]>("/api/scenarios");
      setSavedScenarios(updated);
    } catch { toast.error("Failed to save"); } finally { setSaving(false); }
  };

  const handleReset = () => { setShocks({ ...DEFAULT_SHOCKS }); setTitle(""); setDescription(""); setSavedId(null); setActiveScenarioId(null); };

  const handleSelect = (id: string) => {
    const s = savedScenarios.find((x) => x.id === id);
    if (s) {
      setShocks(s.shocks);
      setTitle(s.title ?? "");
      setDescription(s.description ?? "");
      setActiveScenarioId(id);
      setSavedId(id);
    } else {
      navigate(`/scenarios/${id}`);
    }
  };

  const cat = categoryOf(title);

  return (
    <AppShell>
      <div className="flex min-h-[calc(100vh-3rem)]">

        {/* ── Left: Scenario Library ── */}
        <Library scenarios={savedScenarios} activeId={activeScenarioId} onSelect={handleSelect} onNew={handleReset} />

        {/* ── Center: Scenario Detail + Variables ── */}
        <div className="w-[420px] shrink-0 overflow-y-auto border-r border-[#21262d] p-6">

          {/* Scenario header */}
          <div className="mb-5">
            <div className="flex items-center gap-2 mb-2">
              {title && <span className={`rounded px-2 py-0.5 text-[9px] font-bold uppercase ${cat.label.includes("COMMODITY") ? "bg-amber-500/15 text-amber-400" : cat.label.includes("FX") ? "bg-blue-500/15 text-blue-400" : "bg-purple-500/15 text-purple-400"}`}>{cat.label}</span>}
              {savedId && <span className="rounded bg-green-500/10 px-2 py-0.5 text-[9px] font-bold text-green-400">saved</span>}
            </div>
            <div
              className={`rounded-lg px-3 py-2.5 transition-all duration-300 ${
                !title
                  ? "border border-blue-500/40 bg-blue-500/5 shadow-[0_0_12px_rgba(59,130,246,0.15)] animate-pulse"
                  : "border border-transparent bg-transparent"
              }`}
            >
              {!title && (
                <p className="text-[9px] font-semibold uppercase tracking-wider text-blue-400/70 mb-1.5">
                  Name your scenario
                </p>
              )}
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Oil crash + EM spread widening"
                className="w-full text-[18px] font-semibold text-ink-100 bg-transparent border-none outline-none placeholder:text-ink-600"
              />
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe the thesis — what's driving this shock and why it matters..."
                rows={2}
                className="mt-1 w-full text-[12px] text-ink-400 bg-transparent border-none outline-none resize-none placeholder:text-ink-600"
              />
            </div>
          </div>

          {/* Variables header */}
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-ink-500">⚙</span>
              <span className="text-[13px] font-semibold text-ink-200">Scenario Variables</span>
            </div>
            <span className="text-[10px] text-ink-500">Manual Control</span>
          </div>

          {/* Sliders */}
          <div className="space-y-5">
            {SLIDERS.map((cfg) => {
              const val = shocks[cfg.key];
              const display = cfg.valueFn ? cfg.valueFn(val) : (val >= 0 ? `${val.toFixed(1)}` : val.toFixed(1));
              return (
                <div key={cfg.key}>
                  <div className="flex items-baseline justify-between">
                    <div>
                      <div className="text-[13px] font-medium text-ink-200">{cfg.label}</div>
                      <div className="text-[10px] text-ink-500">{cfg.sub}</div>
                    </div>
                    <span className="text-[16px] font-bold tabular-nums text-amber-400">
                      {display} <span className="text-[12px] font-normal text-ink-500">{cfg.unit}</span>
                    </span>
                  </div>
                  <input
                    type="range"
                    min={cfg.min}
                    max={cfg.max}
                    step={cfg.step}
                    value={val}
                    onChange={(e) => handleSlider(cfg.key, parseFloat(e.target.value))}
                    className="mt-2 w-full accent-amber-500"
                    style={{ height: 6 }}
                  />
                  <div className="mt-1 flex justify-between text-[10px] text-ink-600">
                    <span>{cfg.min} {cfg.unit}</span>
                    <span>{cfg.max} {cfg.unit}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer note */}
          <p className="mt-6 text-[10px] text-ink-600">
            <strong className="text-ink-500">Deterministic engine:</strong> Impact calculations are rule-based. AI proposes only — deterministic model calculates.
          </p>

          {/* Save button */}
          <div className="mt-4 flex gap-2">
            <button onClick={handleSave} disabled={saving || !title.trim()} className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40">
              {saving ? "Saving..." : "Save"}
            </button>
            <button onClick={handleReset} className="rounded-md border border-[#30363d] px-4 py-2 text-sm text-ink-400 hover:bg-[#161b22]">
              Reset
            </button>
          </div>
        </div>

        {/* ── Right: Impact Analysis ── */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-ink-500">📊</span>
              <span className="text-[13px] font-semibold text-ink-200">Scenario Impact Analysis</span>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => setMode("manual")} className={`text-[11px] font-medium ${mode === "manual" ? "text-ink-200" : "text-ink-500"}`}>⚙ Manual</button>
              <button
                onClick={() => {
                  setMode("ai");
                  if (impacts && !aiNarratives && !aiLoading) fetchAiNarratives(debouncedShocks, impacts);
                }}
                className={`text-[11px] font-medium ${mode === "ai" ? "text-indigo-400" : "text-ink-500"}`}
              >
                ✦ AI-Assisted
              </button>
              {mode === "ai" && aiNarratives && (
                <button
                  onClick={() => impacts && fetchAiNarratives(debouncedShocks, impacts)}
                  disabled={aiLoading}
                  className="text-[11px] font-medium text-ink-500 hover:text-ink-300 disabled:opacity-40"
                >
                  ↺ Regenerate
                </button>
              )}
              <button onClick={handleSave} disabled={!title.trim()} className="text-[11px] font-medium text-ink-500 hover:text-ink-300 disabled:opacity-40">💾 Save</button>
            </div>
          </div>
          <p className="text-[10px] text-ink-500 mb-4">
            {mode === "ai" ? "AI-generated analyst narratives · Deterministic risk calculations" : "Deterministic calculation · Live update on slider change"}
          </p>

          {impactsLoading && <p className="text-sm text-ink-400">Computing impact...</p>}

          {!hasNonZero(shocks) && !impactsLoading && (
            <div className={`${C} p-8 text-center`}>
              <p className="text-sm text-ink-400">Move a slider to see impact across all countries.</p>
            </div>
          )}

          {impacts && !impactsLoading && (
            <div className="space-y-3">
              {impacts.map((impact) => (
                <ImpactCard
                  key={impact.iso3}
                  impact={impact}
                  fxValue={debouncedShocks.fx_depreciation}
                  shocks={debouncedShocks}
                  aiNarrative={mode === "ai" ? (aiNarratives?.[impact.iso3] ?? null) : null}
                  aiLoading={mode === "ai" && aiLoading}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
