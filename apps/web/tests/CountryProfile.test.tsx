import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CountryProfile from "../src/routes/CountryProfile";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode, initial = "/countries/GHA") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>
        <AuthProvider>
          <Routes>
            <Route path="/countries/:iso3" element={ui} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const GHA_BUNDLE = {
  country: {
    iso3: "GHA", name: "Ghana", capital: "Accra", region: "West Africa",
    tags: ["SSA"], tier: "C", status: "restructured", fx_regime: "float",
    fx_regime_notes: "Cedi floats", fx_parallel_premium: null,
  },
  macro: [
    { indicator: "PUBLIC_DEBT_PCT_GDP", label: "Public debt (% GDP)", value: 83.0, period: "2024", source: "worldbank", staleness: { state: "fresh", age_days: 30 } },
    { indicator: "INFLATION_PCT", label: "Inflation (CPI % YoY)", value: 22.0, period: "2024", source: "worldbank", staleness: { state: "fresh", age_days: 30 } },
    { indicator: "GDP_GROWTH_PCT", label: "GDP growth (% YoY)", value: 3.1, period: "2024", source: "imf_weo", staleness: { state: "fresh", age_days: 45 } },
  ],
  fx: {
    latest: {
      iso3: "GHA", ccy: "GHS", usd_per_ccy: 0.0667,
      observation_date: "2026-04-16", source: "exchangerate.host",
      ingested_at: "2026-04-16T03:00:00Z",
    },
    delta_1d_pct: -0.3, delta_7d_pct: -1.2, delta_30d_pct: -4.8, delta_ytd_pct: -9.0,
  },
  ratings: {
    latest_per_agency: {
      "S&P": { iso3: "GHA", agency: "S&P", rating: "CCC+", outlook: "stable", action: "upgrade", action_date: "2024-05-01", source_url: null },
    },
    composite_score: 17.5,
    history: [],
  },
  risk: {
    composite: 65.0,
    dimensions: [
      { dimension: "debt_burden", score: 10, rationale: "distressed", input_value: 83.0, is_estimate: false },
      { dimension: "external_liquidity", score: 5, rationale: "3.1mo", input_value: 3.1, is_estimate: false },
      { dimension: "fiscal_flexibility", score: 7, rationale: "-4.5%", input_value: -4.5, is_estimate: false },
      { dimension: "growth_momentum", score: 5, rationale: "3.1%", input_value: 3.1, is_estimate: false },
      { dimension: "inflation_pressure", score: 7, rationale: "22%", input_value: 22.0, is_estimate: false },
      { dimension: "fx_stability", score: 5, rationale: "-4.8%", input_value: -4.8, is_estimate: false },
    ],
  },
  synopsis: null,
  news_placeholder: true,
};

function stubBundle(body: unknown = GHA_BUNDLE) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url === "/api/me") {
        return Promise.resolve(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }));
      }
      if (url.includes("/api/synopses/")) {
        return Promise.resolve(new Response("{}", { status: 404 }));
      }
      if (url.includes("/api/news")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
    }),
  );
}

describe("CountryProfile", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders the header with country name and status", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("Ghana")).toBeInTheDocument();
    expect(screen.getByText(/restructured/i)).toBeInTheDocument();
  });

  it("renders macro tiles with values", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("Public debt (% GDP)")).toBeInTheDocument();
    expect(screen.getByText("83.00")).toBeInTheDocument();
  });

  it("renders FX section with latest rate and deltas", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText(/GHS/i)).toBeInTheDocument();
    expect(screen.getAllByText(/-4.8/).length).toBeGreaterThanOrEqual(1);
  });

  it("renders ratings with composite", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("CCC+")).toBeInTheDocument();
    expect(screen.getByText(/17\.5/)).toBeInTheDocument();
  });

  it("renders the 6 risk dimensions", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    await screen.findByText("Ghana");
    for (const dim of ["debt_burden", "external_liquidity", "fiscal_flexibility", "growth_momentum", "inflation_pressure", "fx_stability"]) {
      expect(screen.getByText(new RegExp(dim.replace("_", " "), "i"))).toBeInTheDocument();
    }
  });

  it("shows synopsis placeholder when synopsis is null", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText(/AI synopsis pending/i)).toBeInTheDocument();
  });

  it("shows news placeholder when news_placeholder is true", async () => {
    stubBundle();
    render(wrap(<CountryProfile />));
    expect(await screen.findByText(/no scored news yet/i)).toBeInTheDocument();
  });

  it("renders 404 state when bundle returns 404", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url === "/api/me") {
          return Promise.resolve(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }));
        }
        return Promise.resolve(new Response(JSON.stringify({ detail: "country ZZZ not found" }), { status: 404 }));
      }),
    );
    render(wrap(<CountryProfile />, "/countries/ZZZ"));
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
