interface ExportItem {
  rank: number;
  commodity_code: string;
  commodity_label: string;
  value_usd: number;
  share_pct: number;
}

interface ImportSource {
  rank: number;
  partner_iso3: string;
  partner_name: string;
  value_usd: number;
  share_pct: number;
}

interface TradePartner {
  rank: number;
  partner_iso3: string;
  partner_name: string;
  exports_usd: number;
  imports_usd: number;
  total_usd: number;
}

interface EconomicStructure {
  year: number;
  diversification_score: number | null;
  diversification_hhi: number | null;
  commodity_dependency_pct: number | null;
  exports_total_usd: number;
  imports_total_usd: number;
  top_exports: ExportItem[];
  top_import_sources: ImportSource[];
  top_trade_partners: TradePartner[];
}

interface EconomicStructureTabProps {
  data: EconomicStructure | null;
  countryName: string;
}

function formatUsd(value: number): string {
  if (value >= 1e9) return `USD ${(value / 1e9).toFixed(2)}bn`;
  if (value >= 1e6) return `USD ${(value / 1e6).toFixed(0)}M`;
  return `USD ${value.toLocaleString()}`;
}

function formatUsdShort(value: number): string {
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}bn`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(0)}M`;
  return value.toLocaleString();
}

function divLabel(score: number): { text: string; color: string } {
  if (score >= 85) return { text: "Highly diversified", color: "text-green-500" };
  if (score >= 70) return { text: "Moderate", color: "text-amber-500" };
  if (score >= 50) return { text: "Concentrated", color: "text-orange-500" };
  return { text: "Highly concentrated", color: "text-red-500" };
}

function depLabel(pct: number): { text: string; color: string } {
  if (pct <= 30) return { text: "Low", color: "text-green-500" };
  if (pct <= 50) return { text: "Moderate", color: "text-amber-500" };
  if (pct <= 75) return { text: "High", color: "text-orange-500" };
  return { text: "Very high", color: "text-red-500" };
}

function scoreColor(score: number): string {
  if (score >= 85) return "text-green-500";
  if (score >= 70) return "text-amber-500";
  if (score >= 50) return "text-orange-500";
  return "text-red-500";
}

export default function EconomicStructureTab({ data, countryName }: EconomicStructureTabProps) {
  if (!data) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.03] py-16">
        <p className="text-sm text-ink-500">
          Economic structure data not yet available for {countryName}. Comtrade reporting may be delayed.
        </p>
      </div>
    );
  }

  const div = data.diversification_score != null ? divLabel(data.diversification_score) : null;
  const dep = data.commodity_dependency_pct != null ? depLabel(data.commodity_dependency_pct) : null;

  return (
    <div className="space-y-6">
      {/* Summary card */}
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-ink-100">Economic Structure</h3>
          <span className="text-xs text-ink-500">Data as of {data.year}</span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-6 md:grid-cols-4">
          {data.diversification_score != null && div && (
            <div>
              <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Diversification</p>
              <p className={`mt-1 text-2xl font-semibold tabular-nums ${scoreColor(data.diversification_score)}`}>
                {data.diversification_score}<span className="text-sm text-ink-500">/100</span>
              </p>
              <p className={`text-xs ${div.color}`}>{div.text}</p>
              {data.diversification_hhi != null && (
                <p className="text-[10px] text-ink-500">HHI: {data.diversification_hhi.toLocaleString()}</p>
              )}
            </div>
          )}

          {data.commodity_dependency_pct != null && dep && (
            <div>
              <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Commodity Dependency</p>
              <p className={`mt-1 text-2xl font-semibold tabular-nums ${dep.color}`}>
                {Number(data.commodity_dependency_pct).toFixed(0)}%
              </p>
              <p className={`text-xs ${dep.color}`}>{dep.text} (HS 01-27)</p>
            </div>
          )}

          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Exports</p>
            <p className="mt-1 text-xl font-semibold tabular-nums text-ink-100">
              {formatUsd(data.exports_total_usd)}
            </p>
          </div>

          <div>
            <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">Imports</p>
            <p className="mt-1 text-xl font-semibold tabular-nums text-ink-100">
              {formatUsd(data.imports_total_usd)}
            </p>
          </div>
        </div>
      </div>

      {/* Exports + Import Sources */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Top Exports */}
        <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-6">
          <h4 className="mb-4 text-sm font-semibold text-ink-300">Top Exports</h4>
          <div className="space-y-3">
            {data.top_exports.map((item) => (
              <div key={item.commodity_code}>
                <div className="flex items-center justify-between text-sm">
                  <span className="truncate text-ink-200" title={item.commodity_label}>
                    {item.commodity_label.length > 30 ? item.commodity_label.slice(0, 30) + "..." : item.commodity_label}
                  </span>
                  <span className="ml-2 shrink-0 tabular-nums text-ink-400">{Number(item.share_pct).toFixed(1)}%</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-white/[0.06]">
                  <div
                    className="h-full rounded-full bg-amber-500/80"
                    style={{ width: `${Math.min(item.share_pct, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Import Sources */}
        <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-6">
          <h4 className="mb-4 text-sm font-semibold text-ink-300">Top Import Sources</h4>
          <div className="space-y-3">
            {data.top_import_sources.map((item) => (
              <div key={item.partner_iso3}>
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="flex h-5 w-7 items-center justify-center rounded bg-ink-700 text-[9px] font-semibold text-ink-300">
                      {item.partner_iso3}
                    </span>
                    <span className="text-ink-200">{item.partner_name}</span>
                  </div>
                  <span className="ml-2 shrink-0 tabular-nums text-ink-400">{Number(item.share_pct).toFixed(1)}%</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-white/[0.06]">
                  <div
                    className="h-full rounded-full bg-amber-500/80"
                    style={{ width: `${Math.min(item.share_pct * 2.5, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top Trade Partners */}
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-6">
        <h4 className="mb-4 text-sm font-semibold text-ink-300">Top Trade Partners</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/[0.06] text-left text-[11px] uppercase tracking-wider text-ink-500">
                <th className="pb-2 pr-4">Rank</th>
                <th className="pb-2 pr-4">Partner</th>
                <th className="pb-2 pr-4 text-right">Exports</th>
                <th className="pb-2 pr-4 text-right">Imports</th>
                <th className="pb-2 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.top_trade_partners.map((p) => (
                <tr key={p.partner_iso3} className="border-b border-white/[0.03] transition-colors hover:bg-white/[0.02]">
                  <td className="py-2.5 pr-4 text-ink-500">{p.rank}</td>
                  <td className="py-2.5 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="flex h-5 w-7 items-center justify-center rounded bg-ink-700 text-[9px] font-semibold text-ink-300">
                        {p.partner_iso3}
                      </span>
                      <span className="text-ink-200">{p.partner_name}</span>
                    </div>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums text-ink-300">{formatUsdShort(p.exports_usd)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums text-ink-300">{formatUsdShort(p.imports_usd)}</td>
                  <td className="py-2.5 text-right tabular-nums font-medium text-ink-100">{formatUsdShort(p.total_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
