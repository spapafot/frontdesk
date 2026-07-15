import { useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE } from "../api/client";

interface Props {
  siteKey: string | null;
  accentColor: string;
  launcherIcon: string;
  launcherPosition: string;
  greeting: string;
  launcherLabel: string;
  showBranding: boolean;
  onRotate: () => Promise<void>;
}

// Where the built widget loader is hosted in production. Overridable at build
// time via VITE_WIDGET_SRC; falls back to a sensible placeholder.
export const WIDGET_SRC =
  (import.meta.env.VITE_WIDGET_SRC as string | undefined) ??
  "https://cdn.yourdomain.com/widget.js";

// Escape a value for safe inclusion inside a double-quoted HTML attribute.
function attrEscape(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function WidgetInstall({
  siteKey,
  accentColor,
  launcherIcon,
  launcherPosition,
  greeting,
  launcherLabel,
  showBranding,
  onRotate,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);

  if (!siteKey) return null;

  // The loader defaults its API base to wherever widget.js is served. In this
  // deployment the widget assets live on the CDN/Pages host, which does not
  // serve the API, so we pin data-api to the API origin explicitly. Appearance
  // is carried as data-* attributes reflecting what was saved above.
  const lines = [
    `  src="${WIDGET_SRC}"`,
    `  data-site-key="${siteKey}"`,
    `  data-api="${API_BASE}"`,
    `  data-accent="${attrEscape(accentColor)}"`,
    `  data-position="${launcherPosition}"`,
    `  data-icon="${launcherIcon}"`,
    `  data-greeting="${attrEscape(greeting)}"`,
  ];
  if (launcherLabel.trim()) {
    lines.push(`  data-launcher-label="${attrEscape(launcherLabel.trim())}"`);
  }
  if (!showBranding) {
    lines.push(`  data-branding="false"`);
  }
  lines.push("  async");
  const snippet = `<script\n${lines.join("\n")}\n></script>`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard may be unavailable; user can still select manually.
    }
  };

  return (
    <section className="mt-5 max-w-3xl rounded-2xl border border-slate-200 bg-white p-5">
      <h3 className="text-sm font-semibold text-slate-800">
        Install on your website
      </h3>
      <p className="mt-1 text-xs text-slate-500">
        Paste this snippet just before the closing &lt;/body&gt; tag on your
        site.
      </p>
      <Link
        to="/widget-guide"
        className="mt-2 inline-block text-xs font-medium text-sky-700 hover:text-sky-800 hover:underline"
      >
        View the full installation and WordPress guide
      </Link>

      <div className="mt-3">
        <label className="block text-xs font-medium text-slate-600">
          Site key
        </label>
        <code className="mt-1.5 block w-full break-all rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-700">
          {siteKey}
        </code>
      </div>

      <div className="mt-3">
        <label className="block text-xs font-medium text-slate-600">
          Embed snippet
        </label>
        <pre className="mt-1.5 overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">
          {snippet}
        </pre>
        <button
          type="button"
          onClick={copy}
          className="mt-2 rounded-xl bg-slate-800 px-4 py-2 text-xs font-medium text-white transition hover:bg-slate-700"
        >
          {copied ? "Copied" : "Copy snippet"}
        </button>
        <button
          type="button"
          disabled={rotating}
          onClick={async () => {
            if (
              !window.confirm(
                "Rotate this key? Existing widget sessions will stop working.",
              )
            )
              return;
            setRotating(true);
            try {
              await onRotate();
            } finally {
              setRotating(false);
            }
          }}
          className="ml-2 rounded-xl border border-red-200 px-4 py-2 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-50"
        >
          {rotating ? "Rotating..." : "Rotate key"}
        </button>
      </div>
    </section>
  );
}
