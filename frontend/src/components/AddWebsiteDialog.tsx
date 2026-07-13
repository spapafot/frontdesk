import { FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface Props {
  open: boolean;
  /** Create the site. Should reject with an Error whose message is shown. */
  onSubmit: (name: string, url: string) => Promise<void>;
  onClose: () => void;
}

/** Modal for creating a website: a display name plus its authorized origin. */
export function AddWebsiteDialog({ open, onSubmit, onClose }: Props) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset the form each time the dialog opens.
  useEffect(() => {
    if (open) {
      setName("");
      setUrl("");
      setError(null);
      setBusy(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(trimmed, url.trim());
      onClose();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <form
        onSubmit={submit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm space-y-4 rounded-xl bg-white p-5 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-website-title"
      >
        <div>
          <h2 id="add-website-title" className="text-base font-semibold text-slate-800">
            Add website
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Each website gets its own assistant, knowledge base, and widget.
          </p>
        </div>

        <label className="block text-sm font-medium text-slate-700">
          Website name
          <input
            type="text"
            autoFocus
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Acme Store"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
          />
        </label>

        <div>
          <label className="block text-sm font-medium text-slate-700">
            Website URL <span className="font-normal text-slate-400">(optional)</span>
            <input
              type="url"
              maxLength={255}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
          </label>
          <p className="mt-1 text-xs text-slate-400">
            The exact origin where the widget runs. You can set or change this later in Settings.
          </p>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-60"
          >
            {busy ? "Creating…" : "Create website"}
          </button>
        </div>
      </form>
    </div>,
    document.body
  );
}
