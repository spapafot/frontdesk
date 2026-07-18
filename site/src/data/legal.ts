// Legal content for the marketing site. Each entry becomes a real, crawlable
// route under /<slug> (see src/pages/[slug].astro).
//
// These are the published, product-accurate policies for Plug & Play. Keep them
// in sync with the actual data flows (see CLAUDE.md) and the billing behaviour
// in backend/app/services/billing.py + app/core/plans.py. The provider is named
// as the "Plug & Play" brand with contact@plugandplay.gr as the single contact;
// the registered legal entity is called out in a marked slot in each policy and
// can be filled in without touching anything else.
export type LegalPage = {
  title: string;
  summary: string;
  sections: Array<{ heading: string; body: string[] }>;
};

// Shown under every legal page heading. Bump when the policies change.
export const LEGAL_UPDATED = "17 July 2026";

// Single contact address for privacy, billing, and general enquiries.
export const LEGAL_CONTACT = "contact@plugandplay.gr";

export const LEGAL_PAGES: Record<string, LegalPage> = {
  "privacy-policy": {
    title: "Privacy Policy",
    summary:
      "This policy explains what personal data Plug & Play processes, why, who it is shared with, how long it is kept, and the rights you have under the EU General Data Protection Regulation (GDPR).",
    sections: [
      {
        heading: "Who is responsible for your data",
        body: [
          "Plug & Play (“we”, “us”) provides an embeddable, document-grounded customer-support assistant. For the personal data described here we act as the data controller for our own account and website data, and as a data processor for the content our customers place in their workspaces.",
          "The registered legal entity operating the Plug & Play service and its address will be identified here. Until then, you can reach us for any privacy question or request at " +
            LEGAL_CONTACT +
            ". We are based in Greece and the service is provided under Greek and EU law.",
        ],
      },
      {
        heading: "Information we process",
        body: [
          "Account data: your sign-in email and authentication details (handled by our authentication provider), plus workspace profile details such as the business name, assistant configuration, team-member invitations, and billing status.",
          "Knowledge base content: when an administrator uploads a document or adds a web page by its URL, we store the file or page name and its extracted text so the assistant can search it.",
          "Conversation data: when a website visitor chats with an assistant, we store the visitor's messages, the assistant's responses, the conversation title, any rating, and related analytics such as which questions went unanswered. If a conversation is escalated to a human operator, we also store the handoff and any callback request.",
          "Technical data: we and our infrastructure providers process IP addresses and request metadata to route traffic, apply rate limits, and keep the service secure.",
        ],
      },
      {
        heading: "How we use information",
        body: [
          "Uploaded and linked content is used to build the workspace's searchable knowledge base. Visitor messages and relevant conversation history are used to generate answers, short internal summaries, and analytics for the workspace administrator.",
          "We use billing data to operate subscriptions and account data to secure access, provide support, and send service and invite emails. We do not sell your personal data and we do not use conversation content to train our own models.",
          "Please do not upload, link to, or submit information you are not authorised to share, and website visitors should avoid sending sensitive personal information through the chat widget.",
        ],
      },
      {
        heading: "Service providers and where data goes",
        body: [
          "We rely on the following processors to run the service: our authentication and database provider (account, workspace, and conversation storage); OpenAI (to create search embeddings from uploaded text, and to screen widget messages for abuse); DeepSeek (to generate assistant answers and summaries from the relevant knowledge-base context and conversation content); Jina AI (to fetch a web page as text when an administrator adds it by URL, and to re-rank search results); Stripe (to process subscription and top-up payments - we never see or store your full card details); and our hosting and edge providers, which operate the servers and content-delivery/edge network that carry requests.",
          "Some of these providers process data outside the European Economic Area. Where that happens, transfers are covered by the safeguards those providers offer (such as the European Commission's Standard Contractual Clauses).",
          "Our marketing website uses Google Analytics to measure site usage, and only after you consent through the cookie banner - see the Cookie Policy.",
        ],
      },
      {
        heading: "How long we keep data",
        body: [
          "Administrators can delete individual documents and conversations from the admin workspace at any time; we then remove the corresponding active records and knowledge chunks.",
          "When a subscription ends - whether it is cancelled or a free trial expires without an upgrade - the account is locked and its data is retained for 30 days so you can reactivate without losing your workspace. After those 30 days we permanently delete the workspace's data from our active systems. Routine encrypted backups are cycled out shortly afterwards.",
          "We keep the minimum billing and transaction records that tax and accounting law requires us to retain, even after deletion of the workspace.",
        ],
      },
      {
        heading: "Your rights",
        body: [
          "Under the GDPR you can request access to your personal data, correction of inaccurate data, erasure, restriction of or objection to processing, and a copy of your data in a portable format. To exercise any of these rights, email " +
            LEGAL_CONTACT +
            ". We will respond within the time limits the GDPR sets.",
          "If you believe we have handled your data unlawfully, you have the right to lodge a complaint with the Hellenic Data Protection Authority (Hellenic DPA) or your local supervisory authority.",
        ],
      },
    ],
  },
  "terms-of-service": {
    title: "Terms of Service",
    summary:
      "These terms govern your use of Plug & Play. By creating an account, signing in, or using the service you agree to them.",
    sections: [
      {
        heading: "The service",
        body: [
          "Plug & Play provides a workspace for configuring a customer-support assistant, uploading source documents, reviewing conversations, and placing an embeddable chat widget on an authorised website origin. Some plans also allow handing a conversation to a live human operator.",
          "The assistant is designed to answer from the workspace's configured knowledge base. It may not have an answer when no relevant information is available.",
          "The provider of the service is Plug & Play (the registered operating entity is identified in the Privacy Policy). You can contact us at " +
            LEGAL_CONTACT +
            ".",
        ],
      },
      {
        heading: "Accounts and eligibility",
        body: [
          "You must be at least 18 years old and able to enter into a contract to open an account. You are responsible for the accuracy of your account details, for keeping your password secure, and for all activity that happens under your account and any team members you invite.",
          "When you sign in you confirm that you accept these Terms and our Privacy Policy. You must tell us promptly at " +
            LEGAL_CONTACT +
            " if you believe your account has been accessed without authorisation.",
        ],
      },
      {
        heading: "Your content and responsibilities",
        body: [
          "You are solely responsible for all content you add to your assistant's knowledge base - uploaded documents, instructions, and any web page you ingest by its URL - and you must hold all rights, licences, and permissions necessary to use that content for this purpose.",
          "When you add a web page by its URL, the service fetches that page through a third-party reader and stores the extracted text in your workspace. By adding a URL you confirm that you are authorised to ingest and use that page's content and that doing so does not infringe any third party's rights or the source website's terms.",
          "You must not use the service to process unlawful content, to infringe others' rights, or to attempt to breach its security or quota controls. We may remove content or suspend access if we receive a credible report of infringement or misuse, or if your use threatens the integrity of the service.",
        ],
      },
      {
        heading: "The widget and account security",
        body: [
          "The widget is authorised for one exact website origin and can be disabled or have its site key rotated from the workspace at any time. Public widget access is granted through short-lived signed sessions tied to that origin; do not attempt to reuse or share those credentials outside the authorised site.",
          "Usage is subject to the message and storage quotas of your plan (see Billing and Refunds). We may apply rate limits and abuse protections to keep the service available to everyone.",
        ],
      },
      {
        heading: "Subscriptions and payment",
        body: [
          "Paid plans, trials, renewals, cancellation, and refunds are described in the Billing and Refunds page, which forms part of these Terms.",
        ],
      },
      {
        heading: "Availability, warranties, and liability",
        body: [
          "The service is provided “as is” and “as available”. AI-generated responses can be incomplete or incorrect; do not treat a response as professional, legal, medical, financial, or other specialist advice. You are responsible for reviewing the content your assistant makes available to your visitors.",
          "To the fullest extent permitted by law, we exclude implied warranties and are not liable for indirect or consequential loss, loss of profits, or loss of data. Nothing in these Terms limits liability that cannot be limited under applicable law, including your statutory rights as a consumer. Where we are liable, our total liability is limited to the fees you paid for the service in the 12 months before the event giving rise to the claim.",
        ],
      },
      {
        heading: "Suspension, termination, and changes",
        body: [
          "You may stop using the service and cancel your subscription at any time. We may suspend or terminate access for a serious or repeated breach of these Terms, or where required by law. On termination, the data-retention and deletion rules in the Privacy Policy apply.",
          "We may update these Terms to reflect changes to the service or the law. Material changes will be reflected by the “last updated” date, and continued use after a change means you accept the updated Terms.",
        ],
      },
      {
        heading: "Governing law",
        body: [
          "These Terms are governed by the laws of Greece, and the courts of Greece have jurisdiction over any dispute, without prejudice to any mandatory consumer-protection rights you have in your country of residence.",
        ],
      },
    ],
  },
  "cookie-policy": {
    title: "Cookie Policy",
    summary:
      "This policy describes the cookies and browser storage used across the Plug & Play website and application, and how you control them.",
    sections: [
      {
        heading: "Analytics cookies on this website",
        body: [
          "This marketing website uses Google Analytics 4 to understand how visitors find and use the site. Analytics are governed by consent: no analytics cookies are set until you accept them through the cookie banner. Until then, Google Consent Mode keeps analytics storage disabled.",
          "When you accept, Google Analytics sets cookies (for example “_ga” and “_ga_<id>”) used to distinguish visitors and measure usage, and IP addresses are anonymised. Your accept-or-decline choice is remembered in your browser's local storage so the banner does not reappear on every visit.",
        ],
      },
      {
        heading: "Storage used by the application",
        body: [
          "The embedded chat widget uses browser local storage to remember a conversation identifier for the widget's configured website origin, so a visitor can continue a conversation after reopening the widget in the same browser.",
          "The admin application uses browser storage to remember the selected conversation, and our authentication provider uses browser storage to maintain your signed-in session. These are essential to the operation of the product and are not used for advertising.",
        ],
      },
      {
        heading: "Cookies and third parties",
        body: [
          "Google Analytics is the only analytics provider used on this website; Google acts as a third party that may process usage data on its own infrastructure. Our payment processor (Stripe) and our hosting and edge providers may set strictly necessary cookies as part of delivering and securing the service.",
          "We do not use advertising or cross-site tracking cookies.",
        ],
      },
      {
        heading: "Your controls",
        body: [
          "You can accept or decline analytics cookies from the cookie banner. To change your choice later, clear this site's browser storage and reload the page to bring the banner back, then choose again.",
          "You can also clear or block cookies and other browser storage through your browser settings. Blocking essential storage may prevent parts of the admin application or widget from working.",
        ],
      },
    ],
  },
  "billing-refunds": {
    title: "Billing and Refunds",
    summary:
      "How plans, trials, payments, renewals, cancellation, and refunds work for Plug & Play. This page forms part of the Terms of Service.",
    sections: [
      {
        heading: "Plans and trials",
        body: [
          "Plug & Play is offered on the Starter, Pro, and Business plans, each available on a monthly or annual billing cycle (annual is billed once a year and works out cheaper than paying monthly). The current plans, their message and storage allowances, and their prices are shown on our pricing page and at checkout.",
          "Every new account starts with a free 7-day trial with Starter-level limits and no credit card required. If you do not choose a paid plan before the trial ends, the account is locked (the widget stops answering and you cannot create new resources) but your data remains available for the retention period described below.",
        ],
      },
      {
        heading: "Payment and renewal",
        body: [
          "Payments are processed securely by Stripe. We do not receive or store your full card details. Prices are in euro (EUR) and exclusive of any VAT or taxes that may apply, which are shown at checkout.",
          "Paid subscriptions renew automatically at the end of each billing cycle (monthly or annual) using your saved payment method, until you cancel. You can view invoices, update your payment method, change plan, or cancel at any time from the Stripe billing portal linked in your account's Billing page.",
          "On any paid plan you can also buy one-time message top-up packs for the current month if you reach your allowance; top-up messages apply to the current billing month and do not roll over when the monthly quota resets.",
        ],
      },
      {
        heading: "Cancellation",
        body: [
          "You can cancel your subscription at any time from the billing portal. Cancellation stops future renewals; your plan stays active until the end of the period you have already paid for, after which the account is locked.",
          "If a renewal payment fails, we mark the subscription past-due and retry through Stripe; if it cannot be collected, the subscription is cancelled and the account is locked.",
        ],
      },
      {
        heading: "Refunds",
        body: [
          "The free 7-day trial is provided so you can evaluate the service before you pay. Because of this, subscription and top-up payments are non-refundable, including for partial periods and unused message allowance. Cancelling stops future charges but does not refund the current period.",
          "This does not affect any mandatory statutory rights you have as a consumer under applicable law. If you believe you were charged in error, contact us at " +
            LEGAL_CONTACT +
            " and we will look into it.",
        ],
      },
      {
        heading: "Your data after your subscription ends",
        body: [
          "When a subscription ends or a trial expires, your workspace data is retained for 30 days so you can reactivate without losing it, and is then permanently deleted. See the Privacy Policy for full details on retention and deletion.",
        ],
      },
    ],
  },
  "ai-use": {
    title: "AI Use Notice",
    summary:
      "Plug & Play uses AI services to generate answers and conversation summaries. This notice explains how that works and what to expect.",
    sections: [
      {
        heading: "How AI is used",
        body: [
          "The assistant searches the workspace knowledge base for relevant content and sends that context, together with the visitor's message, to an AI model to generate a response. Conversation content may also be sent to generate a short internal summary for workspace administrators.",
          "Messages sent through the public widget are also screened by an automated moderation service to detect abuse. See the Privacy Policy for the AI providers involved and how data is shared.",
        ],
      },
      {
        heading: "What to expect",
        body: [
          "Responses are generated automatically and may be incomplete or inaccurate. The assistant is configured to say when the knowledge base does not contain an answer, but that does not guarantee every response is correct.",
          "Avoid submitting sensitive information through the widget. Workspace administrators should review uploaded source material and assistant output for their intended use, and should not present AI answers as professional advice.",
        ],
      },
      {
        heading: "More information",
        body: [
          "See the Privacy Policy for the AI data flows and providers, and the Terms of Service for the limitations that apply to AI-generated content. For any question, contact " +
            LEGAL_CONTACT +
            ".",
        ],
      },
    ],
  },
};

// Controls the order shown in the footer and generated for static routes.
export const LEGAL_ORDER = [
  "privacy-policy",
  "terms-of-service",
  "cookie-policy",
  "billing-refunds",
  "ai-use",
] as const;
