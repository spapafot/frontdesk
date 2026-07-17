import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../components/AuthGate";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { MfaSection } from "../components/MfaSection";
import { PlanStatusBadge } from "../components/PlanStatusBadge";
import { usePlan } from "../components/PlanProvider";
import { useSite } from "../components/SiteProvider";
import { Spinner } from "../components/Spinner";
import { supabase } from "../lib/supabase";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Personal account settings: identity, password, MFA, plan, sessions.
 * Everything here is user-level (available to team members too), unlike the
 * per-site Settings page. */
export function AccountPage() {
  const { userEmail } = useAuth();
  const { ownsAnySite } = useSite();
  const navigate = useNavigate();
  // Fed by MfaSection so the password form knows to ask for a TOTP code.
  const [hasMfa, setHasMfa] = useState(false);

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-slate-100">
      <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-5">
        <h1 className="text-lg font-semibold text-slate-900">Account</h1>
        <p className="mt-1 text-sm text-slate-500">
          Your sign-in details, security settings, and plan.
        </p>
      </header>

      <div className="mx-auto w-full max-w-5xl space-y-5 p-6">
        <section className="rounded-2xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-900">Profile</h2>
          <div className="mt-3 flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-600 text-sm font-semibold text-white">
              {(userEmail ?? "?").charAt(0).toUpperCase()}
            </div>
            <div>
              <p className="text-sm font-medium text-slate-800">
                {userEmail ?? "Unknown user"}
              </p>
              <p className="text-xs text-slate-400">
                You sign in with this email address.
              </p>
            </div>
          </div>
        </section>

        <ChangePasswordSection userEmail={userEmail} hasMfa={hasMfa} />

        <MfaSection onFactorsChanged={setHasMfa} />

        {ownsAnySite ? (
          <PlanSection onManage={() => navigate("/billing")} />
        ) : (
          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900">Plan</h2>
            <p className="mt-1 text-sm text-slate-500">
              Billing for this account is managed by your account owner.
            </p>
          </section>
        )}

        <SessionsSection />
      </div>
    </div>
  );
}

function ChangePasswordSection({
  userEmail,
  hasMfa,
}: {
  userEmail: string | null;
  hasMfa: boolean;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!supabase || !userEmail || busy) return;
    setSaved(false);
    if (next.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    if (next !== confirm) {
      setError("The new passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);

    // Prove the current password first. This re-login downgrades the client
    // session to aal1 for MFA accounts, so the TOTP re-verify below restores
    // aal2 before updateUser (which Supabase requires for enrolled users).
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email: userEmail,
      password: current,
    });
    if (signInError) {
      setBusy(false);
      setError("Current password is incorrect.");
      return;
    }

    if (hasMfa) {
      const { data: factors } = await supabase.auth.mfa.listFactors();
      const totp = (factors?.all ?? []).find(
        (f) => f.factor_type === "totp" && f.status === "verified",
      );
      if (totp) {
        const { data: challenge, error: challengeError } =
          await supabase.auth.mfa.challenge({ factorId: totp.id });
        const { error: verifyError } = challengeError
          ? { error: challengeError }
          : await supabase.auth.mfa.verify({
              factorId: totp.id,
              challengeId: challenge!.id,
              code,
            });
        if (verifyError) {
          setBusy(false);
          setError("That two-factor code didn't work — try again.");
          setCode("");
          return;
        }
      }
    }

    const { error: updateError } = await supabase.auth.updateUser({
      password: next,
    });
    setBusy(false);
    if (updateError) {
      setError(updateError.message);
      return;
    }
    setCurrent("");
    setNext("");
    setConfirm("");
    setCode("");
    setSaved(true);
  };

  const inputClass =
    "mt-1.5 w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-transparent focus:ring-2 focus:ring-sky-500";

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Change password</h2>
      <form onSubmit={onSubmit} className="mt-4 max-w-md space-y-4">
        <label className="block text-sm font-medium text-slate-700">
          Current password
          <input
            type="password"
            required
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          New password
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className={inputClass}
          />
        </label>
        <label className="block text-sm font-medium text-slate-700">
          Confirm new password
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className={inputClass}
          />
        </label>
        {hasMfa && (
          <label className="block text-sm font-medium text-slate-700">
            Two-factor code
            <input
              type="text"
              required
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]*"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className={inputClass}
            />
          </label>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={busy}
            className="rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
          >
            {busy ? "Saving…" : "Change password"}
          </button>
          {saved && <span className="text-sm text-emerald-600">Saved.</span>}
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </form>
    </section>
  );
}

function PlanSection({ onManage }: { onManage: () => void }) {
  const { billing, plan, status, isLoading } = usePlan();
  const usage = billing?.usage;
  const usagePct =
    usage && usage.messages_limit
      ? Math.min(
          100,
          Math.round((usage.messages_used / usage.messages_limit) * 100),
        )
      : 0;
  const renewal =
    status === "trialing" && billing?.trial_ends_at
      ? `Trial ends ${formatDate(billing.trial_ends_at)}`
      : billing?.current_period_end
        ? `Renews ${formatDate(billing.current_period_end)}`
        : null;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Plan</h2>
      {isLoading ? (
        <div className="mt-4" role="status">
          <Spinner className="h-5 w-5" label="Loading plan" />
        </div>
      ) : (
        <>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="text-sm font-semibold text-slate-900">
                {plan === "superadmin"
                  ? "Internal (unlimited)"
                  : `${plan.charAt(0).toUpperCase()}${plan.slice(1)} plan`}
              </span>
              <PlanStatusBadge status={status} />
            </div>
            <button
              type="button"
              onClick={onManage}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
            >
              Manage billing
            </button>
          </div>
          {renewal && <p className="mt-1.5 text-xs text-slate-400">{renewal}</p>}
          {usage && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-sm text-slate-600">
                <span>Messages this month</span>
                <span className="tabular-nums">
                  {usage.messages_used.toLocaleString()}
                  {usage.messages_limit != null
                    ? ` / ${usage.messages_limit.toLocaleString()}`
                    : " (unlimited)"}
                </span>
              </div>
              {usage.messages_limit != null && (
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full ${usagePct >= 100 ? "bg-red-500" : "bg-sky-600"}`}
                    style={{ width: `${usagePct}%` }}
                  />
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function SessionsSection() {
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const signOutOthers = async () => {
    setConfirming(false);
    if (!supabase) return;
    const { error: signOutError } = await supabase.auth.signOut({
      scope: "others",
    });
    if (signOutError) {
      setError(signOutError.message);
      return;
    }
    setError(null);
    setDone(true);
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5">
      <h2 className="text-sm font-semibold text-slate-900">Sessions</h2>
      <p className="mt-1 text-sm text-slate-500">
        Signed in somewhere you don't recognize? Sign out of every other
        device; this one stays signed in.
      </p>
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Sign out everywhere else
        </button>
        {done && (
          <span className="text-sm text-emerald-600">
            Signed out on other devices. Active sessions may take up to an hour
            to expire.
          </span>
        )}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>

      <ConfirmDialog
        open={confirming}
        title="Sign out everywhere else"
        message="Every other device and browser will be signed out. This session stays active."
        confirmLabel="Sign out others"
        onConfirm={() => void signOutOthers()}
        onCancel={() => setConfirming(false)}
      />
    </section>
  );
}
