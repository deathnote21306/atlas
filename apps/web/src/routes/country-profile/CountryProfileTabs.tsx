import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { TabList, TabPanel, type TabDef } from "../../components/ui/Tabs";
import type { SynopsisData } from "../../components/SynopsisCard";
import type { StalenessState } from "@atlas/design-system";
import { api } from "../../api/client";
import OverviewTab from "./OverviewTab";
import MacroTab from "./MacroTab";
import FxIntelligenceTab from "./FxIntelligenceTab";
import RiskDecompositionTab from "./RiskDecompositionTab";
import EconomicStructureTab from "./EconomicStructureTab";
import ForecastsTab from "./ForecastsTab";
import NewsTab from "./NewsTab";
import EventsTab from "./EventsTab";

interface MacroTile {
  indicator: string;
  label: string;
  value: number | null;
  period: string | null;
  source: string | null;
  staleness: { state: StalenessState; age_days: number | null };
}

interface CountryData {
  iso3: string;
  name?: string;
  key_risks: string[] | null;
  key_opportunities: string[] | null;
  risk_decomposition: any;
  macro_annotations: Record<string, string> | null;
  fx_intelligence: any;
  economic_structure: any;
  forecasts: any;
}

interface FxDeltas {
  latest: { usd_per_ccy: number; observation_date: string };
  delta_1d_pct: number | null;
}

interface CountryProfileTabsProps {
  country: CountryData;
  macro: MacroTile[];
  synopsisData: SynopsisData | null;
  fx: FxDeltas | null;
}

interface NewsArticle {
  id: string;
  event_type: string | null;
  [key: string]: any;
}

const VALID_TABS = [
  "overview", "macro", "fx-intelligence", "risk-decomposition",
  "economic-structure", "forecasts", "news", "events",
];

function Placeholder({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center rounded-lg bg-[#161b22] py-16">
      <p className="text-sm text-ink-500">{message}</p>
    </div>
  );
}

export default function CountryProfileTabs({ country, macro, synopsisData, fx }: CountryProfileTabsProps) {
  const [searchParams, setSearchParams] = useSearchParams();

  const { data: allNews } = useQuery<NewsArticle[]>({
    queryKey: ["country-news-counts", country.iso3],
    queryFn: () => api<NewsArticle[]>(`/api/news?iso3=${country.iso3}&limit=100`),
    staleTime: 5 * 60_000,
  });

  const newsCount = allNews?.length ?? 0;
  const eventsCount = useMemo(
    () => (allNews ?? []).filter((a) => a.event_type != null && a.event_type !== "Market").length,
    [allNews],
  );

  const rawTab = searchParams.get("tab") ?? "overview";
  const activeTab = VALID_TABS.includes(rawTab) ? rawTab : "overview";

  const setTab = useCallback(
    (id: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("tab", id);
        next.delete("article");
        next.delete("event");
        return next;
      });
    },
    [setSearchParams],
  );

  const tabs: TabDef[] = [
    { id: "overview", label: "Overview" },
    { id: "macro", label: "Macro" },
    { id: "fx-intelligence", label: "FX Intelligence" },
    { id: "risk-decomposition", label: "Risk Decomposition" },
    { id: "economic-structure", label: "Economic Structure" },
    { id: "forecasts", label: "Forecasts" },
    { id: "news", label: "News", badge: String(newsCount) },
    { id: "events", label: "Events", badge: String(eventsCount) },
  ];

  const sparklines: Record<string, number[]> = {};
  const seenIndicators = new Set<string>();
  for (const tile of macro) {
    if (!seenIndicators.has(tile.indicator) && tile.value != null) {
      seenIndicators.add(tile.indicator);
      sparklines[tile.indicator] = [tile.value * 0.85, tile.value * 0.9, tile.value * 0.95, tile.value * 1.02, tile.value * 0.98, tile.value];
    }
  }

  return (
    <div>
      <TabList tabs={tabs} activeTab={activeTab} onTabChange={setTab} />

      <TabPanel id="overview" activeTab={activeTab}>
        <OverviewTab
          keyRisks={country.key_risks ?? []}
          keyOpportunities={country.key_opportunities ?? []}
          riskDecomposition={country.risk_decomposition}
          synopsisData={synopsisData}
        />
      </TabPanel>

      <TabPanel id="macro" activeTab={activeTab}>
        <MacroTab
          tiles={macro}
          annotations={country.macro_annotations ?? {}}
          sparklines={sparklines}
        />
      </TabPanel>

      <TabPanel id="fx-intelligence" activeTab={activeTab}>
        <FxIntelligenceTab
          iso3={country.iso3}
          fxIntel={country.fx_intelligence}
          spotRate={fx ? Math.round((1 / fx.latest.usd_per_ccy) * 100) / 100 : null}
          spotAsOf={fx?.latest.observation_date ?? null}
          staleness="FRESH"
        />
      </TabPanel>

      <TabPanel id="risk-decomposition" activeTab={activeTab}>
        <RiskDecompositionTab data={country.risk_decomposition} />
      </TabPanel>

      <TabPanel id="economic-structure" activeTab={activeTab}>
        <EconomicStructureTab data={country.economic_structure} countryName={country.name ?? country.iso3} />
      </TabPanel>

      <TabPanel id="forecasts" activeTab={activeTab}>
        <ForecastsTab data={country.forecasts} countryName={country.name ?? country.iso3} />
      </TabPanel>

      <TabPanel id="news" activeTab={activeTab}>
        <NewsTab iso3={country.iso3} />
      </TabPanel>

      <TabPanel id="events" activeTab={activeTab}>
        <EventsTab iso3={country.iso3} />
      </TabPanel>
    </div>
  );
}
