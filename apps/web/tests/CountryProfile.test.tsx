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
    iso_code_short: "GH", sub_region: "West Africa",
    status_tags: ["RESTRUCTURING"], context_tags: ["POST RESTRUCTURING"],
    composite_risk: { score: 65, label: "Elevated", trend: "improving", as_of: null },
    atlas_spread: { value_bps: 900, as_of: null },
    imf_program: { code: "ECF", status: "ACTIVE" },
    key_risks: ["Post-restructuring fragility"], key_opportunities: ["IMF anchor"],
    risk_decomposition: null, macro_annotations: {},
    fx_intelligence: null, economic_structure: null, forecasts: null,
  },
  macro: [],
  fx: null,
  ratings: { latest_per_agency: {}, composite_score: null, history: [] },
  risk: { composite: 65, dimensions: [] },
  synopsis: "Ghana test synopsis",
  news_placeholder: false,
};

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : (input as Request).url;
    if (url.includes("/bundle")) return Response.json(GHA_BUNDLE);
    if (url.includes("/synopses/")) return Response.json(null);
    if (url.includes("/news?")) return Response.json([]);
    if (url.includes("/fx/ticker")) return Response.json({ as_of: "", indicative: true, quotes: [] });
    if (url.includes("/api/me")) return new Response(null, { status: 401 });
    return new Response(null, { status: 404 });
  });
});

describe("CountryProfile", () => {
  it("renders the country header with name and status pills", async () => {
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("Ghana")).toBeTruthy();
    expect(screen.getByText("RESTRUCTURING")).toBeTruthy();
  });

  it("renders the composite risk score", async () => {
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("65")).toBeTruthy();
  });

  it("renders the IMF program pill", async () => {
    render(wrap(<CountryProfile />));
    expect(await screen.findByText("ECF")).toBeTruthy();
  });
});
