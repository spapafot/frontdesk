import { FormEvent, useCallback, useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { supabase } from "../lib/supabase";

interface Props {
  /** The session was upgraded to aal2; let the app render. */
  onVerified: () => void;
  /** Escape valve so a user without their authenticator isn't trapped here. */
  onSignOut: () => void;
}

/**
 * Post-login TOTP challenge, shown by AuthGate whenever the session is aal1
 * but the account has a verified factor (nextLevel aal2). The backend
 * independently rejects aal1 tokens for such accounts, so this screen is the
 * UX for a hard requirement, not the enforcement itself.
 */
export function MfaChallenge({ onVerified, onSignOut }: Props) {
  const [factorId, setFactorId] = useState<string | null>(null);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const begin = useCallback(async () => {
    if (!supabase) return;
    const { data: factors, error: listError } = await supabase.auth.mfa.listFactors();
    if (listError) {
      setError(listError.message);
      return;
    }
    const all = factors?.all ?? [];
    const totp =
      all.find((f) => f.factor_type === "totp" && f.status === "verified") ??
      factors?.totp?.[0];
    if (!totp) {
      setError("No authenticator app is enrolled on this account.");
      return;
    }
    const { data: challenge, error: challengeError } =
      await supabase.auth.mfa.challenge({ factorId: totp.id });
    if (challengeError) {
      setError(challengeError.message);
      return;
    }
    setFactorId(totp.id);
    setChallengeId(challenge.id);
  }, []);

  useEffect(() => {
    void begin();
  }, [begin]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!supabase || !factorId || !challengeId || busy) return;
    setBusy(true);
    setError(null);
    const { error: verifyError } = await supabase.auth.mfa.verify({
      factorId,
      challengeId,
      code,
    });
    setBusy(false);
    if (verifyError) {
      // A challenge is single-use; issue a fresh one for the retry.
      setError("That code didn't work — try again.");
      setCode("");
      void begin();
      return;
    }
    onVerified();
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
            Two-factor authentication
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Enter the 6-digit code from your authenticator app to continue.
          </p>
        </div>

        <label className="block text-sm font-medium text-slate-700">
          Verification code
          <input
            type="text"
            required
            autoFocus
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]*"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-center text-lg tracking-[0.4em] focus:border-transparent focus:outline-none focus:ring-2 focus:ring-sky-500"
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
          disabled={busy || code.length < 6}
          className="w-full rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
        >
          {busy ? "Verifying…" : "Verify"}
        </button>

        <button
          type="button"
          onClick={onSignOut}
          className="w-full text-center text-sm font-medium text-slate-500 hover:text-slate-700"
        >
          Sign out
        </button>
      </form>
    </div>
  );
}
