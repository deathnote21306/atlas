import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

interface NavItem {
  label: string;
  to: string;
  icon: string;
  disabled?: boolean;
  badge?: string;
  children?: NavItem[];
}

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "INTELLIGENCE",
    items: [
      { label: "Dashboard", to: "/", icon: "\u25C9" },
      {
        label: "Country Intelligence",
        to: "/countries",
        icon: "\u25EB",
        children: [
          { label: "Country Comparison", to: "/countries/compare", icon: "" },
        ],
      },
      { label: "Scenario Engine", to: "/scenarios/new", icon: "\u26A1" },
      { label: "News & Events", to: "/news", icon: "\u25C8" },
    ],
  },
  {
    title: "OPERATIONS",
    items: [
      { label: "Deal Analysis", to: "#", icon: "", disabled: true, badge: "Soon" },
      { label: "Live Monitoring", to: "#", icon: "", disabled: true, badge: "Soon" },
      { label: "Reports", to: "#", icon: "", disabled: true, badge: "Soon" },
    ],
  },
];

function isActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to || pathname.startsWith(to + "/");
}

export default function Sidebar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const nav = useNavigate();

  async function handleLogout() {
    await logout();
    nav("/login", { replace: true });
  }

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-56 flex-col border-r border-white/[0.06] bg-ink-900/85 backdrop-blur-xl">
      {/* Brand */}
      <div className="px-4 py-5">
        <span className="bg-gradient-to-br from-blue-400 to-purple-400 bg-clip-text text-lg font-semibold tracking-tight text-transparent">
          Atlas
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-2">
        {SECTIONS.map((section) => (
          <div key={section.title} className="mb-4">
            <p className="mb-1 px-3 py-2 text-xs font-medium uppercase tracking-wide text-ink-500">
              {section.title}
            </p>
            <ul>
              {section.items.map((item) => (
                <li key={item.label}>
                  {item.disabled ? (
                    <span className="flex cursor-default items-center gap-2 rounded-md px-3 py-2 text-sm text-ink-500 opacity-40">
                      {item.icon && <span className="w-4 text-center text-xs">{item.icon}</span>}
                      <span>{item.label}</span>
                      {item.badge && (
                        <span className="ml-auto rounded bg-ink-700 px-1.5 py-0.5 text-[10px] font-medium text-ink-400">
                          {item.badge}
                        </span>
                      )}
                    </span>
                  ) : (
                    <Link
                      to={item.to}
                      className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors duration-150 ${
                        isActive(location.pathname, item.to)
                          ? "border-l-2 border-accent bg-ink-800 text-ink-100"
                          : "text-ink-400 hover:bg-white/[0.04] hover:text-ink-200"
                      }`}
                    >
                      {item.icon && <span className="w-4 text-center text-xs">{item.icon}</span>}
                      <span>{item.label}</span>
                    </Link>
                  )}

                  {/* Sub-items */}
                  {item.children?.map((child) => (
                    <Link
                      key={child.to}
                      to={child.to}
                      className={`ml-6 flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors duration-150 ${
                        isActive(location.pathname, child.to)
                          ? "border-l-2 border-accent bg-ink-800 text-ink-100"
                          : "text-ink-400 hover:bg-white/[0.04] hover:text-ink-200"
                      }`}
                    >
                      <span>{child.label}</span>
                    </Link>
                  ))}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* User / Logout */}
      {user && (
        <div className="border-t border-white/[0.06] px-3 py-3">
          <p className="truncate text-xs text-ink-400">{user.email}</p>
          <button
            type="button"
            onClick={handleLogout}
            className="mt-2 w-full rounded-md border border-ink-600 px-3 py-1.5 text-xs text-ink-400 transition-colors duration-150 hover:border-ink-500 hover:text-ink-200"
          >
            Logout
          </button>
        </div>
      )}
    </aside>
  );
}
