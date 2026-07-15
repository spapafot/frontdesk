import { useState } from "react";
import { Link } from "react-router-dom";
import useSWR from "swr";
import { getSettings, settingsKey } from "../api/settings";
import { WIDGET_SRC } from "../components/WidgetInstall";
import { useSite } from "../components/SiteProvider";

interface CodeBlockProps {
  code: string;
  label?: string;
}

function CodeBlock({ code, label }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // The code remains selectable when clipboard access is unavailable.
    }
  };

  return (
    <div>
      {label && <p className="mb-1 text-xs font-medium text-slate-600">{label}</p>}
      <div className="relative">
        <pre className="overflow-x-auto rounded-xl border border-slate-700 bg-slate-950 px-4 py-4 pr-20 text-xs leading-relaxed text-slate-100">
          <code>{code}</code>
        </pre>
        <button
          type="button"
          onClick={copy}
          className="absolute right-2 top-2 rounded-md border border-slate-600 bg-slate-800 px-2.5 py-1 text-[11px] font-medium text-slate-100 transition hover:bg-slate-700"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

const attributes = [
  {
    name: "data-site-key",
    required: true,
    defaultValue: "None",
    example: "pk_live_...",
    description: "Your public widget installation key from Settings.",
  },
  {
    name: "data-accent",
    required: false,
    defaultValue: "#0284c7",
    example: "#7c3aed",
    description: "CSS color used for the launcher, header, and send button.",
  },
  {
    name: "data-position",
    required: false,
    defaultValue: "bottom-right",
    example: "bottom-left",
    description: "Launcher position. Accepts bottom-right or bottom-left.",
  },
  {
    name: "data-greeting",
    required: false,
    defaultValue: "Hi! How can I help you today?",
    example: "Welcome! Ask us anything.",
    description: "First message displayed when a visitor opens the chat.",
  },
  {
    name: "data-api",
    required: false,
    defaultValue: "Widget script origin",
    example: "https://support.example.com",
    description: "Advanced: overrides the API origin used for sessions and chat.",
  },
  {
    name: "data-app",
    required: false,
    defaultValue: "app/index.html beside the script",
    example: "https://cdn.example.com/app/index.html",
    description: "Advanced: overrides the iframe application URL.",
  },
];

export function WidgetDocsPage() {
  const { selectedSiteId } = useSite();
  const { data: settings } = useSWR(
    selectedSiteId != null ? settingsKey(selectedSiteId) : null,
    () => getSettings(selectedSiteId as number)
  );
  const siteKey = settings?.public_key ?? "YOUR_SITE_KEY";
  const snippet = `<script
  src="${WIDGET_SRC}"
  data-site-key="${siteKey}"
  data-accent="#0284c7"
  data-position="bottom-right"
  data-greeting="Hi! How can I help you today?"
  async
></script>`;

  return (
    <div className="h-full overflow-y-auto">
        <div className="bg-gradient-to-br from-sky-700 via-sky-600 to-cyan-500 px-6 py-10 text-white">
          <div className="mx-auto max-w-4xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-100">
            Installation guide
          </p>
          <h1 className="mt-2 text-2xl font-semibold sm:text-3xl">
            Add the chat widget to your website
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-sky-50">
            Install one script before the closing body tag. The launcher is isolated
            from your website styles and the full chat loads only when a visitor opens it.
          </p>
          </div>
        </div>
      <article className="mx-auto max-w-4xl px-6 py-6">

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
            <div>
              <h2 className="text-lg font-semibold text-slate-800">Before you install</h2>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                In Settings, enter the exact website origin, such as
                <code className="mx-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs">
                  https://example.com
                </code>
                and make sure the widget is enabled.
              </p>
            </div>
            <Link
              to="/settings"
              className="shrink-0 rounded-full bg-sky-600 px-4 py-2 text-center text-xs font-medium text-white transition hover:bg-sky-700"
            >
              Open Settings
            </Link>
          </div>
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">
            The origin includes the protocol and domain, but no page path. A widget
            authorized for <strong>https://example.com</strong> will not run on
            <strong> https://www.example.com</strong> unless that exact origin is configured.
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-800">Standard installation</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Paste this once on every page where the widget should appear, preferably just
            before <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">&lt;/body&gt;</code>.
          </p>
          <div className="mt-4">
            <CodeBlock code={snippet} label="Your embed code" />
          </div>
          {!settings?.public_key && (
            <p className="mt-2 text-xs text-slate-500">
              Your site key will appear here after Settings finishes loading.
            </p>
          )}
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-800">Widget attributes</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            Add or change these attributes directly on the script tag. Attribute names
            are lowercase and values must remain inside quotes.
          </p>
          <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-[760px] w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-3 font-semibold">Attribute</th>
                  <th className="px-4 py-3 font-semibold">Required</th>
                  <th className="px-4 py-3 font-semibold">Default</th>
                  <th className="px-4 py-3 font-semibold">Example</th>
                  <th className="px-4 py-3 font-semibold">Purpose</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-slate-700">
                {attributes.map((attribute) => (
                  <tr key={attribute.name} className="align-top">
                    <td className="whitespace-nowrap px-4 py-3 font-mono font-medium text-sky-700">
                      {attribute.name}
                    </td>
                    <td className="px-4 py-3">{attribute.required ? "Yes" : "No"}</td>
                    <td className="max-w-44 px-4 py-3">{attribute.defaultValue}</td>
                    <td className="max-w-44 break-all px-4 py-3 font-mono text-[11px]">
                      {attribute.example}
                    </td>
                    <td className="min-w-56 px-4 py-3 leading-5">{attribute.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs leading-5 text-slate-500">
            Most installations only need the site key, accent, position, and greeting.
            Use the API and app overrides only when your deployment administrator gives
            you specific URLs.
          </p>
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-800">Install on WordPress</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            The exact menu names vary by theme and hosting provider. Use the first option
            your WordPress setup supports.
          </p>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-800">Site-wide custom code</p>
              <ol className="mt-3 list-decimal space-y-2 pl-5 text-xs leading-5 text-slate-600">
                <li>Open your theme, builder, or hosting provider's custom-code area.</li>
                <li>Choose the footer or end-of-body location.</li>
                <li>Paste the standard installation snippet once.</li>
                <li>Apply it site-wide, save, and clear all WordPress/CDN caches.</li>
              </ol>
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-800">Header/footer code plugin</p>
              <ol className="mt-3 list-decimal space-y-2 pl-5 text-xs leading-5 text-slate-600">
                <li>Install a reputable script or header/footer insertion plugin.</li>
                <li>Create an HTML/JavaScript snippet for the frontend only.</li>
                <li>Select footer or before closing body, then enable it site-wide.</li>
                <li>Paste the code, save, clear caches, and test while signed out.</li>
              </ol>
            </div>
          </div>

          <div className="mt-4 rounded-xl bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-600">
            Avoid editing a parent theme's <code>footer.php</code> directly: theme updates
            can remove the change. A Custom HTML block usually installs the widget on only
            that page, and some WordPress accounts strip script tags from editor content.
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-800">Other website builders</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {[
              ["Shopify", "Add the snippet to the theme layout before </body>, or use the store's supported custom-code mechanism."],
              ["Webflow", "Place it in site-wide custom code before </body>, publish the site, then test the published domain."],
              ["HTML / React", "Add the script to the shared HTML shell or layout once, after the main content and before </body>."],
            ].map(([title, body]) => (
              <div key={title} className="rounded-xl border border-slate-200 p-4">
                <p className="text-sm font-semibold text-slate-800">{title}</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">{body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-800">Troubleshooting</h2>
          <div className="mt-4 divide-y divide-slate-200">
            {[
              ["The launcher does not appear", "Confirm the script is present in the published page source, the site key is included, and browser or CDN caches were cleared."],
              ["Widget authorization failed", "Check that Settings contains the exact origin shown in the browser address bar and that the widget is enabled."],
              ["It works for admins but not visitors", "Test in a private window. WordPress optimization or consent tools may delay or block scripts for signed-out visitors."],
              ["The wrong side or color is used", "Check for a second copy of the widget script and verify data-position and data-accent are on the same script tag."],
              ["A strict Content Security Policy blocks it", "Allow the widget host in the site's script-src, connect-src, and frame-src directives, then retest the browser console."],
            ].map(([title, body]) => (
              <div key={title} className="py-4 first:pt-0 last:pb-0">
                <p className="text-sm font-medium text-slate-800">{title}</p>
                <p className="mt-1 text-xs leading-5 text-slate-600">{body}</p>
              </div>
            ))}
          </div>
        </section>
      </article>
    </div>
  );
}
