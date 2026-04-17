import { useQuery } from "@tanstack/react-query";
import { KpiCard } from "@atlas/design-system";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import AppShell from "./AppShell";

interface Health { status: string; version: string }

export default function Home() {
  const { user } = useAuth();
  const { data } = useQuery<Health>({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  return (
    <AppShell>
      <main className="mx-auto max-w-6xl p-8">
        <h1 className="text-xl font-semibold">Atlas — signed in as {user?.email}</h1>
        <div className="mt-6 grid grid-cols-2 gap-3">
          <KpiCard label="API status" value={data?.status ?? "—"} />
          <KpiCard label="API version" value={data?.version ?? "—"} />
        </div>
      </main>
    </AppShell>
  );
}
