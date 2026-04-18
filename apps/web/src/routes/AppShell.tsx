import type { ReactNode } from "react";
import Sidebar from "../components/Sidebar";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main
        className="ml-56 flex-1 overflow-auto bg-ink-800 p-6"
        style={{
          backgroundImage:
            "radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.06) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, rgba(99,102,241,0.05) 0%, transparent 50%)",
        }}
      >
        {children}
      </main>
    </div>
  );
}
