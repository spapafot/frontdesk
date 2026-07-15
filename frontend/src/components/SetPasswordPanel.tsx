import { FormEvent, useState } from "react";
import { supabase } from "../lib/supabase";

interface Props {
  /** Called once the password is saved so the app can proceed. */
  onDone: () => void;
}

/**
 * Shown right after an invitee lands from their invite email: the invite link
 * signs them in (Supabase session from the URL hash) but their account has no
 * password yet, so without this step they could never sign in again.
 */
export function SetPasswordPanel({ onDone }: Props) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!supabase || busy) return;
    if (password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("The passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.updateUser({ password });
    if (error) {
      setError(error.message);
      setBusy(false);
      return;
    }
    onDone();
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
            Welcome to the team
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Choose a password to finish setting up your account. You'll use it
            to sign in from now on.
          </p>
        </div>

        <label className="block text-sm font-medium text-slate-700">
          New password
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </label>

        <label className="block text-sm font-medium text-slate-700">
          Confirm password
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
        >
          {busy ? "Saving…" : "Save password and continue"}
        </button>
      </form>
    </div>
  );
}
