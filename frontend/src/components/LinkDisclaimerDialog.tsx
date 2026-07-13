import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { TERMS_URL } from "../api/client";

interface Props {
  open: boolean;
  /** The URL about to be ingested, shown for confirmation. */
  url: string;
  /** Called once the user has ticked the acknowledgment and confirmed. */
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Blocking disclaimer shown before a web page is ingested. The user must
 * acknowledge they have the right to use the page's content and accept sole
 * responsibility for it before the page is added.
 */
export function LinkDisclaimerDialog({ open, url, onConfirm, onCancel }: Props) {
  const [agreed, setAgreed] = useState(false);

  // Reset the acknowledgment each time the dialog opens.
  useEffect(() => {
    if (open) setAgreed(false);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onCancel}
      role="presentation"
    >
      <div
        className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="link-disclaimer-title"
      >
        <h2
          id="link-disclaimer-title"
          className="text-base font-semibold text-slate-800"
        >
          Add this web page?
        </h2>
        {url && (
          <p className="mt-1 break-words text-xs text-slate-500">{url}</p>
        )}
        <p className="mt-3 text-sm text-slate-600">
          We'll fetch this page through a third-party reader and store its text
          in your knowledge base so the assistant can answer from it. You are
          solely responsible for the content you ingest and must have the right
          to use it.
        </p>

        <label className="mt-4 flex items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
          />
          <span>
            I confirm I have the right to use this page's content and accept sole
            responsibility for it, in line with the{" "}
            <a
              href={TERMS_URL}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-sky-600 underline"
            >
              Terms of Service
            </a>
            .
          </span>
        </label>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={!agreed}
            className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Add page
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
