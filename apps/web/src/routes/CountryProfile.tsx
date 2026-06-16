import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import {
  type StalenessState,
} from "@atlas/design-system";
import { Search, Bell } from "lucide-react";
import { ApiError, api } from "../api/client";
import AppShell from "./AppShell";
import { SkeletonLine, SkeletonCard } from "../components/Skeleton";
import { type SynopsisData } from "../components/SynopsisCard";
import RiskGaugeCircle from "../components/RiskGaugeCircle";
import RatingCard from "../components/RatingCard";
import CountryProfileTabs from "./country-profile/CountryProfileTabs";

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

interface CompositeRisk {
  score: number;
  label: string;
  trend: string;
  as_of: string | null;
}

interface AtlasSpread {
  value_bps: number;
  as_of: string | null;
}

interface ImfProgram {
  code: string;
  status: string;
}

interface CountryData {
  iso3: string;
  name: string;
  capital: string;
  region: string;
  tags: string[];
  tier: string;
  status: string;
  fx_regime: string;
  fx_regime_notes: string | null;
  fx_parallel_premium: number | null;
  iso_code_short: string | null;
  sub_region: string | null;
  status_tags: string[] | null;
  context_tags: string[] | null;
  composite_risk: CompositeRisk | null;
  atlas_spread: AtlasSpread | null;
  imf_program: ImfProgram | null;
  key_risks: string[] | null;
  key_opportunities: string[] | null;
  risk_decomposition: any;
  macro_annotations: Record<string, string> | null;
  fx_intelligence: any;
  economic_structure: any;
  forecasts: any;
}

interface CountryBundle {
  country: CountryData;
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
  debt_profile: any | null;
}

function statusPillColor(tag: string): string {
  switch (tag.toUpperCase()) {
    case "DISTRESSED":
      return "bg-red-500/10 text-red-500 border-red-500/30";
    case "RESTRUCTURING":
      return "bg-orange-500/10 text-orange-500 border-orange-500/30";
    case "WATCHLIST":
      return "bg-amber-500/10 text-amber-500 border-amber-500/30";
    case "WATCHLIST_POSITIVE":
      return "bg-amber-500/10 text-amber-500 border-amber-500/30";
    case "STABLE":
    case "GROWTH":
      return "bg-green-500/10 text-green-500 border-green-500/30";
    case "REFORM":
      return "bg-blue-500/10 text-blue-500 border-blue-500/30";
    default:
      return "bg-ink-700/50 text-ink-400 border-ink-600/30";
  }
}

function spreadColor(bps: number): string {
  if (bps > 500) return "text-danger";
  if (bps > 300) return "text-warning";
  return "text-positive";
}

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3600_000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatBps(bps: number): string {
  return bps >= 1000
    ? `${Math.floor(bps / 1000)}\u2009${String(bps % 1000).padStart(3, "0")}bps`
    : `${bps}bps`;
}

function ratingStatus(rating: string): string {
  const r = rating.toUpperCase().replace(/[+-]/g, "");
  if (["D", "RD", "SD", "C", "CC", "CCC", "CA", "CAA", "CAA1", "CAA3"].includes(r)) return "DISTRESSED";
  if (r === "NR") return "UNDER_REVIEW";
  return "STABLE";
}

export default function CountryProfile() {
  const { iso3 = "" } = useParams();
  const [synopsisExpanded, setSynopsisExpanded] = useState(false);

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

  if (isLoading) {
    return (
      <AppShell>
        <div className="mx-auto max-w-6xl p-6">
          <div className="space-y-6">
            <SkeletonLine className="h-8 w-1/4" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => <SkeletonCard key={i} />)}
            </div>
          </div>
        </div>
      </AppShell>
    );
  }
  if (error) {
    const msg =
      error instanceof ApiError && error.status === 404
        ? `Country ${iso3.toUpperCase()} not found`
        : "Failed to load country profile";
    return (
      <AppShell>
        <div className="p-8 text-danger">{msg}</div>
      </AppShell>
    );
  }
  if (!data) return null;

  const { country, macro, ratings, fx, debt_profile } = data;

  const synopsisText = synopsisData?.text ?? data.synopsis ?? "";

  const agencyOrder: ("Moodys" | "S&P" | "Fitch")[] = ["Moodys", "S&P", "Fitch"];

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl p-6">
        {/* === NEW HEADER === */}

        {/* Breadcrumb + title row */}
        <div className="mb-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-ink-500">
                <Link to="/countries" className="hover:text-ink-300">
                  Country Intelligence
                </Link>
                <span className="mx-1.5">&rsaquo;</span>
                <span className="text-ink-400">{country.name}</span>
              </p>
              <h1 className="mt-1 text-2xl font-semibold text-ink-100">
                {country.name} &mdash; Country Intelligence
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 rounded-md bg-[#161b22] px-3 py-1.5">
                <Search className="h-3.5 w-3.5 text-ink-500" />
                <span className="text-sm text-ink-500">Search countries...</span>
              </div>
              {/* TODO: Phase 3 — count comes from user alerts service */}
              <span className="flex items-center gap-1 rounded-full bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-500">
                <Bell className="h-3 w-3" />
                5 Active
              </span>
            </div>
          </div>
        </div>

        {/* Country card (hero) */}
        <div className="mb-6 rounded-lg bg-[#161b22] p-6">
          <div className="flex gap-6">
            {/* Left column */}
            <div className="flex-1">
              <div className="flex items-center gap-3">
                {/* Country code badge */}
                <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-[#21262d] bg-ink-800 text-lg font-semibold text-white">
                  {country.iso_code_short ?? country.iso3.slice(0, 2)}
                </div>

                <h2 className="text-[28px] font-bold text-ink-100">{country.name}</h2>

                {/* Status pills */}
                <div className="flex gap-1.5">
                  {(country.status_tags ?? []).map((tag) => (
                    <span
                      key={tag}
                      className={`rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${statusPillColor(tag)}`}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>

              {/* Subtitle */}
              <p className="mt-2 text-sm text-ink-500">
                {country.region}
                {country.sub_region && country.sub_region !== country.region && (
                  <> &middot; {country.sub_region}</>
                )}
                {country.capital && <> &middot; Capital: {country.capital}</>}
              </p>

              {/* Synopsis */}
              <div className="mt-4">
                <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">
                  ATLAS Executive Synopsis
                </p>
                <div className="mt-1.5">
                  <p
                    className={`text-sm leading-relaxed text-ink-200 ${!synopsisExpanded ? "line-clamp-4" : ""}`}
                  >
                    {synopsisText || "No synopsis available."}
                  </p>
                  {synopsisText && synopsisText.length > 200 && (
                    <button
                      type="button"
                      onClick={() => setSynopsisExpanded(!synopsisExpanded)}
                      className="mt-1 text-xs text-amber-500 hover:text-amber-400"
                    >
                      {synopsisExpanded ? "Show less" : "Read more"}
                    </button>
                  )}
                </div>
              </div>

              {/* Context tags */}
              {country.context_tags && country.context_tags.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {country.context_tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded border border-amber-500/20 bg-amber-500/5 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-500/80"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Right column */}
            <div className="flex w-48 flex-col items-center gap-4">
              {/* Composite risk gauge */}
              {country.composite_risk ? (
                <RiskGaugeCircle
                  score={country.composite_risk.score}
                  label={country.composite_risk.label}
                  trend={country.composite_risk.trend}
                />
              ) : (
                <div className="text-sm text-ink-500">No risk score</div>
              )}

              {/* Atlas spread */}
              <div className="w-full text-center">
                <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">ATLAS SPREAD</p>
                {country.atlas_spread ? (
                  <>
                    <p className={`mt-0.5 text-lg font-semibold tabular-nums ${spreadColor(country.atlas_spread.value_bps)}`}>
                      {formatBps(country.atlas_spread.value_bps)}
                    </p>
                    <p className="text-[10px] text-ink-600">
                      {relativeTime(country.atlas_spread.as_of)}
                    </p>
                  </>
                ) : (
                  <p className="mt-0.5 text-sm text-ink-500">&mdash;</p>
                )}
              </div>

              {/* IMF program */}
              <div className="w-full text-center">
                <p className="text-[10px] uppercase tracking-[0.14em] text-ink-500">IMF Program</p>
                {country.imf_program ? (
                  <span className="mt-1 inline-block rounded-full bg-amber-500/10 px-3 py-0.5 text-xs font-semibold text-amber-500">
                    {country.imf_program.code}
                  </span>
                ) : (
                  <p className="mt-0.5 text-sm text-ink-500">&mdash;</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* === RATINGS SECTION === */}
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-400">
            Sovereign Ratings
          </h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {agencyOrder.map((agency) => {
              const r = ratings.latest_per_agency[agency];
              const agencyHistory = ratings.history.filter((h) => h.agency === agency);
              if (!r) {
                return (
                  <RatingCard
                    key={agency}
                    agency={agency}
                    grade="NR"
                    outlook={null}
                    action="Not Rated"
                    date="\u2014"
                    status="UNDER_REVIEW"
                    history={[]}
                  />
                );
              }
              return (
                <RatingCard
                  key={agency}
                  agency={r.agency}
                  grade={r.rating}
                  outlook={r.outlook}
                  action={r.action}
                  date={r.action_date}
                  status={ratingStatus(r.rating)}
                  history={agencyHistory}
                />
              );
            })}
          </div>
        </section>

        {/* === TABBED CONTENT === */}
        <CountryProfileTabs
          country={country}
          macro={macro}
          synopsisData={synopsisData ?? null}
          fx={fx}
          debtProfile={debt_profile ?? null}
        />
      </div>
    </AppShell>
  );
}
