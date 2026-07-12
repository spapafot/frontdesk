// Legal content for the marketing site. Ported from the former in-app
// PublicSite drafts and rebranded to Plug & Play. Each entry becomes a real,
// crawlable route under /<slug>.
export type LegalPage = {
  title: string;
  summary: string;
  sections: Array<{ heading: string; body: string[] }>;
};

export const LEGAL_PAGES: Record<string, LegalPage> = {
  "privacy-policy": {
    title: "Privacy Policy",
    summary:
      "This draft explains the data flows currently visible in Plug & Play. It must be completed with the business details and practices listed below before publication.",
    sections: [
      {
        heading: "Information used by the service",
        body: [
          "Plug & Play processes account sign-in information through its authentication service. It also stores workspace profile details, such as the business name and assistant settings.",
          "When an administrator uploads a document, the document name and extracted text are stored in the workspace knowledge base. When a website visitor chats with an assistant, the service stores the visitor's messages, assistant responses, conversation title, rating, and related analytics information.",
        ],
      },
      {
        heading: "How information is used",
        body: [
          "Uploaded content is used to build the assistant's searchable knowledge base. Chat messages and relevant conversation history are used to generate responses. Workspace administrators can review conversations, ratings, summaries, and unanswered questions in the admin workspace.",
          "Do not upload or submit information unless you are authorised to share it. Website visitors should avoid sending sensitive information through the chat widget.",
        ],
      },
      {
        heading: "AI and service providers",
        body: [
          "The current application sends uploaded document text to OpenAI to create search embeddings. It sends chat content, relevant knowledge-base context, and conversation content used for summaries to DeepSeek to generate responses and summaries.",
          "The application architecture also uses Supabase for authentication and database services, and the marketing website uses Google Analytics to measure site usage after a visitor consents (see the Cookie Policy). Production hosting and edge services must be confirmed before a final policy identifies all providers and applicable data locations.",
        ],
      },
      {
        heading: "Storage and deletion",
        body: [
          "Workspace administrators can delete individual documents and conversations from the admin workspace. The application deletes the corresponding active database records and document chunks.",
          "This draft does not state a retention period or make a claim about backups, logs, or third-party retention. Those details must be confirmed before publication.",
        ],
      },
      {
        heading: "Your questions and choices",
        body: [
          "A final policy must identify the organisation responsible for Plug & Play, provide a privacy contact, explain available privacy choices, and state how requests are handled. Those details are not yet configured in the application.",
        ],
      },
    ],
  },
  "terms-of-service": {
    title: "Terms of Service",
    summary:
      "These service-use terms describe the product at a high level. They are a draft and are not a substitute for reviewed contractual terms.",
    sections: [
      {
        heading: "The service",
        body: [
          "Plug & Play provides a workspace for configuring a customer-support assistant, uploading source documents, reviewing conversations, and placing an embeddable chat widget on an authorised website origin.",
          "The assistant is designed to answer using the workspace's configured knowledge base. It may not have an answer when no relevant information is available.",
        ],
      },
      {
        heading: "Your content and responsibilities",
        body: [
          "You are responsible for the documents, instructions, and other content you provide to configure your assistant, including having the necessary rights and permissions to use that content.",
          "You should review your assistant's configuration and the information it makes available to website visitors.",
        ],
      },
      {
        heading: "Account and widget access",
        body: [
          "The admin workspace uses email-and-password sign-in when authentication is enabled. The widget is configured for one exact website origin and can be disabled or have its site key rotated from the workspace.",
          "A final version must define account eligibility, security responsibilities, suspension, termination, and support arrangements.",
        ],
      },
      {
        heading: "Important limitations",
        body: [
          "AI-generated responses can be incomplete or incorrect. Do not treat a response as professional, legal, medical, financial, or other specialist advice unless your own reviewed content and service process make that appropriate.",
          "A qualified lawyer must supply the final provisions on warranties, liability, disputes, governing law, and any other contractual protections.",
        ],
      },
    ],
  },
  "cookie-policy": {
    title: "Cookie Policy",
    summary:
      "This draft describes the cookies and browser storage used across the Plug & Play website and application. It is not yet a completed cookie inventory.",
    sections: [
      {
        heading: "Analytics cookies on this website",
        body: [
          "This marketing website uses Google Analytics 4 to understand how visitors find and use the site. Analytics are governed by consent: no analytics cookies are set until you accept them through the cookie banner. Until then, Google Consent Mode keeps analytics storage disabled.",
          "When you accept, Google Analytics sets cookies (for example “_ga” and “_ga_<id>”) used to distinguish visitors and measure usage, and IP addresses are anonymised. Your accept-or-decline choice is remembered in your browser's local storage so the banner does not reappear on every visit.",
        ],
      },
      {
        heading: "Browser storage used by the application",
        body: [
          "The embedded chat widget uses browser local storage to remember a conversation identifier for the widget's configured website origin. This lets a visitor continue a conversation after reopening the widget in the same browser.",
          "The admin application also uses browser storage to remember the selected conversation. Its authentication provider may use browser storage to maintain an authenticated session.",
        ],
      },
      {
        heading: "Cookies and third parties",
        body: [
          "Google Analytics is the analytics provider used on this website; Google acts as a third party that may process usage data on its own infrastructure. Hosting, authentication, and other production services may set additional cookies or use other storage; this must be verified in the deployed product before publication.",
          "Do not describe additional analytics or advertising technologies here unless they are actually in use and have been verified.",
        ],
      },
      {
        heading: "Your controls",
        body: [
          "You can accept or decline analytics cookies from the cookie banner. To change your choice later, clear this site's browser storage and reload the page to bring the banner back, then choose again.",
          "You can also clear or block cookies and other browser storage through your browser settings. A final policy should list the specific cookies, providers, and retention periods, and explain any additional in-product controls, once confirmed.",
        ],
      },
    ],
  },
  "billing-refunds": {
    title: "Billing and Refunds",
    summary:
      "Billing, payment, subscription, and refund functionality is not present in the current application. No commercial terms are published here.",
    sections: [
      {
        heading: "Before this page is published",
        body: [
          "Confirm the payment provider, plans, prices, billing frequency, taxes, trials, renewal rules, cancellation path, access after cancellation, refund eligibility, and support contact.",
          "Do not describe Stripe flows, automatic renewals, cancellation timing, or refunds until those flows exist and have been verified end to end.",
        ],
      },
    ],
  },
  "ai-use": {
    title: "AI Use Notice",
    summary:
      "Plug & Play uses AI services to help provide responses and conversation summaries. This notice explains the product behaviour visible today.",
    sections: [
      {
        heading: "How AI is used",
        body: [
          "The assistant searches the workspace knowledge base for relevant content and sends that context with the visitor's message to an AI model to generate a response. Conversation content may also be sent to generate a short internal summary for workspace administrators.",
        ],
      },
      {
        heading: "What to expect",
        body: [
          "Responses are generated automatically and may be incomplete or inaccurate. The assistant is configured to say when the knowledge base does not contain an answer, but that does not guarantee every response is correct.",
          "Avoid submitting sensitive information through the widget. Workspace administrators should review uploaded source material and assistant output for their intended use.",
        ],
      },
      {
        heading: "More information",
        body: [
          "See the Privacy Policy for the currently identified AI data flows. A final notice should include the responsible organisation and support contact.",
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
