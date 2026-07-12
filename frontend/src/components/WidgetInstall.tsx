import { useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE } from "../api/client";

interface Props {
  siteKey: string | null;
  onRotate: () => Promise<void>;
}

// Where the built widget loader is hosted in production. Overridable at build
// time via VITE_WIDGET_SRC; falls back to a sensible placeholder.
export const WIDGET_SRC =
  (import.meta.env.VITE_WIDGET_SRC as string | undefined) ??
  "https://cdn.yourdomain.com/widget.js";

export function WidgetInstall({ siteKey, onRotate }: Props) {
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);

  if (!siteKey) return null;

  // The loader defaults its API base to wherever widget.js is served. In this
  // deployment the widget assets live on the CDN/Pages host, which does not
  // serve the API, so we pin data-api to the API origin explicitly.
  const snippet = `<script
  src="${WIDGET_SRC}"
  data-site-key="${siteKey}"
  data-api="${API_BASE}"
  data-accent="#0284c7"
  data-position="bottom-right"
  async
></script>`;

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
    <div className="mt-8 border-t border-slate-200 pt-6">
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
        <code className="mt-1 block w-full break-all rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
          {siteKey}
        </code>
      </div>

      <div className="mt-3">
        <label className="block text-xs font-medium text-slate-600">
          Embed snippet
        </label>
        <pre className="mt-1 overflow-x-auto rounded-lg border border-slate-200 bg-slate-900 px-3 py-3 text-xs leading-relaxed text-slate-100">
          {snippet}
        </pre>
        <button
          type="button"
          onClick={copy}
          className="mt-2 rounded-full bg-slate-800 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700"
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
          className="ml-2 rounded-full border border-red-300 px-4 py-1.5 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-50"
        >
          {rotating ? "Rotating..." : "Rotate key"}
        </button>
      </div>
    </div>
  );
}
