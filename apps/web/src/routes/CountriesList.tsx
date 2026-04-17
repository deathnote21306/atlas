import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import AppShell from "./AppShell";

interface Country {
  iso3: string;
  name: string;
  region: string;
  status: string;
  fx_regime: string;
  tier: string;
}

const REGIONS = ["West Africa", "East Africa", "Southern Africa", "North Africa"] as const;

export default function CountriesList() {
  const { data, isLoading, error } = useQuery<Country[]>({
    queryKey: ["countries"],
    queryFn: () => api<Country[]>("/api/countries"),
    staleTime: 5 * 60 * 1000,
  });
  const [q, setQ] = useState("");
  const [region, setRegion] = useState<string | null>(null);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.filter((c) => {
      if (region && c.region !== region) return false;
      if (!q) return true;
      const needle = q.trim().toLowerCase();
      return c.iso3.toLowerCase().includes(needle) || c.name.toLowerCase().includes(needle);
    });
  }, [data, q, region]);

  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-8">
        <h1 className="text-xl font-semibold text-ink-900">Countries</h1>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <input
            type="search"
            placeholder="Search by name or ISO3…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-56 rounded border border-ink-100 px-3 py-1 text-sm"
          />
          <div className="flex items-center gap-1">
            {REGIONS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRegion(region === r ? null : r)}
                className={`rounded border px-2 py-0.5 text-xs ${region === r ? "border-accent bg-accent/10 text-accent" : "border-ink-100 text-ink-700 hover:border-ink-300"}`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="mt-8 text-ink-500">Loading…</div>
        ) : error ? (
          <div className="mt-8 text-danger">Failed to load countries.</div>
        ) : (
          <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((c) => (
              <li key={c.iso3}>
                <Link
                  to={`/countries/${c.iso3}`}
                  className="block rounded-md border border-ink-100 bg-white p-4 transition hover:border-accent"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-sm font-semibold text-ink-900">{c.name}</div>
                      <div className="text-xs text-ink-500">{c.region} · {c.iso3}</div>
                    </div>
                    <span className="font-mono text-xs text-ink-500">Tier {c.tier}</span>
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-[10px] uppercase tracking-wide text-ink-500">
                    <span className="rounded bg-ink-100 px-1.5 py-0.5">{c.status}</span>
                    <span className="rounded bg-ink-100 px-1.5 py-0.5">{c.fx_regime}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </AppShell>
  );
}
