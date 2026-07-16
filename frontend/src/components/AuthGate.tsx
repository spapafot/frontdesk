import {
  createContext,
  FormEvent,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import type { Session } from "@supabase/supabase-js";
import { authEnabled, supabase } from "../lib/supabase";
import { SetPasswordPanel } from "./SetPasswordPanel";
import { Spinner } from "./Spinner";
import { AlertTriangle } from "lucide-react";

interface AuthContextValue {
  /** True only when a real session exists and can be signed out. */
  canSignOut: boolean;
  signOut: () => void;
  /** Supabase user id (`sub`) - the same value the backend sees as the admin
   * user id, so it can be compared against e.g. a ticket's assignee. */
  userId: string | null;
  userEmail: string | null;
}

const AuthContext = createContext<AuthContextValue>({
  canSignOut: false,
  signOut: () => {},
  userId: null,
  userEmail: null,
});

/** Lets any descendant (e.g. the sidebar) trigger sign-out. */
export function useAuth() {
  return useContext(AuthContext);
}

/**
 * Gates the admin app behind Supabase email/password auth. Missing Supabase
 * configuration fails closed in every environment, including local dev.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  // If auth is disabled we're "ready" immediately.
  const [ready, setReady] = useState(!authEnabled);
  // A team-invite link lands here with `type=invite` in the URL hash. Capture
  // it synchronously on first render - supabase-js consumes the hash to create
  // the session and strips it from the URL. The invitee has no password yet,
  // so they must set one before entering the app (or they could never sign in
  // a second time).
  const [invitePending, setInvitePending] = useState(() =>
    window.location.hash.includes("type=invite"),
  );

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

  const signOut = () => {
    void supabase?.auth.signOut();
  };

  if (!authEnabled) {
    return <AuthConfigurationError />;
  }
  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-50">
        <Spinner className="h-8 w-8" label="Signing in" />
      </div>
    );
  }
  if (!session) return <LoginForm />;
  if (invitePending) {
    return <SetPasswordPanel onDone={() => setInvitePending(false)} />;
  }

  return (
    <AuthContext.Provider
      value={{
        canSignOut: true,
        signOut,
        userId: session.user.id,
        userEmail: session.user.email ?? null,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

function AuthConfigurationError() {
  return (
    <div className="flex h-full items-center justify-center bg-slate-50 p-4">
      <div
        role="alert"
        aria-labelledby="auth-config-title"
        className="max-w-md rounded-2xl border border-red-200 bg-white p-6 text-center shadow-sm"
      >
        <h1
          id="auth-config-title"
          className="text-lg font-semibold text-slate-900"
        >
          Authentication is not configured
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY before starting the
          admin app.
        </p>
      </div>
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
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (error) setError(error.message);
    setBusy(false);
  };

  return (
    <div className="flex h-full items-center justify-center bg-slate-50 p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-5 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <div className="flex flex-col items-center text-center">
          <img
            src="/logo-stacked-full-color.png"
            alt="Plug & Play"
            className="mb-5 h-24 w-auto"
          />
          <h1 className="text-xl font-semibold text-slate-900">
            Admin sign in
          </h1>
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
            className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-sky-500"
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
            className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </label>

        {error && (
          <p className="flex items-center gap-1.5 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
