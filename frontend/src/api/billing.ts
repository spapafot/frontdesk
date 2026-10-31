import { API_BASE, parse } from "./client";

export interface Entitlements {
  sites: number | null;
  messages: number | null;
  seats: number | null;
  knowledge_chunks: number | null;
  live_handoff: boolean;
  remove_branding: boolean;
}

export interface BillingUsage {
  messages_used: number;
  messages_limit: number | null;
  bonus_messages: number;
  resets_at: string;
}

export interface KnowledgeUsage {
  // Chunks are the enforced unit; ~100 chunks ≈ 1 MB.
  chunks_used: number;
  chunks_limit: number | null;
}

export interface Billing {
  // "trial" | "starter" | "pro" | "business" | "superadmin"
  plan: string;
  // "trialing" | "active" | "past_due" | "canceled" | "locked"
  status: string;
  manageable: boolean;
  has_stripe_customer: boolean;
  // "month" | "year"; null until the first Stripe subscription exists.
  billing_interval: string | null;
  trial_ends_at: string | null;
  current_period_end: string | null;
  entitlements: Entitlements;
  usage: BillingUsage;
  knowledge: KnowledgeUsage;
}

export type BillingInterval = "month" | "year";
export type PaidPlan = "starter" | "pro" | "business";

export const billingKey = `${API_BASE}/billing`;

export async function getBilling(): Promise<Billing> {
  return parse(await fetch(billingKey));
}

export async function createCheckout(
  plan: PaidPlan,
  interval: BillingInterval
): Promise<{ url: string }> {
  return parse(
    await fetch(`${API_BASE}/billing/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan, interval }),
    })
  );
}

export async function createPortal(): Promise<{ url: string }> {
  return parse(await fetch(`${API_BASE}/billing/portal`, { method: "POST" }));
}

// Number of messages per top-up pack (mirrors the backend TOPUP_PACK_SIZE).
export const TOPUP_PACK_SIZE = 1000;
export const TOPUP_PACK_PRICE = 5; // EUR per pack

export async function createTopup(packs: number): Promise<{ url: string }> {
  return parse(
    await fetch(`${API_BASE}/billing/topup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ packs }),
    })
  );
}
