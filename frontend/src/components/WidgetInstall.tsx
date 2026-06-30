import { useState } from "react";

interface Props {
  siteKey: string | null;
}

// Where the built widget loader is hosted in production. Overridable at build
// time via VITE_WIDGET_SRC; falls back to a sensible placeholder.
const WIDGET_SRC =
  (import.meta.env.VITE_WIDGET_SRC as string | undefined) ??
  "https://cdn.yourdomain.com/widget.js";

export function WidgetInstall({ siteKey }: Props) {
  const [copied, setCopied] = useState(false);

  if (!siteKey) return null;

  const snippet = `<script
  src="${WIDGET_SRC}"
  data-site-key="${siteKey}"
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
      <h3 className="text-sm font-semibold text-slate-800">Install on your website</h3>
      <p className="mt-1 text-xs text-slate-500">
        Paste this snippet just before the closing &lt;/body&gt; tag on your site. The
        site key is public and only identifies your assistant.
      </p>

      <div className="mt-3">
        <label className="block text-xs font-medium text-slate-600">Site key</label>
        <code className="mt-1 block w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
          {siteKey}
        </code>
      </div>

      <div className="mt-3">
        <label className="block text-xs font-medium text-slate-600">Embed snippet</label>
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
      </div>
    </div>
  );
}
