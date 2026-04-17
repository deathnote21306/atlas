import type { ReactNode } from "react";
import TopNav from "../components/TopNav";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-ink-100">
      <TopNav />
      <div>{children}</div>
    </div>
  );
}
