import { usePlan } from "./PlanProvider";

function daysLeft(iso: string | null): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms)) return null;
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

/** A slim, account-wide status banner shown above the app content while on a
 * trial, locked (expired/canceled), or past-due plan. Renders nothing for
 * active paid plans and super-admins. */
export function PlanBanner({ onUpgrade }: { onUpgrade: () => void }) {
  const { billing, isTrialing, isLocked, status, isSuperAdmin } = usePlan();
  if (isSuperAdmin || !billing) return null;

  if (isLocked) {
    return (
      <Bar
        tone="error"
        message="Your trial has ended. Choose a plan to reactivate your assistant."
        action="Choose a plan"
        onAction={onUpgrade}
      />
    );
  }
  if (status === "past_due") {
    return (
      <Bar
        tone="warning"
        message="We couldn't process your last payment. Update your billing to avoid interruption."
        action="Update billing"
        onAction={onUpgrade}
      />
    );
  }
  if (isTrialing) {
    const days = daysLeft(billing.trial_ends_at);
    const label =
      days === null
        ? "You're on a free trial."
        : days <= 1
          ? "Your free trial ends today."
          : `${days} days left in your free trial.`;
    return (
      <Bar tone="info" message={label} action="Upgrade" onAction={onUpgrade} />
    );
  }
  return null;
}

const TONE = {
  info: "border-sky-200 bg-sky-50 text-sky-800",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  error: "border-red-200 bg-red-50 text-red-700",
} as const;

const BUTTON = {
  info: "bg-sky-600 hover:bg-sky-700",
  warning: "bg-amber-600 hover:bg-amber-700",
  error: "bg-red-600 hover:bg-red-700",
} as const;

function Bar({
  tone,
  message,
  action,
  onAction,
}: {
  tone: keyof typeof TONE;
  message: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-3 border-b px-4 py-2 text-sm ${TONE[tone]}`}
    >
      <span className="min-w-0">{message}</span>
      <button
        type="button"
        onClick={onAction}
        className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium text-white transition ${BUTTON[tone]}`}
      >
        {action}
      </button>
    </div>
  );
}
