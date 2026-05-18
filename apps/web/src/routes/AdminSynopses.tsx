import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { toast } from "../components/Toast";
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

  const { data: synopses, isLoading, isError, error } = useQuery<SynopsisListItem[]>({
    queryKey: ["admin-synopses"],
    queryFn: () => api<SynopsisListItem[]>("/api/admin/synopses"),
    staleTime: 30 * 1000,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) =>
      api(`/api/admin/synopses/${id}/approve`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-synopses"] });
      toast.success("Synopsis approved");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Approve failed");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) =>
      api(`/api/admin/synopses/${id}/reject`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-synopses"] });
      toast.success("Synopsis rejected");
    },
    onError: (err: Error) => {
      toast.error(err.message || "Reject failed");
    },
  });

  return (
    <AppShell>
      <main className="mx-auto max-w-4xl p-6">
        <h1 className="mb-6 text-xl font-semibold text-ink-100">Synopsis Review</h1>

        {isLoading && (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="rounded-lg bg-[#161b22] p-4 space-y-3">
                <div className="h-4 w-1/3 animate-pulse rounded bg-[#21262d]" />
                <div className="h-3 w-full animate-pulse rounded bg-[#21262d]" />
                <div className="h-3 w-2/3 animate-pulse rounded bg-[#21262d]" />
              </div>
            ))}
          </div>
        )}

        {isError && (
          <div role="alert" className="mb-4 rounded-md border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
            Failed to load synopses: {error?.message || "Unknown error"}
          </div>
        )}

        {synopses && synopses.length === 0 && (
          <p className="text-ink-400">No synopses pending review.</p>
        )}

        <div className="space-y-4">
          {synopses?.map((s) => (
            <div key={s.id} className="rounded-lg bg-[#161b22] p-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium text-ink-100">{s.iso3}</span>
                  <span className="rounded bg-amber-500/10 px-2 py-0.5 text-xs text-amber-400">
                    {s.approval_state}
                  </span>
                </div>
                <span className="text-xs text-ink-400">
                  {new Date(s.generated_at).toLocaleString()}
                </span>
              </div>

              <div className="mb-3 text-sm text-ink-300 line-clamp-4">{s.text}</div>

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
