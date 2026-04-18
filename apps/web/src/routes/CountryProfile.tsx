import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import {
  InstitutionalTable,
  RatingBadge,
  RiskGauge,
  StalenessChip,
  type StalenessState,
} from "@atlas/design-system";
import { ApiError, api } from "../api/client";
import AppShell from "./AppShell";
import { SkeletonLine, SkeletonCard } from "../components/Skeleton";
import SynopsisCard, { type SynopsisData } from "../components/SynopsisCard";
import NewsItemCard, { type NewsItemData } from "../components/NewsItemCard";

interface MacroTile {
  indicator: string;
  label: string;
  value: number | null;
  period: string | null;
  source: string | null;
  staleness: { state: StalenessState; age_days: number | null };
}

interface FxObservation {
  iso3: string;
  ccy: string;
  usd_per_ccy: number;
  observation_date: string;
  source: string;
  ingested_at: string;
}

interface FxDeltas {
  latest: FxObservation;
  delta_1d_pct: number | null;
  delta_7d_pct: number | null;
  delta_30d_pct: number | null;
  delta_ytd_pct: number | null;
}

interface RatingAction {
  iso3: string;
  agency: "S&P" | "Moodys" | "Fitch";
  rating: string;
  outlook: string | null;
  action: string;
  action_date: string;
  source_url: string | null;
}

interface DimensionScore {
  dimension: string;
  score: number;
  rationale: string;
  input_value: number | null;
  is_estimate: boolean;
}

interface CountryBundle {
  country: {
    iso3: string; name: string; capital: string; region: string;
    tags: string[]; tier: string; status: string; fx_regime: string;
    fx_regime_notes: string | null; fx_parallel_premium: number | null;
  };
  macro: MacroTile[];
  fx: FxDeltas | null;
  ratings: {
    latest_per_agency: Record<string, RatingAction>;
    composite_score: number | null;
    history: RatingAction[];
  };
  risk: { composite: number; dimensions: DimensionScore[] };
  synopsis: string | null;
  news_placeholder: boolean;
}

function fmtPct(n: number | null): string {
  return n == null ? "\u2014" : `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function fmtValue(n: number | null): string {
  return n == null ? "\u2014" : n.toFixed(2);
}

function dimensionLabel(d: string): string {
  return d.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function CountryProfile() {
  const { iso3 = "" } = useParams();
  const { data, isLoading, error } = useQuery<CountryBundle>({
    queryKey: ["country-bundle", iso3.toUpperCase()],
    queryFn: () => api<CountryBundle>(`/api/countries/${iso3.toUpperCase()}/bundle`),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const { data: synopsisData } = useQuery<SynopsisData | null>({
    queryKey: ["synopsis", iso3.toUpperCase()],
    queryFn: () => api<SynopsisData | null>(`/api/synopses/${iso3.toUpperCase()}`),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const { data: newsData } = useQuery<NewsItemData[]>({
    queryKey: ["news", iso3.toUpperCase()],
    queryFn: () => api<NewsItemData[]>(`/api/news?iso3=${iso3.toUpperCase()}&limit=10`),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  if (isLoading) {
    return (
      <AppShell>
        <main className="mx-auto max-w-6xl p-6">
          <div className="space-y-6">
            <SkeletonLine className="h-8 w-1/4" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => <SkeletonCard key={i} />)}
            </div>
          </div>
        </main>
      </AppShell>
    );
  }
  if (error) {
    const msg = error instanceof ApiError && error.status === 404
      ? `Country ${iso3.toUpperCase()} not found`
      : "Failed to load country profile";
    return <AppShell><main className="p-8 text-danger">{msg}</main></AppShell>;
  }
  if (!data) return null;

  const { country, macro, fx, ratings, risk, synopsis, news_placeholder } = data;

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-6">
        {/* Header */}
        <header className="mb-6">
          <div className="flex items-baseline justify-between">
            <div className="flex items-baseline gap-3">
              <h1 className="text-2xl font-semibold text-ink-900">{country.name}</h1>
              <span className="font-mono text-sm text-ink-500">{country.iso3}</span>
            </div>
            <Link
              to={`/scenarios/new?country=${country.iso3}`}
              className="rounded-md bg-atlas-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-atlas-700"
            >
              Run Scenario
            </Link>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-ink-500">
            <span className="rounded bg-ink-100 px-2 py-0.5 uppercase tracking-wide">{country.status}</span>
            <span className="rounded bg-ink-100 px-2 py-0.5 uppercase tracking-wide">{country.fx_regime}</span>
            <span>Tier {country.tier} · {country.region}</span>
          </div>
        </header>

        {/* Synopsis */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">Synopsis</h2>
          <SynopsisCard synopsis={synopsisData ?? null} />
        </section>

        {/* Ratings */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">Ratings</h2>
          <div className="flex flex-wrap items-center gap-2">
            {Object.values(ratings.latest_per_agency).map((r) => (
              <RatingBadge key={r.agency} agency={r.agency} rating={r.rating} outlook={r.outlook} />
            ))}
            {ratings.composite_score != null ? (
              <span className="ml-2 rounded border border-ink-100 px-2 py-0.5 text-xs text-ink-700">
                Composite <span className="font-mono">{ratings.composite_score.toFixed(1)}</span>/21
              </span>
            ) : null}
          </div>
        </section>

        {/* Macro grid */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">Macro</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
            {macro.map((t) => (
              <div key={t.indicator} className="rounded-md border border-ink-100 bg-white p-3">
                <div className="flex items-start justify-between">
                  <div className="text-xs text-ink-500">{t.label}</div>
                  <StalenessChip state={t.staleness.state} ageDays={t.staleness.age_days} />
                </div>
                <div className="mt-1 font-mono text-lg text-ink-900">{fmtValue(t.value)}</div>
                <div className="text-[10px] text-ink-300">
                  {t.period ?? "\u2014"}{t.source ? ` \u00b7 ${t.source}` : ""}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* FX section */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">FX</h2>
          {fx ? (
            <div className="rounded-md border border-ink-100 bg-white p-4">
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="text-xs text-ink-500">{fx.latest.ccy} / USD</span>
                  <div className="font-mono text-2xl text-ink-900">{fx.latest.usd_per_ccy.toFixed(6)}</div>
                </div>
                <div className="text-[10px] text-ink-300">as of {fx.latest.observation_date}</div>
              </div>
              <div className="mt-3 grid grid-cols-4 gap-2 text-center">
                {[
                  { label: "1d", v: fx.delta_1d_pct },
                  { label: "7d", v: fx.delta_7d_pct },
                  { label: "30d", v: fx.delta_30d_pct },
                  { label: "YTD", v: fx.delta_ytd_pct },
                ].map((cell) => (
                  <div key={cell.label} className="rounded bg-ink-100/40 py-2">
                    <div className="text-[10px] uppercase tracking-wide text-ink-500">{cell.label}</div>
                    <div className={`font-mono text-sm ${cell.v == null ? "text-ink-500" : cell.v < 0 ? "text-danger" : "text-positive"}`}>
                      {fmtPct(cell.v)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <InstitutionalTable columns={[{ key: "label", header: "" }]} rows={[]} emptyLabel="No FX data yet" />
          )}
        </section>

        {/* Risk decomposition */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">
            Risk decomposition <span className="ml-2 font-mono text-ink-900">{risk.composite.toFixed(1)}/100</span>
          </h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {risk.dimensions.map((d) => (
              <RiskGauge
                key={d.dimension}
                label={dimensionLabel(d.dimension)}
                score={d.score}
                rationale={d.rationale}
                isEstimate={d.is_estimate}
              />
            ))}
          </div>
        </section>

        {/* News & impact */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-500">News & impact</h2>
          {newsData && newsData.length > 0 ? (
            <div className="space-y-2">
              {newsData.map((item) => (
                <NewsItemCard key={item.id} item={item} />
              ))}
            </div>
          ) : (
            <InstitutionalTable columns={[{ key: "label", header: "" }]} rows={[]} emptyLabel="No scored news yet." />
          )}
        </section>
      </main>
    </AppShell>
  );
}
