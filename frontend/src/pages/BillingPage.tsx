import { ReactNode, useState } from "react";
import { Check } from "lucide-react";
import {
  BillingInterval,
  PaidPlan,
  TOPUP_PACK_PRICE,
  TOPUP_PACK_SIZE,
  createCheckout,
  createPortal,
  createTopup,
} from "../api/billing";
import { PlanStatusBadge } from "../components/PlanStatusBadge";
import { Spinner } from "../components/Spinner";
import { usePlan } from "../components/PlanProvider";
import { useToast } from "../components/Toast";

interface Tier {
  id: PaidPlan;
  name: string;
  monthly: number;
  yearly: number;
  blurb: string;
  features: string[];
  highlighted?: boolean;
}

const TIERS: Tier[] = [
  {
    id: "starter",
    name: "Starter",
    monthly: 13,
    yearly: 130,
    blurb: "For a single website that just needs a chatbot.",
    features: [
      "Up to 1 website",
      "500 messages / month",
      "50 MB knowledge base",
      "1 seat",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    monthly: 39,
    yearly: 390,
    blurb: "For growing teams that want live handoff.",
    features: [
      "Up to 3 websites",
      "5,000 messages / month",
      "500 MB knowledge base",
      "5 seats",
      "Live human handoff",
      "Remove branding",
    ],
    highlighted: true,
  },
  {
    id: "business",
    name: "Business",
    monthly: 159,
    yearly: 1590,
    blurb: "For agencies and multi-brand operators.",
    features: [
      "Up to 20 websites",
      "50,000 messages / month",
      "2 GB knowledge base",
      "Unlimited seats",
      "Live human handoff",
      "Remove branding",
      "Priority support",
    ],
  },
];

function formatResetDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function BillingPage() {
  const { billing, isLoading, plan, status } = usePlan();
  const { showToast } = useToast();
  const [interval, setInterval] = useState<BillingInterval>("month");
  const [busy, setBusy] = useState<string | null>(null);
  const [packs, setPacks] = useState(1);

  const onSelect = async (tier: PaidPlan) => {
    setBusy(tier);
    try {
      const { url } = await createCheckout(tier, interval);
      window.location.href = url;
    } catch (error) {
      showToast(
        error instanceof Error ? error.message : "Could not start checkout.",
      );
      setBusy(null);
    }
  };

  const onManage = async () => {
    setBusy("portal");
    try {
      const { url } = await createPortal();
      window.location.href = url;
    } catch (error) {
      showToast(
        error instanceof Error ? error.message : "Could not open billing.",
      );
      setBusy(null);
    }
  };

  const onTopup = async () => {
    setBusy("topup");
    try {
      const { url } = await createTopup(packs);
      window.location.href = url;
    } catch (error) {
      showToast(
        error instanceof Error ? error.message : "Could not start checkout.",
      );
      setBusy(null);
    }
  };

  const manageable = billing?.manageable ?? false;
  const usage = billing?.usage;
  const usagePct =
    usage && usage.messages_limit
      ? Math.min(
          100,
          Math.round((usage.messages_used / usage.messages_limit) * 100),
        )
      : 0;
  const knowledge = billing?.knowledge;
  const knowledgePct =
    knowledge && knowledge.chunks_limit
      ? Math.min(
          100,
          Math.round((knowledge.chunks_used / knowledge.chunks_limit) * 100),
        )
      : 0;
  // ~100 chunks ≈ 1 MB of database (see plans.CHUNKS_PER_MB).
  const mb = (chunks: number) => Math.round(chunks / 100);
  // Every active paid plan can add messages for a month that runs over.
  const canTopup =
    manageable &&
    status === "active" &&
    (plan === "starter" || plan === "pro" || plan === "business");
  // With a live subscription, a tier button becomes a plan *switch*: the
  // backend returns a portal subscription-update link instead of a new
  // Checkout (a second Checkout subscription would double-bill).
  const isSwitching =
    (status === "active" || status === "past_due") &&
    Boolean(billing?.has_stripe_customer);

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-slate-100">
      <header className="border-b border-slate-200 bg-white px-6 py-5">
        <h1 className="text-lg font-semibold text-slate-900">
          Billing &amp; plan
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Manage your subscription, usage, and payment details.
        </p>
      </header>

      <div className="mx-auto w-full max-w-5xl px-6 py-6">
        {isLoading ? (
          <div className="flex justify-center py-16" role="status">
            <Spinner className="h-6 w-6" label="Loading billing" />
          </div>
        ) : (
          <>
            {/* Current plan + usage */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <span className="text-sm font-semibold text-slate-900">
                    {plan === "superadmin"
                      ? "Internal (unlimited)"
                      : `${plan.charAt(0).toUpperCase()}${plan.slice(1)} plan`}
                  </span>
                  <PlanStatusBadge status={status} />
                </div>
                {manageable && billing?.has_stripe_customer && (
                  <button
                    type="button"
                    onClick={onManage}
                    disabled={busy !== null}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
                  >
                    {busy === "portal" ? "Opening…" : "Manage billing"}
                  </button>
                )}
              </div>

              {usage && (
                <div className="mt-4">
                  <div className="flex items-center justify-between text-sm text-slate-600">
                    <span>Messages this month</span>
                    <span className="tabular-nums">
                      {usage.messages_used.toLocaleString()}
                      {usage.messages_limit != null
                        ? ` / ${usage.messages_limit.toLocaleString()}`
                        : " (unlimited)"}
                      {usage.bonus_messages > 0
                        ? ` (+${usage.bonus_messages.toLocaleString()} top-up)`
                        : ""}
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
                  {usage.resets_at && (
                    <p className="mt-1.5 text-xs text-slate-400">
                      Resets {formatResetDate(usage.resets_at)}
                    </p>
                  )}
                </div>
              )}

              {knowledge && (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <div className="flex items-center justify-between text-sm text-slate-600">
                    <span>Knowledge base</span>
                    <span className="tabular-nums">
                      {knowledge.chunks_used.toLocaleString()}
                      {knowledge.chunks_limit != null
                        ? ` / ${knowledge.chunks_limit.toLocaleString()} chunks`
                        : " chunks (unlimited)"}
                    </span>
                  </div>
                  {knowledge.chunks_limit != null && (
                    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full ${knowledgePct >= 100 ? "bg-red-500" : "bg-sky-600"}`}
                        style={{ width: `${knowledgePct}%` }}
                      />
                    </div>
                  )}
                  <p className="mt-1.5 text-xs text-slate-400">
                    {knowledge.chunks_limit != null
                      ? `~${mb(knowledge.chunks_used)} MB of ${mb(knowledge.chunks_limit)} MB used. `
                      : ""}
                    ~100 chunks ≈ 1 MB · an FAQ ≈ 1 chunk, a page ≈ 3 chunks.
                  </p>
                </div>
              )}
            </div>

            {!manageable && (
              <p className="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                Billing for this account is managed by your account owner.
              </p>
            )}

            {canTopup && (
              <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-5">
                <h3 className="text-sm font-semibold text-slate-900">
                  Need more messages this month?
                </h3>
                <p className="mt-1 text-sm text-slate-500">
                  Add {TOPUP_PACK_SIZE.toLocaleString()}-message packs for €
                  {TOPUP_PACK_PRICE} each. Extra messages apply to the current
                  month only and reset with your quota.
                </p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <div className="inline-flex items-center rounded-xl border border-slate-200">
                    <button
                      type="button"
                      aria-label="Fewer packs"
                      onClick={() => setPacks((p) => Math.max(1, p - 1))}
                      disabled={packs <= 1}
                      className="px-3 py-2 text-slate-500 transition hover:bg-slate-50 disabled:opacity-40"
                    >
                      −
                    </button>
                    <span className="min-w-[3rem] text-center text-sm font-medium tabular-nums text-slate-800">
                      {packs}
                    </span>
                    <button
                      type="button"
                      aria-label="More packs"
                      onClick={() => setPacks((p) => Math.min(50, p + 1))}
                      disabled={packs >= 50}
                      className="px-3 py-2 text-slate-500 transition hover:bg-slate-50 disabled:opacity-40"
                    >
                      +
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={onTopup}
                    disabled={busy !== null}
                    className="rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
                  >
                    {busy === "topup"
                      ? "Redirecting…"
                      : `Add ${(packs * TOPUP_PACK_SIZE).toLocaleString()} messages - €${packs * TOPUP_PACK_PRICE}`}
                  </button>
                </div>
              </div>
            )}

            {manageable && (
              <>
                {/* Billing cycle toggle */}
                <div className="mt-8 flex items-center justify-center gap-2">
                  <CycleButton
                    active={interval === "month"}
                    onClick={() => setInterval("month")}
                  >
                    Monthly
                  </CycleButton>
                  <CycleButton
                    active={interval === "year"}
                    onClick={() => setInterval("year")}
                  >
                    Yearly · 2 months free
                  </CycleButton>
                </div>

                {/* Tier grid */}
                <div className="mt-6 grid gap-6 md:grid-cols-3">
                  {TIERS.map((tier) => {
                    // Current = same plan AND same interval (a Pro-monthly user
                    // switching the toggle to Yearly sees a live switch button).
                    const isCurrent =
                      plan === tier.id &&
                      status === "active" &&
                      (billing?.billing_interval == null ||
                        billing.billing_interval === interval);
                    const price =
                      interval === "month" ? tier.monthly : tier.yearly;
                    return (
                      <div
                        key={tier.id}
                        className={`flex flex-col rounded-2xl border bg-white p-5 ${tier.highlighted ? "border-sky-500 ring-1 ring-sky-200" : "border-slate-200"}`}
                      >
                        <div className="flex items-center gap-2">
                          <h3 className="text-base font-semibold text-slate-900">
                            {tier.name}
                          </h3>
                          {tier.highlighted && (
                            <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] font-semibold text-sky-700">
                              Most popular
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-slate-500">
                          {tier.blurb}
                        </p>
                        <div className="mt-4">
                          <span className="text-3xl font-semibold text-slate-900">
                            €{price}
                          </span>
                          <span className="text-sm text-slate-500">
                            {interval === "month" ? " / month" : " / year"}
                          </span>
                        </div>
                        <ul className="mt-4 flex-1 space-y-2">
                          {tier.features.map((feature) => (
                            <li
                              key={feature}
                              className="flex items-start gap-2 text-sm text-slate-600"
                            >
                              <Check
                                className="mt-0.5 h-4 w-4 shrink-0 text-sky-600"
                                aria-hidden="true"
                              />
                              {feature}
                            </li>
                          ))}
                        </ul>
                        <button
                          type="button"
                          disabled={isCurrent || busy !== null}
                          onClick={() => onSelect(tier.id)}
                          className={`mt-5 w-full rounded-xl px-4 py-2.5 text-sm font-medium transition disabled:opacity-60 ${
                            tier.highlighted
                              ? "bg-sky-600 text-white hover:bg-sky-700"
                              : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                          }`}
                        >
                          {isCurrent
                            ? "Current plan"
                            : busy === tier.id
                              ? "Redirecting…"
                              : `${isSwitching ? "Switch to" : "Choose"} ${tier.name}`}
                        </button>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-6 text-center text-xs text-slate-400">
                  Prices in EUR. Taxes calculated at checkout. Cancel anytime.
                </p>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function CycleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
        active
          ? "bg-sky-600 text-white"
          : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
      }`}
    >
      {children}
    </button>
  );
}
