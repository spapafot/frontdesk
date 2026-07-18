// Marketing pricing tiers. Keep in sync with the backend plan limits
// (backend/app/core/plans.py) and the in-app Billing page.

export interface PricingTier {
  id: "starter" | "pro" | "business";
  name: string;
  priceMonthly: number; // EUR / month
  priceYearly: number; // EUR / year (2 months free)
  tagline: string;
  features: string[];
  highlighted?: boolean;
}

export const PRICING_TIERS: PricingTier[] = [
  {
    id: "starter",
    name: "Starter",
    priceMonthly: 13,
    priceYearly: 130,
    tagline: "For a single website that just needs a chatbot.",
    features: [
      "Up to 1 website",
      "500 messages / month",
      "50 MB knowledge base",
      "1 seat",
      "Grounded, multilingual answers",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    priceMonthly: 39,
    priceYearly: 390,
    tagline: "For growing teams that want live handoff.",
    highlighted: true,
    features: [
      "Up to 3 websites",
      "5,000 messages / month",
      "500 MB knowledge base",
      "5 seats",
      "Live human handoff",
      "Remove branding",
    ],
  },
  {
    id: "business",
    name: "Business",
    priceMonthly: 159,
    priceYearly: 1590,
    tagline: "For agencies and multi-brand operators.",
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

export const TRIAL_NOTE =
  "Every plan starts with a free 7-day trial - no credit card required.";

export const MESSAGE_TOPUP = {
  messages: 1_000,
  price: 5,
} as const;
