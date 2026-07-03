import { useState } from "react";
import { ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
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

// Actual shape coming from the DB (seeded debt_profile JSONB)
interface CurrencyComposition {
  domestic_pct?: number;
  external_pct?: number;
  note?: string;
}

interface MaturityProfile {
  short_term_pct?: number;
  medium_term_pct?: number;
  long_term_pct?: number;
  avg_maturity_years?: number;
}

interface Creditor {
  name: string;
  share_pct: number;
}

interface Issuance {
  type?: string;
  coupon_pct?: number;
  maturity_yr?: number;
  amount_usd_mn?: number;
}

interface DebtProfileRaw {
  total_debt_pct_gdp?: number | null;
  currency_composition?: CurrencyComposition;
  maturity_profile?: MaturityProfile;
  major_creditors?: Creditor[];
  recent_issuance?: Record<string, Issuance>;
  key_risks?: string[];
  ai_commentary?: string | null;
  ai_commentary_model?: string;
  ai_commentary_generated_at?: string;
}

interface DebtIntelligenceTabProps {
  iso3: string;
  data: DebtProfileRaw | null;
}

const CREDITOR_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#6b7280"];

export default function DebtIntelligenceTab({ iso3, data }: DebtIntelligenceTabProps) {
  const [commentaryOpen, setCommentaryOpen] = useState(true);

  if (!data) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-[#161b22] py-16">
        <p className="text-sm text-ink-500">Debt profile not yet available for this country</p>
      </div>
    );
  }

  // Maturity bar chart data
  const maturity = data.maturity_profile ?? {};
  const maturityData = [
    { label: "Short-term", pct: maturity.short_term_pct ?? 0 },
    { label: "Medium-term", pct: maturity.medium_term_pct ?? 0 },
    { label: "Long-term", pct: maturity.long_term_pct ?? 0 },
  ].filter((d) => d.pct > 0);

  // Creditor pie
  const creditors = data.major_creditors ?? [];

  // Recent issuances
  const issuances = Object.entries(data.recent_issuance ?? {});

  const generatedAt = data.ai_commentary_generated_at
    ? new Date(data.ai_commentary_generated_at).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : null;

  return (
    <div className="space-y-4">
      {/* Headline metric */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-[#161b22] p-5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Debt / GDP</p>
          <p className="mt-2 text-3xl font-bold tabular-nums text-ink-100">
            {data.total_debt_pct_gdp != null ? `${data.total_debt_pct_gdp}%` : "—"}
          </p>
        </div>
        <div className="rounded-lg bg-[#161b22] p-5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Avg Maturity</p>
          <p className="mt-2 text-3xl font-bold tabular-nums text-ink-100">
            {maturity.avg_maturity_years != null ? `${maturity.avg_maturity_years}yr` : "—"}
          </p>
        </div>
        <div className="rounded-lg bg-[#161b22] p-5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">External Share</p>
          <p className="mt-2 text-3xl font-bold tabular-nums text-ink-100">
            {data.currency_composition?.external_pct != null
              ? `${data.currency_composition.external_pct}%`
              : "—"}
          </p>
        </div>
      </div>

      {/* AI Commentary */}
      <div className="rounded-lg bg-[#161b22] p-5">
        <button
          onClick={() => setCommentaryOpen((o) => !o)}
          aria-expanded={commentaryOpen}
          className="flex w-full items-center justify-between text-left"
        >
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">
            AI Debt Commentary
            {generatedAt && (
              <span className="ml-2 normal-case text-ink-600">· {generatedAt}</span>
            )}
          </p>
          {commentaryOpen
            ? <ChevronUp className="h-4 w-4 text-ink-500" />
            : <ChevronDown className="h-4 w-4 text-ink-500" />}
        </button>
        {commentaryOpen && (
          <p className="mt-3 max-w-prose text-sm leading-relaxed text-ink-300">
            {data.ai_commentary ?? "Commentary will be generated in the next nightly run."}
          </p>
        )}
        {commentaryOpen && data.ai_commentary_model && (
          <p className="mt-2 text-[10px] text-ink-600">Model: {data.ai_commentary_model}</p>
        )}
      </div>

      {/* Domestic / External split */}
      {data.currency_composition && (
        <div className="rounded-lg bg-[#161b22] p-5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Debt Composition</p>
          <div className="mt-4">
            <p className="mb-2 text-xs text-ink-500">Domestic / External</p>
            <div className="flex h-3 w-full overflow-hidden rounded-full">
              <div
                className="bg-blue-500"
                style={{ width: `${data.currency_composition.domestic_pct ?? 0}%` }}
              />
              <div
                className="bg-purple-500"
                style={{ width: `${data.currency_composition.external_pct ?? 0}%` }}
              />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-ink-400">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
                Domestic {data.currency_composition.domestic_pct ?? 0}%
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-2 rounded-full bg-purple-500" />
                External {data.currency_composition.external_pct ?? 0}%
              </span>
            </div>
            {data.currency_composition.note && (
              <p className="mt-3 text-xs text-ink-500">{data.currency_composition.note}</p>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Maturity profile */}
        {maturityData.length > 0 && (
          <div className="rounded-lg bg-[#161b22] p-5">
            <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Maturity Profile</p>
            <div className="mt-4">
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={maturityData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <XAxis
                    dataKey="label"
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "#6b7280", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    unit="%"
                  />
                  <Tooltip
                    contentStyle={{ background: "#0d1117", border: "1px solid #21262d", borderRadius: 6 }}
                    labelStyle={{ color: "#e6edf3" }}
                    formatter={(v: ValueType | undefined) => [`${v ?? "—"}%`, "Share"]}
                  />
                  <Bar dataKey="pct" radius={[3, 3, 0, 0]}>
                    {maturityData.map((_, i) => (
                      <Cell key={i} fill={i === 0 ? "#f59e0b" : "#3b82f6"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Major creditors */}
        {creditors.length > 0 && (
          <div className="rounded-lg bg-[#161b22] p-5">
            <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Major Creditors</p>
            <div className="mt-4 flex items-center gap-4">
              <ResponsiveContainer width={100} height={100}>
                <PieChart>
                  <Pie
                    data={creditors}
                    dataKey="share_pct"
                    cx="50%"
                    cy="50%"
                    outerRadius={45}
                    strokeWidth={0}
                  >
                    {creditors.map((_, i) => (
                      <Cell key={i} fill={CREDITOR_COLORS[i % CREDITOR_COLORS.length]} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5">
                {creditors.map((c, i) => (
                  <span key={c.name} className="flex items-center gap-1.5 text-xs text-ink-400">
                    <span
                      className="inline-block h-2 w-2 shrink-0 rounded-full"
                      style={{ background: CREDITOR_COLORS[i % CREDITOR_COLORS.length] }}
                    />
                    {c.name} — {c.share_pct}%
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Recent issuances */}
      {issuances.length > 0 && (
        <div className="rounded-lg bg-[#161b22] p-5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Recent Issuance</p>
          <div className="mt-3 space-y-3">
            {issuances.map(([year, iss]) => (
              <div key={year} className="flex items-center justify-between rounded-md border border-[#21262d] px-3 py-2">
                <div>
                  <span className="text-sm font-medium text-ink-100">{year} {iss.type}</span>
                  {iss.amount_usd_mn && (
                    <span className="ml-2 text-xs text-ink-500">
                      USD {(iss.amount_usd_mn / 1000).toFixed(1)}bn
                    </span>
                  )}
                </div>
                <div className="text-right text-xs text-ink-400">
                  {iss.coupon_pct != null && <span>{iss.coupon_pct}% coupon</span>}
                  {iss.maturity_yr && <span className="ml-2">Mat. {iss.maturity_yr}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Key risks */}
      {data.key_risks && data.key_risks.length > 0 && (
        <div className="rounded-lg bg-[#161b22] p-5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Key Debt Risks</p>
          <div className="mt-3 space-y-2">
            {data.key_risks.map((risk, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-ink-300">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                {risk}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
