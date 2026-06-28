import { useState, useEffect, useRef } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  LayoutGrid,
  Globe,
  FileText,
  Activity,
  BookOpen,
  Bell,
  FolderOpen,
  Lock,
  Settings,
  LogOut,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

interface NavChild {
  label: string;
  to: string;
}

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
  disabled?: boolean;
  badge?: string;
  badgeColor?: "amber" | "red";
  children?: NavChild[];
  expandKey?: string;
  routePrefix?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const SECTIONS: NavSection[] = [
  {
    title: "CORE MODULES",
    items: [
      { label: "Dashboard", to: "/", icon: <LayoutGrid className="h-4 w-4" /> },
      {
        label: "Country Intelligence",
        to: "/countries",
        icon: <Globe className="h-4 w-4" />,
        expandKey: "country",
        routePrefix: "/countries",
        children: [
          { label: "Country List", to: "/countries" },
          { label: "Country Comparison", to: "/countries/compare" },
        ],
      },
      {
        label: "Deal Analysis",
        to: "#",
        icon: <FileText className="h-4 w-4" />,
        disabled: true,
        expandKey: "deals",
        routePrefix: "/deals",
        children: [
          { label: "Deal List", to: "#" },
          { label: "New Deal", to: "#" },
        ],
      },
      {
        label: "Scenario Engine",
        to: "/scenarios/new",
        icon: <Activity className="h-4 w-4" />,
        badge: "NEW",
        badgeColor: "amber",
      },
      { label: "News & Events", to: "/news", icon: <BookOpen className="h-4 w-4" /> },
      {
        label: "Live Monitoring",
        to: "#",
        icon: <Bell className="h-4 w-4" />,
        disabled: true,
        badge: "3",
        badgeColor: "red",
      },
      {
        label: "Reports",
        to: "/reports",
        icon: <FolderOpen className="h-4 w-4" />,
        badge: "NEW",
        badgeColor: "amber",
        expandKey: "reports",
        routePrefix: "/reports",
        children: [
          { label: "All Reports", to: "/reports" },
          { label: "Generate Report", to: "/reports/new" },
        ],
      },
    ],
  },
  {
    title: "ENTERPRISE \u2014 COMING SOON",
    items: [
      { label: "Capital View", to: "#", icon: <Lock className="h-4 w-4" />, disabled: true },
      { label: "Portfolio System", to: "#", icon: <Lock className="h-4 w-4" />, disabled: true },
    ],
  },
];

const STORAGE_KEY = "atlas:sidebar:expanded";

function loadExpanded(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function isExactActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to;
}

function sectionOwnsRoute(routePrefix: string, pathname: string): boolean {
  return pathname === routePrefix || pathname.startsWith(routePrefix + "/");
}

export default function Sidebar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const nav = useNavigate();
  const [expanded, setExpanded] = useState<Record<string, boolean>>(loadExpanded);
  const manualToggles = useRef<Set<string>>(new Set());

  // Auto-expand sections whose routePrefix matches the current route,
  // unless the user has manually toggled that section this session.
  useEffect(() => {
    setExpanded((prev) => {
      const next = { ...prev };
      for (const section of SECTIONS) {
        for (const item of section.items) {
          if (!item.expandKey || !item.routePrefix) continue;
          if (manualToggles.current.has(item.expandKey)) continue;
          next[item.expandKey] = sectionOwnsRoute(item.routePrefix, location.pathname);
        }
      }
      return next;
    });
  }, [location.pathname]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(expanded));
  }, [expanded]);

  function toggle(key: string) {
    manualToggles.current.add(key);
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleLogout() {
    await logout();
    nav("/login", { replace: true });
  }

  const version = (import.meta as any).env?.VITE_APP_VERSION ?? "v2.0 \u00b7 MVP";

  return (
    <aside className="sticky top-0 z-40 flex h-[calc(100vh-2rem)] w-60 shrink-0 flex-col border-r border-[#1e2b42] bg-[#0e1523]">
      {/* Brand */}
      <div className="px-5 pb-4 pt-5">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/10">
            <span className="text-sm font-bold text-amber-500">A</span>
          </div>
          <div>
            <span className="text-base font-semibold tracking-tight text-amber-500">ATLAS</span>
            <span className="ml-2 text-[10px] uppercase tracking-[0.14em] text-ink-500">
              Core MVP
            </span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-2">
        {SECTIONS.map((section) => (
          <div key={section.title} className="mb-5">
            <p className="mb-2 px-3 text-[10px] uppercase tracking-[0.14em] text-ink-500/70">
              {section.title}
            </p>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const sectionActive =
                  !item.disabled &&
                  item.routePrefix != null &&
                  sectionOwnsRoute(item.routePrefix, location.pathname);

                const itemActive =
                  !item.disabled &&
                  !item.children &&
                  isExactActive(location.pathname, item.to);

                const parentHighlight = sectionActive || itemActive;

                const hasChildren = item.children && item.children.length > 0;
                const isExpanded = item.expandKey ? expanded[item.expandKey] : false;

                if (item.disabled) {
                  return (
                    <li key={item.label}>
                      <span className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-3 py-2 text-sm text-ink-500 opacity-50">
                        {item.icon}
                        <span>{item.label}</span>
                        {item.badge && item.badgeColor === "red" && (
                          <span className="ml-auto flex h-4 min-w-4 items-center justify-center rounded-full bg-danger/20 px-1 text-[10px] font-medium text-danger">
                            {item.badge}
                          </span>
                        )}
                        {item.badge && item.badgeColor !== "red" && (
                          <span className="ml-auto rounded bg-[#1e2b42] px-1.5 py-0.5 text-[10px] font-medium text-ink-400">
                            {item.badge}
                          </span>
                        )}
                      </span>
                    </li>
                  );
                }

                return (
                  <li key={item.label}>
                    {hasChildren ? (
                      <button
                        type="button"
                        onClick={() => item.expandKey && toggle(item.expandKey)}
                        className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors duration-150 ${
                          parentHighlight
                            ? "text-amber-500"
                            : "text-ink-400 hover:bg-[#1a2640] hover:text-ink-200"
                        }`}
                      >
                        {item.icon}
                        <span>{item.label}</span>
                        <span className="ml-auto">
                          {isExpanded ? (
                            <ChevronDown className="h-3.5 w-3.5" />
                          ) : (
                            <ChevronRight className="h-3.5 w-3.5" />
                          )}
                        </span>
                      </button>
                    ) : (
                      <NavLink
                        to={item.to}
                        className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors duration-150 ${
                          parentHighlight
                            ? "border-l-[3px] border-amber-500 bg-amber-500/5 text-amber-500"
                            : "text-ink-400 hover:bg-[#1a2640] hover:text-ink-200"
                        }`}
                      >
                        {item.icon}
                        <span>{item.label}</span>
                        {item.badge && item.badgeColor === "amber" && (
                          <span className="ml-auto rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-amber-500">
                            {item.badge}
                          </span>
                        )}
                        {item.badge && item.badgeColor === "red" && (
                          <span className="ml-auto flex h-4 min-w-4 items-center justify-center rounded-full bg-danger/20 px-1 text-[10px] font-medium text-danger">
                            {item.badge}
                          </span>
                        )}
                      </NavLink>
                    )}

                    {/* Children */}
                    {hasChildren && isExpanded && (
                      <ul className="ml-5 mt-0.5 space-y-0.5 border-l border-[#1e2b42] pl-3">
                        {item.children!.map((child) => {
                          const childActive = isExactActive(location.pathname, child.to);
                          return (
                            <li key={child.to}>
                              <NavLink
                                to={child.to}
                                end
                                className={`flex items-center rounded-md px-3 py-1.5 text-sm transition-colors duration-150 ${
                                  childActive
                                    ? "border-l-[3px] border-amber-500 bg-amber-500/5 text-amber-500"
                                    : "text-ink-400 hover:bg-[#1a2640] hover:text-ink-200"
                                }`}
                              >
                                <span className="mr-2 text-[10px] text-ink-600">&bull;</span>
                                {child.label}
                              </NavLink>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* User footer */}
      {user && (
        <div className="border-t border-[#1e2b42] px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-500/10 text-xs font-semibold text-amber-500">
              {user.email.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="truncate text-sm text-ink-200">{user.email.split("@")[0]}</p>
              <p className="truncate text-[10px] text-ink-500">{user.role}</p>
            </div>
            <div className="flex gap-1">
              <button
                type="button"
                className="rounded p-1 text-ink-500 hover:bg-[#1a2640] hover:text-ink-300"
                title="Settings"
              >
                <Settings className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded p-1 text-ink-500 hover:bg-[#1a2640] hover:text-ink-300"
                title="Logout"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Version */}
      <div className="px-4 pb-3">
        <p className="text-[10px] text-ink-600">ATLAS Core {version}</p>
      </div>
    </aside>
  );
}
