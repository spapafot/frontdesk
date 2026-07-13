import { FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface Props {
  open: boolean;
  initialName: string;
  /** Rename the site. Should reject with an Error whose message is shown. */
  onSubmit: (name: string) => Promise<void>;
  onClose: () => void;
}

/** Modal for renaming a website (its display name). */
export function RenameWebsiteDialog({ open, initialName, onSubmit, onClose }: Props) {
  const [name, setName] = useState(initialName);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-fill with the current name each time the dialog opens.
  useEffect(() => {
    if (open) {
      setName(initialName);
      setError(null);
      setBusy(false);
    }
  }, [open, initialName]);

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
      await onSubmit(trimmed);
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
        aria-labelledby="rename-website-title"
      >
        <h2 id="rename-website-title" className="text-base font-semibold text-slate-800">
          Rename website
        </h2>

        <label className="block text-sm font-medium text-slate-700">
          Website name
          <input
            type="text"
            autoFocus
            required
            maxLength={255}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
          />
        </label>

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
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </div>,
    document.body
  );
}
