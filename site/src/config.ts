// Central site metadata. Keep brand and URLs here so pages and schema markup
// stay consistent.
export const SITE = {
  name: "Plug & Play",
  // Used in <title> suffixes and schema. The ampersand is safe in text nodes;
  // it is only escaped when placed inside attributes.
  tagline: "Customer support, grounded in your own documents",
  description:
    "Plug & Play turns the documents you already have into a support assistant that answers in your customer's language- grounded only in what you've approved. Add one line of code and it's live.",
  url: "https://plugandplay.gr",
  // Where the marketing CTAs send people to sign in / register.
  appUrl: import.meta.env.PUBLIC_APP_URL ?? "https://app.plugandplay.gr",
  locale: "en",
  ogImage: "/og.png",
  // Google Analytics 4 measurement ID. Analytics only load after the visitor
  // grants consent (Consent Mode v2 defaults to denied - see Analytics.astro).
  gaMeasurementId: "G-6E65S82JQN",
} as const;

export const NAV = {
  features: "/#features",
  login: SITE.appUrl,
  register: SITE.appUrl,
} as const;
