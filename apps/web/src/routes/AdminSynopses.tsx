import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import AppShell from "./AppShell";

interface SynopsisListItem {
  id: string;
  iso3: string;
  text: string;
  generated_at: string;
  approval_state: string;
}

export default function AdminSynopses() {
  const queryClient = useQueryClient();

  const { data: synopses, isLoading } = useQuery<SynopsisListItem[]>({
    queryKey: ["admin-synopses"],
    queryFn: () => api<SynopsisListItem[]>("/api/admin/synopses"),
    staleTime: 30 * 1000,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      api(`/api/admin/synopses/${id}/approve`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-synopses"] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) =>
      api(`/api/admin/synopses/${id}/reject`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-synopses"] }),
  });

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl p-6">
        <h1 className="mb-6 text-xl font-semibold text-ink-900">Synopsis Review</h1>

        {isLoading && <p className="text-ink-500">Loading...</p>}

        {synopses && synopses.length === 0 && (
          <p className="text-ink-500">No synopses pending review.</p>
        )}

        <div className="space-y-4">
          {synopses?.map((s) => (
            <div key={s.id} className="rounded-md border border-ink-100 bg-white p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium text-ink-900">{s.iso3}</span>
                  <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                    {s.approval_state}
                  </span>
                </div>
                <span className="text-xs text-ink-400">
                  {new Date(s.generated_at).toLocaleString()}
                </span>
              </div>

              <div className="mb-3 text-sm text-ink-700 line-clamp-4">{s.text}</div>

              <div className="flex gap-2">
                <button
                  onClick={() => approveMutation.mutate(s.id)}
                  disabled={approveMutation.isPending}
                  className="rounded-md bg-positive px-3 py-1.5 text-xs font-medium text-white hover:bg-positive/90 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  onClick={() => rejectMutation.mutate(s.id)}
                  disabled={rejectMutation.isPending}
                  className="rounded-md bg-danger px-3 py-1.5 text-xs font-medium text-white hover:bg-danger/90 disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      </main>
    </AppShell>
  );
}
