import { FormEvent, useState } from "react";
import { supabase } from "../lib/supabase";

interface Props {
  /** Called once the password is saved so the app can proceed. */
  onDone: () => void;
  title?: string;
  description?: string;
  submitLabel?: string;
  /** Invitees must accept the ToS (default); a password-recovery user already
   * accepted it at sign-up, so recovery passes false and hides the checkbox. */
  requireAgreement?: boolean;
}

/**
 * Sets the account password on the current session. Two entry points, both
 * arriving via a one-time Supabase action link in the URL hash:
 *  * team invite (default copy) - the invitee has no password yet, so without
 *    this step they could never sign in a second time;
 *  * password recovery - same mechanics with recovery copy and no ToS gate.
 */
export function SetPasswordPanel({
  onDone,
  title = "Welcome to the team",
  description = "Choose a password to finish setting up your account. You'll use it to sign in from now on.",
  submitLabel = "Save password and continue",
  requireAgreement = true,
}: Props) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [agreed, setAgreed] = useState(false);
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
    if (requireAgreement && !agreed) {
      setError("Please accept the Terms of Service and Privacy Policy.");
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
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
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

        {requireAgreement && (
          <label className="flex items-start gap-2.5 text-sm text-slate-600">
            <input
              type="checkbox"
              required
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            <span>
              I agree to the{" "}
              <a
                href="https://plugandplay.gr/terms-of-service"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-sky-700 underline hover:text-sky-800"
              >
                Terms of Service
              </a>{" "}
              and{" "}
              <a
                href="https://plugandplay.gr/privacy-policy"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-sky-700 underline hover:text-sky-800"
              >
                Privacy Policy
              </a>
              .
            </span>
          </label>
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy || (requireAgreement && !agreed)}
          className="w-full rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
        >
          {busy ? "Saving…" : submitLabel}
        </button>
      </form>
    </div>
  );
}
