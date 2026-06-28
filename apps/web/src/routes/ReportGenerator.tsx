import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { FileText, Loader2, CheckCircle, XCircle, ChevronDown, Download } from "lucide-react";
import { api } from "../api/client";
import AppShell from "./AppShell";

interface Country {
  iso3: string;
  name: string;
  region: string;
  tier: number;
}

interface ReportOut {
  id: string;
  template: string;
  iso3: string;
  generated_at: string;
  status: "pending" | "ready" | "failed";
}

const TEMPLATES = [
  {
    id: "country_brief",
    label: "Country Brief",
    description: "Full sovereign brief: risk score, macro KPIs, credit ratings, AI debt note",
  },
];

async function downloadReport(id: string, iso3: string, date: string) {
  const res = await fetch(`/api/reports/${id}/download`, { credentials: "include" });
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `atlas_${iso3}_${date}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ReportGenerator() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [iso3, setIso3] = useState(searchParams.get("country")?.toUpperCase() ?? "");
  const [template, setTemplate] = useState("country_brief");
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<ReportOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const { data: countries } = useQuery<Country[]>({
    queryKey: ["countries-list"],
    queryFn: () => api<Country[]>("/api/countries"),
    staleTime: 60_000,
  });

  async function handleGenerate() {
    if (!iso3) return;
    setGenerating(true);
    setResult(null);
    setError(null);
    try {
      const report = await api<ReportOut>("/api/reports", {
        method: "POST",
        body: JSON.stringify({ iso3, template }),
      });
      setResult(report);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  async function handleDownload() {
    if (!result) return;
    setDownloading(true);
    try {
      const dateStr = new Date(result.generated_at).toISOString().slice(0, 10).replace(/-/g, "");
      await downloadReport(result.id, result.iso3, dateStr);
    } finally {
      setDownloading(false);
    }
  }

  const selectedCountry = countries?.find((c) => c.iso3 === iso3);

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl p-6">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-xl font-semibold text-ink-100">Generate Report</h1>
          <p className="mt-0.5 text-sm text-ink-500">
            Create a downloadable PDF country brief from live Atlas data
          </p>
        </div>

        <div className="rounded-xl border border-[#1e2b42] bg-[#111929] p-6 space-y-6">
          {/* Country selector */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-ink-500 mb-2">
              Country
            </label>
            <div className="relative">
              <select
                value={iso3}
                onChange={(e) => setIso3(e.target.value)}
                className="w-full appearance-none rounded-lg border border-[#1e2b42] bg-[#0e1523] px-3 py-2.5 pr-9 text-sm text-ink-200 focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500/30"
              >
                <option value="">Select a country…</option>
                {countries
                  ?.sort((a, b) => a.name.localeCompare(b.name))
                  .map((c) => (
                    <option key={c.iso3} value={c.iso3}>
                      {c.name} ({c.iso3})
                    </option>
                  ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-500" />
            </div>
            {selectedCountry && (
              <p className="mt-1.5 text-xs text-ink-600">
                {selectedCountry.region} · Tier {selectedCountry.tier}
              </p>
            )}
          </div>

          {/* Template selector */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-ink-500 mb-2">
              Template
            </label>
            <div className="space-y-2">
              {TEMPLATES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTemplate(t.id)}
                  className={`w-full rounded-lg border p-3 text-left transition-colors ${
                    template === t.id
                      ? "border-amber-500 bg-amber-500/5"
                      : "border-[#1e2b42] hover:border-[#2a3a55] hover:bg-[#0e1827]"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <FileText
                      className={`h-4 w-4 ${template === t.id ? "text-amber-400" : "text-ink-500"}`}
                    />
                    <span
                      className={`text-sm font-medium ${
                        template === t.id ? "text-amber-400" : "text-ink-300"
                      }`}
                    >
                      {t.label}
                    </span>
                    {template === t.id && (
                      <CheckCircle className="ml-auto h-4 w-4 text-amber-400" />
                    )}
                  </div>
                  <p className="mt-1 ml-6 text-xs text-ink-600">{t.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Generate button */}
          <button
            type="button"
            onClick={handleGenerate}
            disabled={!iso3 || generating}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating PDF…
              </>
            ) : (
              <>
                <FileText className="h-4 w-4" />
                Generate Report
              </>
            )}
          </button>

          {/* Result */}
          {result && (
            <div
              className={`rounded-lg border p-4 ${
                result.status === "ready"
                  ? "border-emerald-800 bg-emerald-950/40"
                  : result.status === "failed"
                  ? "border-red-800 bg-red-950/40"
                  : "border-amber-800 bg-amber-950/30"
              }`}
            >
              <div className="flex items-start gap-3">
                {result.status === "ready" ? (
                  <CheckCircle className="h-5 w-5 text-emerald-400 mt-0.5 shrink-0" />
                ) : result.status === "failed" ? (
                  <XCircle className="h-5 w-5 text-red-400 mt-0.5 shrink-0" />
                ) : (
                  <Loader2 className="h-5 w-5 text-amber-400 animate-spin mt-0.5 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p
                    className={`text-sm font-semibold ${
                      result.status === "ready"
                        ? "text-emerald-300"
                        : result.status === "failed"
                        ? "text-red-300"
                        : "text-amber-300"
                    }`}
                  >
                    {result.status === "ready"
                      ? "Report ready"
                      : result.status === "failed"
                      ? "Generation failed"
                      : "Generating…"}
                  </p>
                  <p className="text-xs text-ink-500 mt-0.5">
                    {result.iso3} · {result.template.replace(/_/g, " ")} ·{" "}
                    {new Date(result.generated_at).toLocaleString()}
                  </p>
                  {result.status === "ready" && (
                    <div className="mt-3 flex gap-2">
                      <button
                        type="button"
                        onClick={handleDownload}
                        disabled={downloading}
                        className="flex items-center gap-1.5 rounded-md bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50 transition-colors"
                      >
                        {downloading ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Download className="h-3.5 w-3.5" />
                        )}
                        Download PDF
                      </button>
                      <button
                        type="button"
                        onClick={() => navigate("/reports")}
                        className="rounded-md border border-[#1e2b42] px-3 py-1.5 text-xs font-medium text-ink-400 hover:text-ink-200 transition-colors"
                      >
                        View All Reports
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-800 bg-red-950/40 p-4">
              <div className="flex items-center gap-2">
                <XCircle className="h-4 w-4 text-red-400 shrink-0" />
                <p className="text-sm text-red-300">{error}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
