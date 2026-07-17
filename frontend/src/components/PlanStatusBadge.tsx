const STATUS_BADGE: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  trialing: "bg-amber-100 text-amber-700",
  past_due: "bg-amber-100 text-amber-700",
  locked: "bg-red-100 text-red-700",
  canceled: "bg-red-100 text-red-700",
};

const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  trialing: "Trial",
  past_due: "Payment due",
  locked: "Expired",
  canceled: "Canceled",
};

/** Subscription status pill, shared by the Billing and Account pages. */
export function PlanStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_BADGE[status] ?? "bg-slate-100 text-slate-600"}`}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
