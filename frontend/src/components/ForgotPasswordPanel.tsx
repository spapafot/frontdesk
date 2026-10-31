import { FormEvent, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { requestPasswordRecovery } from "../api/auth";
import { ApiError } from "../api/client";

interface Props {
  /** Return to the sign-in form. */
  onBack: () => void;
}

/**
 * Asks for the account email and requests a reset link. Deliberately always
 * lands on the same "if an account exists" confirmation - the backend response
 * reveals nothing about whether the email is registered, and neither do we.
 * Only rate-limit (429) and validation (422) errors are worth surfacing.
 */
export function ForgotPasswordPanel({ onBack }: Props) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await requestPasswordRecovery(email);
      setSent(true);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 429 || err.status === 422)) {
        setError(err.message);
      } else {
        // Anything else (network, 5xx) still shows the generic confirmation:
        // an attacker must not learn more from failures than from successes.
        setSent(true);
      }
    }
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
            Reset your password
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {sent
              ? "If an account exists for that email, we've sent a reset link. Check your inbox."
              : "Enter your account email and we'll send you a reset link."}
          </p>
        </div>

        {!sent && (
          <>
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
              {busy ? "Sending…" : "Send reset link"}
            </button>
          </>
        )}

        <button
          type="button"
          onClick={onBack}
          className="w-full text-center text-sm font-medium text-sky-700 hover:text-sky-800"
        >
          Back to sign in
        </button>
      </form>
    </div>
  );
}
