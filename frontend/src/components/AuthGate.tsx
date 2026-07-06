import { FormEvent, ReactNode, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { authEnabled, supabase } from "../lib/supabase";

/**
 * Gates the admin app behind Supabase email/password auth. When auth is
 * disabled (no VITE_SUPABASE_* env), it renders children directly so local dev
 * is unchanged.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  // If auth is disabled we're "ready" immediately.
  const [ready, setReady] = useState(!authEnabled);

  useEffect(() => {
    if (!authEnabled || !supabase) return;
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  if (!authEnabled) return <>{children}</>;
  if (!ready) return null;
  if (!session) return <LoginForm />;

  return (
    <div className="relative h-full">
      {children}
      <button
        onClick={() => supabase?.auth.signOut()}
        className="fixed bottom-3 right-3 z-50 rounded-md bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-white shadow hover:bg-slate-700"
      >
        Sign out
      </button>
    </div>
  );
}

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) setError(error.message);
    setBusy(false);
  };

  return (
    <div className="flex h-full items-center justify-center bg-slate-50">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div>
          <h1 className="text-lg font-semibold text-slate-900">Admin sign in</h1>
          <p className="mt-1 text-sm text-slate-500">
            Sign in to manage the knowledge base and settings.
          </p>
        </div>

        <label className="block text-sm font-medium text-slate-700">
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          Password
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
