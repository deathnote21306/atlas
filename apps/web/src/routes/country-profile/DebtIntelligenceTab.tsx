import { useState } from "react";
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle, ArrowRight } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  PieChart,
  Pie,
  ResponsiveContainer,
} from "recharts";
import type { ValueType } from "recharts/types/component/DefaultTooltipContent";

interface DebtHeadline {
  debt_gdp_pct: number | null;
  external_debt_gni_pct: number | null;
  debt_service_exports_pct: number | null;
}

interface DebtComposition {
  domestic_pct: number;
  external_pct: number;
  currency: { usd: number; eur: number; local: number; other: number };
  fixed_pct: number;
  variable_pct: number;
}

interface DebtMaturity {
  lt1yr_pct: number;
  yr1_3_pct: number;
  yr3_5_pct: number;
  gt5yr_pct: number;
  wall_year: number | null;
}

interface DebtFlags {
  high_fx_exposure: boolean;
  near_term_maturity_wall: boolean;
  market_access_restricted: boolean;
  restructuring_overhang: boolean;
}

interface DebtProfile {
  vintage: string;
  source: string;
  headline: DebtHeadline;
  composition: DebtComposition;
  maturity: DebtMaturity;
  flags: DebtFlags;
  ai_commentary: string | null;
}

interface DebtIntelligenceTabProps {
  iso3: string;
  data: DebtProfile | null;
}

function MetricCard({ label, value, suffix }: { label: string; value: number | null; suffix: string }) {
  return (
    <div className="rounded-lg bg-[#161b22] p-5">
      <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums text-ink-100">
        {value != null ? `${value}${suffix}` : "—"}
      </p>
    </div>
  );
}

function FlagRow({ label, active, danger }: { label: string; active: boolean; danger: boolean }) {
  const icon = active
    ? <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
    : <CheckCircle className="h-4 w-4 shrink-0 text-green-500" />;
  return (
    <div className="flex items-center gap-3 py-2">
      {icon}
      <span className={`text-sm ${active && danger ? "text-amber-400" : "text-ink-300"}`}>
        {label}
      </span>
    </div>
  );
}

const CURRENCY_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#6b7280"];

export default function DebtIntelligenceTab({ iso3, data }: DebtIntelligenceTabProps) {
  const [commentaryOpen, setCommentaryOpen] = useState(true);

  if (!data) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-[#161b22] py-16">
        <p className="text-sm text-ink-500">Debt profile not yet available for this country</p>
      </div>
    );
  }

  const maturityData = [
    { label: "<1yr", pct: data.maturity.lt1yr_pct },
    { label: "1–3yr", pct: data.maturity.yr1_3_pct },
    { label: "3–5yr", pct: data.maturity.yr3_5_pct },
    { label: ">5yr", pct: data.maturity.gt5yr_pct },
  ];

  const currencyData = [
    { name: "USD", value: data.composition.currency.usd },
    { name: "EUR", value: data.composition.currency.eur },
    { name: "Local", value: data.composition.currency.local },
    { name: "Other", value: data.composition.currency.other },
  ];

  return (
    <div className="space-y-4">
      {/* Headline metrics */}
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Debt / GDP" value={data.headline.debt_gdp_pct} suffix="%" />
        <MetricCard label="Ext. Debt / GNI" value={data.headline.external_debt_gni_pct} suffix="%" />
        <MetricCard label="Debt Service / Exports" value={data.headline.debt_service_exports_pct} suffix="%" />
      </div>

      {/* AI Commentary */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <button
          onClick={() => setCommentaryOpen((o) => !o)}
          aria-expanded={commentaryOpen}
          aria-label="Toggle AI Commentary"
          className="flex w-full items-center justify-between text-left"
        >
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">AI Commentary</p>
          {commentaryOpen
            ? <ChevronUp className="h-4 w-4 text-ink-500" />
            : <ChevronDown className="h-4 w-4 text-ink-500" />}
        </button>
        {commentaryOpen && (
          <p className="mt-3 max-w-prose text-sm leading-relaxed text-ink-300">
            {data.ai_commentary ?? "Commentary will be generated in the next nightly run."}
          </p>
        )}
      </div>

      {/* Composition */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Composition</p>
        <div className="mt-4 grid grid-cols-2 gap-6">
          {/* Domestic / External */}
          <div>
            <p className="mb-2 text-xs text-ink-500">Domestic / External</p>
            <div className="flex h-3 w-full overflow-hidden rounded-full">
              <div className="bg-blue-500" style={{ width: `${data.composition.domestic_pct}%` }} />
              <div className="bg-purple-500" style={{ width: `${data.composition.external_pct}%` }} />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-ink-400">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
                Domestic {data.composition.domestic_pct}%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-purple-500" />
                External {data.composition.external_pct}%
              </span>
            </div>
          </div>

          {/* Fixed / Variable */}
          <div>
            <p className="mb-2 text-xs text-ink-500">Fixed / Variable Rate</p>
            <div className="flex h-3 w-full overflow-hidden rounded-full">
              <div className="bg-green-500" style={{ width: `${data.composition.fixed_pct}%` }} />
              <div className="bg-amber-500" style={{ width: `${data.composition.variable_pct}%` }} />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-ink-400">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                Fixed {data.composition.fixed_pct}%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-amber-500" />
                Variable {data.composition.variable_pct}%
              </span>
            </div>
          </div>
        </div>

        {/* Currency mix */}
        <p className="mt-5 text-xs text-ink-500">Currency Mix</p>
        <div className="mt-2 flex items-center gap-6">
          <ResponsiveContainer width={100} height={100}>
            <PieChart>
              <Pie data={currencyData} dataKey="value" cx="50%" cy="50%" outerRadius={45} strokeWidth={0}>
                {currencyData.map((_, i) => (
                  <Cell key={i} fill={CURRENCY_COLORS[i % CURRENCY_COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
            {currencyData.map((d, i) => (
              <span key={d.name} className="flex items-center gap-1.5 text-xs text-ink-400">
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ background: CURRENCY_COLORS[i % CURRENCY_COLORS.length] }}
                />
                {d.name} {d.value}%
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Maturity profile */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <div className="flex items-start justify-between">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Maturity Profile</p>
          {data.maturity.wall_year && (
            <span className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
              Wall: {data.maturity.wall_year}
            </span>
          )}
        </div>
        <div className="mt-4">
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={maturityData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="label" tick={{ fill: "#6b7280", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
              <Tooltip
                contentStyle={{ background: "#0d1117", border: "1px solid #21262d", borderRadius: 6 }}
                labelStyle={{ color: "#e6edf3" }}
                formatter={(v: ValueType | undefined) => [`${v ?? "—"}%`, "Share"]}
              />
              <Bar dataKey="pct" radius={[3, 3, 0, 0]}>
                {maturityData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={entry.label === "<1yr" && data.flags.near_term_maturity_wall ? "#f59e0b" : "#3b82f6"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Vulnerability flags */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Vulnerability Flags</p>
        <div className="mt-3 divide-y divide-[#21262d]">
          <FlagRow label="High FX Exposure" active={data.flags.high_fx_exposure} danger />
          <FlagRow label="Near-Term Maturity Wall" active={data.flags.near_term_maturity_wall} danger />
          <FlagRow label="Market Access Restricted" active={data.flags.market_access_restricted} danger />
          <FlagRow label="Restructuring Overhang" active={data.flags.restructuring_overhang} danger />
        </div>
      </div>

      {/* Scenario CTA */}
      <div className="rounded-lg border border-[#21262d] bg-[#0d1117] p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-ink-100">Run Debt Shock Scenario</p>
            <p className="mt-0.5 text-xs text-ink-500">
              Model the impact of FX depreciation or rate spikes on this debt profile
            </p>
          </div>
          <a
            href={`?tab=scenarios&iso3=${iso3}`}
            className="flex items-center gap-1.5 rounded-md border border-[#30363d] bg-[#161b22] px-3 py-1.5 text-xs font-medium text-ink-200 hover:border-blue-500/50 hover:text-blue-400"
          >
            Open Scenarios
            <ArrowRight className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      {/* Data source footer */}
      <p className="text-center text-[10px] text-ink-500">
        Source: {data.source} · Vintage: {data.vintage}
      </p>
    </div>
  );
}
