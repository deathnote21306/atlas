import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import CountriesList from "../src/routes/CountriesList";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const SAMPLE = [
  { iso3: "GHA", name: "Ghana", capital: "Accra", region: "West Africa", tags: ["SSA"], tier: "C", status: "restructured", fx_regime: "float", fx_regime_notes: null, fx_parallel_premium: null },
  { iso3: "KEN", name: "Kenya", capital: "Nairobi", region: "East Africa", tags: ["SSA"], tier: "B", status: "performing", fx_regime: "managed_float", fx_regime_notes: null, fx_parallel_premium: null },
  { iso3: "ZAF", name: "South Africa", capital: "Pretoria", region: "Southern Africa", tags: ["SSA"], tier: "A", status: "performing", fx_regime: "float", fx_regime_notes: null, fx_parallel_premium: null },
];

function stubFetch(countries: typeof SAMPLE) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url === "/api/me") {
        return Promise.resolve(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(countries), { status: 200 }));
    }),
  );
}

describe("CountriesList", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders each seeded country", async () => {
    stubFetch(SAMPLE);
    render(wrap(<CountriesList />));
    expect(await screen.findByText("Ghana")).toBeInTheDocument();
    expect(screen.getByText("Kenya")).toBeInTheDocument();
    expect(screen.getByText("South Africa")).toBeInTheDocument();
  });

  it("filters by search term", async () => {
    stubFetch(SAMPLE);
    render(wrap(<CountriesList />));
    await screen.findByText("Ghana");
    await userEvent.type(screen.getByPlaceholderText(/search/i), "ken");
    expect(screen.getByText("Kenya")).toBeInTheDocument();
    expect(screen.queryByText("Ghana")).not.toBeInTheDocument();
  });

  it("filters by region chip", async () => {
    stubFetch(SAMPLE);
    render(wrap(<CountriesList />));
    await screen.findByText("Ghana");
    await userEvent.click(screen.getByRole("button", { name: /east africa/i }));
    expect(screen.getByText("Kenya")).toBeInTheDocument();
    expect(screen.queryByText("Ghana")).not.toBeInTheDocument();
  });
});
