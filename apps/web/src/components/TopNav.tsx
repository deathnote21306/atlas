import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function TopNav() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  async function handleLogout() {
    await logout();
    nav("/login", { replace: true });
  }

  return (
    <header className="border-b border-ink-100 bg-white">
      <div className="mx-auto flex h-12 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <span className="font-semibold tracking-tight text-ink-900">Atlas</span>
          <nav className="flex items-center gap-4 text-sm text-ink-700">
            <Link to="/" className="hover:text-ink-900">Home</Link>
            <Link to="/countries" className="hover:text-ink-900">Countries</Link>
          </nav>
        </div>
        {user ? (
          <div className="flex items-center gap-3 text-xs text-ink-500">
            <span>{user.email}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded border border-ink-100 px-2 py-0.5 hover:border-ink-300 hover:text-ink-900"
            >
              Logout
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
