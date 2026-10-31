import { FormEvent, useCallback, useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { ConfirmDialog } from "./ConfirmDialog";
import { Spinner } from "./Spinner";

interface Factor {
  id: string;
  factor_type: string;
  status: string;
  friendly_name?: string;
  created_at?: string;
}

interface Enrolling {
  factorId: string;
  /** Data-URI SVG straight from Supabase; rendered as an <img>. */
  qrCode: string;
  secret: string;
}

interface Props {
  /** Lets the parent (change-password form) know whether a TOTP code is
   * required; fires after every list refresh. */
  onFactorsChanged?: (hasVerified: boolean) => void;
}

/**
 * TOTP enrollment and removal, backed by supabase-js `auth.mfa`. Verifying the
 * enrollment upgrades the current session to aal2 in place, so the AuthGate
 * never interrupts; from the next sign-in on, the code challenge (and the
 * backend's aal2 requirement) apply.
 */
export function MfaSection({ onFactorsChanged }: Props) {
  const [factors, setFactors] = useState<Factor[] | null>(null);
  const [enrolling, setEnrolling] = useState<Enrolling | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<Factor | null>(null);

  const refresh = useCallback(async () => {
    if (!supabase) return;
    const { data, error: listError } = await supabase.auth.mfa.listFactors();
    if (listError) {
      setError(listError.message);
      return;
    }
    const totp = (data?.all ?? []).filter((f) => f.factor_type === "totp");
    setFactors(totp);
    onFactorsChanged?.(totp.some((f) => f.status === "verified"));
  }, [onFactorsChanged]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const verified = factors?.filter((f) => f.status === "verified") ?? [];

  const startEnroll = async () => {
    if (!supabase || busy) return;
    setBusy(true);
    setError(null);
    // Clear abandoned unverified factors first: Supabase keeps them around
    // and rejects a second enrollment with the same friendly name.
    for (const stale of factors?.filter((f) => f.status !== "verified") ?? []) {
      await supabase.auth.mfa.unenroll({ factorId: stale.id });
    }
    const { data, error: enrollError } = await supabase.auth.mfa.enroll({
      factorType: "totp",
      friendlyName: "Authenticator app",
    });
    setBusy(false);
    if (enrollError || !data) {
      setError(enrollError?.message ?? "Could not start enrollment.");
      return;
    }
    setEnrolling({
      factorId: data.id,
      qrCode: data.totp.qr_code,
      secret: data.totp.secret,
    });
    setCode("");
  };

  const cancelEnroll = async () => {
    if (!supabase || !enrolling) return;
    // Best-effort cleanup of the never-verified factor.
    await supabase.auth.mfa.unenroll({ factorId: enrolling.factorId });
    setEnrolling(null);
    setError(null);
    void refresh();
  };

  const confirmEnroll = async (e: FormEvent) => {
    e.preventDefault();
    if (!supabase || !enrolling || busy) return;
    setBusy(true);
    setError(null);
    const { data: challenge, error: challengeError } =
      await supabase.auth.mfa.challenge({ factorId: enrolling.factorId });
    if (challengeError || !challenge) {
      setBusy(false);
      setError(challengeError?.message ?? "Could not verify the code.");
      return;
    }
    const { error: verifyError } = await supabase.auth.mfa.verify({
      factorId: enrolling.factorId,
      challengeId: challenge.id,
      code,
    });
    setBusy(false);
    if (verifyError) {
      setError("That code didn't work — try again.");
      setCode("");
      return;
    }
    setEnrolling(null);
    void refresh();
  };

  const removeFactor = async () => {
    if (!supabase || !confirmRemove) return;
    const { error: unenrollError } = await supabase.auth.mfa.unenroll({
      factorId: confirmRemove.id,
    });
    setConfirmRemove(null);
    if (unenrollError) {
      setError(unenrollError.message);
      return;
    }
    void refresh();
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">
        Two-factor authentication
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Require a code from an authenticator app when signing in. Recommended —
        a password alone won't be enough to access your account.
      </p>

      {factors === null ? (
        <div className="mt-4" role="status">
          <Spinner className="h-5 w-5" label="Loading two-factor status" />
        </div>
      ) : enrolling ? (
        <form onSubmit={confirmEnroll} className="mt-4 space-y-4">
          <div className="flex flex-wrap items-start gap-5">
            <img
              src={enrolling.qrCode}
              alt="QR code for your authenticator app"
              className="h-40 w-40 rounded-lg border border-slate-200 bg-white p-2"
            />
            <div className="min-w-0 flex-1 space-y-3 text-sm text-slate-600">
              <p>
                1. Scan the QR code with your authenticator app (Google
                Authenticator, 1Password, Authy…).
              </p>
              <div>
                <p>
                  2. Or enter this secret manually — and save a copy somewhere
                  safe as a backup:
                </p>
                <code className="mt-1 block break-all rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-800">
                  {enrolling.secret}
                </code>
              </div>
              <p>3. Enter the 6-digit code the app shows.</p>
            </div>
          </div>

          <label className="block max-w-xs text-sm font-medium text-slate-700">
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
              className="mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500"
            />
          </label>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={busy || code.length < 6}
              className="rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
            >
              {busy ? "Verifying…" : "Turn on two-factor"}
            </button>
            <button
              type="button"
              onClick={() => void cancelEnroll()}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : verified.length > 0 ? (
        <div className="mt-4">
          {verified.map((factor) => (
            <div
              key={factor.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3"
            >
              <div>
                <p className="text-sm font-medium text-slate-800">
                  {factor.friendly_name || "Authenticator app"}
                </p>
                <p className="text-xs text-slate-400">
                  {factor.created_at
                    ? `Added ${new Date(factor.created_at).toLocaleDateString()}`
                    : "Enabled"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setConfirmRemove(factor)}
                className="rounded-xl border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50"
              >
                Remove
              </button>
            </div>
          ))}
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </div>
      ) : (
        <div className="mt-4">
          <button
            type="button"
            onClick={() => void startEnroll()}
            disabled={busy}
            className="rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
          >
            {busy ? "Starting…" : "Add authenticator app"}
          </button>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </div>
      )}

      <ConfirmDialog
        open={confirmRemove !== null}
        title="Remove two-factor authentication"
        message="Signing in will no longer require a code from your authenticator app. Your account will be protected by your password alone."
        confirmLabel="Remove"
        destructive
        onConfirm={() => void removeFactor()}
        onCancel={() => setConfirmRemove(null)}
      />
    </section>
  );
}
