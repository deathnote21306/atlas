import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      nav("/", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) setError(err.status === 401 ? "Invalid credentials" : err.message);
      else setError("Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto mt-24 w-80 space-y-3 rounded-[10px] bg-white/[0.05] backdrop-blur-2xl border border-white/[0.08] p-6">
      <h1 className="text-lg font-semibold text-ink-100">Atlas</h1>
      <label className="block text-xs text-ink-400">Email
        <input className="mt-1 w-full rounded border border-white/[0.06] bg-white/[0.04] px-2 py-1 text-ink-100 placeholder:text-ink-500"
               type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label className="block text-xs text-ink-400">Password
        <input className="mt-1 w-full rounded border border-white/[0.06] bg-white/[0.04] px-2 py-1 text-ink-100 placeholder:text-ink-500"
               type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </label>
      {error ? <div role="alert" className="text-xs text-danger">{error}</div> : null}
      <button disabled={submitting} className="w-full rounded bg-accent hover:bg-atlas-400 py-1 text-white disabled:opacity-50">
        {submitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
