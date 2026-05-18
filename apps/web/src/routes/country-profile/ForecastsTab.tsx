interface YearForecast {
  year: number;
  current_value: number | null;
  bull: number | null;
  baseline: number | null;
  bear: number | null;
  source: string;
  bull_clamped: boolean;
  bear_clamped: boolean;
  baseline_provenance: string;
}

interface ForecastIndicator {
  key: string;
  label: string;
  unit: string;
  direction: string;
  base_width: number;
  years: YearForecast[];
}

interface ForecastsData {
  horizon_years: number[];
  current_year: number;
  methodology_version: string;
  methodology_note: string;
  risk_multiplier: number;
  indicators: ForecastIndicator[];
}

interface ForecastsTabProps {
  data: ForecastsData | null;
  countryName: string;
}

function fmtVal(v: number | null, unit: string): string {
  if (v == null) return "\u2014";
  return `${v.toFixed(1)}${unit === "%" ? "%" : ""}`;
}

export default function ForecastsTab({ data, countryName }: ForecastsTabProps) {
  if (!data) {
    return (
      <div className="flex items-center justify-center rounded-lg bg-[#161b22] py-16">
        <p className="text-sm text-ink-500">Forecasts temporarily unavailable for {countryName}</p>
      </div>
    );
  }

  const hasClamped = data.indicators.some((ind) =>
    ind.years.some((y) => y.bull_clamped || y.bear_clamped),
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-ink-100">
          ATLAS Forecasts &mdash; {data.current_year}
        </h3>
        <div className="flex items-center gap-4 text-[11px] uppercase tracking-wider text-ink-500">
          <span>Baseline</span>
          <span className="text-green-500">Bull Case</span>
          <span className="text-red-500">Bear Case</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-lg bg-[#161b22]">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[#161b22] text-left text-[11px] uppercase tracking-wider text-ink-500">
                <th className="px-4 py-3">Indicator</th>
                <th className="px-4 py-3">Year</th>
                <th className="px-4 py-3 text-right">Current</th>
                <th className="px-4 py-3 text-right">Bull</th>
                <th className="px-4 py-3 text-right">Baseline</th>
                <th className="px-4 py-3 text-right">Bear</th>
                <th className="px-4 py-3">Source</th>
              </tr>
            </thead>
            <tbody>
              {data.indicators.map((ind, indIdx) =>
                ind.years.map((yr, yrIdx) => (
                  <tr
                    key={`${ind.key}-${yr.year}`}
                    className={`border-b border-[#21262d] ${
                      yrIdx === 0 && indIdx > 0 ? "border-t-2 border-t-[#21262d]" : ""
                    }`}
                  >
                    <td className="px-4 py-3 text-ink-200">
                      {yrIdx === 0 ? ind.label : ""}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-ink-400">{yr.year}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-500">
                      {fmtVal(yr.current_value, ind.unit)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-green-500">
                      {yr.bull != null ? (
                        <>
                          {fmtVal(yr.bull, ind.unit)}
                          {yr.bull_clamped && <sup className="text-[9px] text-ink-500">&dagger;</sup>}
                        </>
                      ) : (
                        "\u2014"
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium text-ink-100">
                      {fmtVal(yr.baseline, ind.unit)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-red-500">
                      {yr.bear != null ? (
                        <>
                          {fmtVal(yr.bear, ind.unit)}
                          {yr.bear_clamped && <sup className="text-[9px] text-ink-500">&dagger;</sup>}
                        </>
                      ) : (
                        "\u2014"
                      )}
                    </td>
                    <td className="px-4 py-3 text-[11px] text-ink-500">{yr.source}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Clamping footnote */}
      {hasClamped && (
        <p className="text-[11px] text-ink-500">
          &dagger; Value clamped to historical range limits.
        </p>
      )}

      {/* Methodology footer */}
      <p className="max-w-prose text-xs leading-relaxed text-ink-500">
        Provenance: ATLAS forecasts combine IMF WEO baseline with ATLAS proprietary adjustments
        using country-specific risk dimension scores. Bull/bear cases reflect
        &plusmn;base_width &times; risk multiplier {data.risk_multiplier.toFixed(2)} scenario bounds.
        All forecasts are deterministic and reproducible. Methodology {data.methodology_version}.
      </p>
    </div>
  );
}
