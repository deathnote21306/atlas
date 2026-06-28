import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { FileText, Download, Plus, Clock, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { api } from "../api/client";
import AppShell from "./AppShell";

interface ReportOut {
  id: string;
  template: string;
  iso3: string;
  generated_at: string;
  generated_by: string | null;
  status: "pending" | "ready" | "failed";
  manifest: Record<string, unknown> | null;
}

function StatusBadge({ status }: { status: ReportOut["status"] }) {
  if (status === "ready")
    return (
      <span className="flex items-center gap-1 text-xs font-medium text-emerald-400">
        <CheckCircle className="h-3.5 w-3.5" /> Ready
      </span>
    );
  if (status === "failed")
    return (
      <span className="flex items-center gap-1 text-xs font-medium text-danger">
        <XCircle className="h-3.5 w-3.5" /> Failed
      </span>
    );
  return (
    <span className="flex items-center gap-1 text-xs font-medium text-amber-400">
      <Loader2 className="h-3.5 w-3.5 animate-spin" /> Generating…
    </span>
  );
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

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

export default function ReportsList() {
  const [downloading, setDownloading] = useState<string | null>(null);

  const { data: reports, isLoading } = useQuery<ReportOut[]>({
    queryKey: ["reports"],
    queryFn: () => api<ReportOut[]>("/api/reports"),
    refetchInterval: 5000,
  });

  async function handleDownload(report: ReportOut) {
    setDownloading(report.id);
    try {
      const dateStr = new Date(report.generated_at).toISOString().slice(0, 10).replace(/-/g, "");
      await downloadReport(report.id, report.iso3, dateStr);
    } finally {
      setDownloading(null);
    }
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink-100">Reports</h1>
            <p className="mt-0.5 text-sm text-ink-500">
              Generated country brief PDFs — institutional grade, ready to share
            </p>
          </div>
          <Link
            to="/reports/new"
            className="flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-amber-400"
          >
            <Plus className="h-4 w-4" />
            New Report
          </Link>
        </div>

        {/* Table */}
        <div className="rounded-xl border border-[#1e2b42] bg-[#111929] overflow-hidden">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 text-ink-500">
              <Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading reports…
            </div>
          ) : !reports || reports.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <FileText className="h-10 w-10 text-ink-600 mb-3" />
              <p className="text-sm font-medium text-ink-400">No reports yet</p>
              <p className="text-xs text-ink-600 mt-1 mb-4">
                Generate your first country brief PDF
              </p>
              <Link
                to="/reports/new"
                className="flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-black"
              >
                <Plus className="h-4 w-4" /> Generate Report
              </Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1e2b42] text-left">
                  <th className="px-5 py-3 text-[10px] uppercase tracking-wider text-ink-500 font-medium">Country</th>
                  <th className="px-5 py-3 text-[10px] uppercase tracking-wider text-ink-500 font-medium">Template</th>
                  <th className="px-5 py-3 text-[10px] uppercase tracking-wider text-ink-500 font-medium">Generated</th>
                  <th className="px-5 py-3 text-[10px] uppercase tracking-wider text-ink-500 font-medium">Status</th>
                  <th className="px-5 py-3 text-[10px] uppercase tracking-wider text-ink-500 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1a2438]">
                {reports.map((r) => (
                  <tr key={r.id} className="hover:bg-[#0e1827] transition-colors">
                    <td className="px-5 py-3.5">
                      <Link
                        to={`/countries/${r.iso3}`}
                        className="font-semibold text-amber-400 hover:underline"
                      >
                        {r.iso3}
                      </Link>
                    </td>
                    <td className="px-5 py-3.5 text-ink-300 capitalize">
                      {r.template.replace(/_/g, " ")}
                    </td>
                    <td className="px-5 py-3.5 text-ink-500">
                      <span className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5" />
                        {formatDate(r.generated_at)}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {r.status === "ready" && (
                        <button
                          type="button"
                          onClick={() => handleDownload(r)}
                          disabled={downloading === r.id}
                          className="flex items-center gap-1.5 ml-auto rounded-md bg-[#1a2640] px-3 py-1.5 text-xs font-medium text-ink-300 hover:bg-[#213050] hover:text-ink-100 disabled:opacity-50 transition-colors"
                        >
                          {downloading === r.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Download className="h-3.5 w-3.5" />
                          )}
                          Download PDF
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <p className="mt-3 text-xs text-ink-600">
          Reports auto-refresh every 5 seconds. PDFs are generated server-side and stored temporarily.
        </p>
      </div>
    </AppShell>
  );
}
