import type { ReactNode } from "react";
import Sidebar from "../components/Sidebar";
import FxTicker from "../components/FxTicker";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="fixed left-0 right-0 top-0 z-50">
        <FxTicker />
      </div>
      <div className="flex flex-1 pt-8">
        <Sidebar />
        <main
          className="flex-1 overflow-auto bg-ink-800 pl-4"
          style={{
            backgroundImage:
              "radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.06) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, rgba(99,102,241,0.05) 0%, transparent 50%)",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
