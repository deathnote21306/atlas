import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { Menu } from "lucide-react";
import Sidebar from "../components/Sidebar";
import FxTicker from "../components/FxTicker";

export default function AppShell({ children }: { children: ReactNode }) {
  // Below lg the sidebar is a drawer. Above lg it is always docked and this
  // state is inert.
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  // Never leave the drawer covering the page after a route change.
  useEffect(() => setNavOpen(false), [location.pathname]);

  useEffect(() => {
    function onEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setNavOpen(false);
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <div className="fixed left-0 right-0 top-0 z-50">
        <FxTicker />
      </div>
      <div className="flex flex-1 pt-8">
        <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />

        {navOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/60 lg:hidden"
            onClick={() => setNavOpen(false)}
            aria-hidden="true"
          />
        )}

        <main
          className="min-w-0 flex-1 overflow-auto lg:pl-4"
          style={{
            backgroundColor: "#111929",
            backgroundImage:
              "radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.07) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, rgba(99,102,241,0.05) 0%, transparent 50%)",
          }}
        >
          {/* Drawer trigger. Hidden once the sidebar docks at lg. */}
          <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-[#1e2b42] bg-[#0e1523]/95 px-4 py-2 backdrop-blur lg:hidden">
            <button
              type="button"
              onClick={() => setNavOpen(true)}
              aria-label="Open navigation"
              aria-expanded={navOpen}
              className="flex h-8 w-8 items-center justify-center rounded-md border border-[#1e2b42] text-ink-300 transition-colors hover:text-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              <Menu className="h-4 w-4" />
            </button>
            <span className="text-sm font-semibold tracking-tight text-amber-500">ATLAS</span>
          </div>

          {children}
        </main>
      </div>
    </div>
  );
}
