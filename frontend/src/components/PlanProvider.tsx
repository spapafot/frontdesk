import { createContext, ReactNode, useContext } from "react";
import useSWR from "swr";
import { Billing, Entitlements, billingKey, getBilling } from "../api/billing";
import { useAuth } from "./AuthGate";

// While billing is loading (or unavailable), default to permissive entitlements
// so the app shell doesn't flicker features away on every reload. The backend
// is the real gate; these only drive optimistic UI.
const PERMISSIVE: Entitlements = {
  sites: null,
  messages: null,
  seats: null,
  knowledge_chunks: null,
  live_handoff: true,
  remove_branding: true,
};

interface PlanContextValue {
  billing: Billing | undefined;
  entitlements: Entitlements;
  plan: string;
  status: string;
  /** Trial expired / canceled and no active plan: the app is read-only. */
  isLocked: boolean;
  isTrialing: boolean;
  isSuperAdmin: boolean;
  isLoading: boolean;
  /** Re-fetch the billing status (used after a checkout returns). */
  refresh: () => Promise<Billing | undefined>;
}

const PlanContext = createContext<PlanContextValue>({
  billing: undefined,
  entitlements: PERMISSIVE,
  plan: "trial",
  status: "trialing",
  isLocked: false,
  isTrialing: false,
  isSuperAdmin: false,
  isLoading: true,
  refresh: async () => undefined,
});

/** Account-wide subscription/entitlement state for the whole admin app. */
export function usePlan() {
  return useContext(PlanContext);
}

export function PlanProvider({ children }: { children: ReactNode }) {
  const { isSuperAdmin } = useAuth();
  const { data: billing, isLoading, mutate } = useSWR(billingKey, getBilling);

  const entitlements = billing?.entitlements ?? PERMISSIVE;
  const status = billing?.status ?? "trialing";

  return (
    <PlanContext.Provider
      value={{
        billing,
        entitlements,
        plan: billing?.plan ?? "trial",
        status,
        isLocked: status === "locked" || status === "canceled",
        isTrialing: status === "trialing",
        isSuperAdmin,
        isLoading,
        refresh: () => mutate(),
      }}
    >
      {children}
    </PlanContext.Provider>
  );
}
