import { FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { KnowledgeDocument } from "../api/knowledge";

interface Props {
  open: boolean;
  /** Existing entry to edit, or null to add a new one. */
  doc: KnowledgeDocument | null;
  /** Queue the entry; the parent closes this dialog synchronously. */
  onSubmit: (question: string, answer: string) => void;
  onClose: () => void;
}

/** Modal for adding or editing an FAQ entry (question + exact answer). */
export function FaqDialog({ open, doc, onSubmit, onClose }: Props) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Reset (or prefill, when editing) each time the dialog opens.
  useEffect(() => {
    if (open) {
      setQuestion(doc?.title ?? "");
      setAnswer(doc?.content ?? "");
      setError(null);
    }
  }, [open, doc]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    const a = answer.trim();
    if (q.length < 5) {
      setError("The question must be at least 5 characters.");
      return;
    }
    if (a.length < 10) {
      setError("The answer must be at least 10 characters.");
      return;
    }
    setError(null);
    onSubmit(q, a);
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
        className="w-full max-w-lg space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="faq-dialog-title"
      >
        <div>
          <h2 id="faq-dialog-title" className="text-base font-semibold text-slate-800">
            {doc ? "Edit FAQ" : "Add FAQ"}
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            This is the exact wording the assistant will draw on when a visitor
            asks something similar.
          </p>
        </div>

        <label className="block text-sm font-medium text-slate-700">
          Question
          <input
            type="text"
            autoFocus
            required
            maxLength={255}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What are your opening hours?"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
          />
          <span className="mt-1 block text-right text-xs font-normal text-slate-400">
            {question.length}/255
          </span>
        </label>

        <label className="block text-sm font-medium text-slate-700">
          Answer
          <textarea
            required
            maxLength={4000}
            rows={6}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="e.g. We are open 9am to 5pm, Monday to Friday."
            className="mt-1 w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
          />
          <span className="mt-1 block text-right text-xs font-normal text-slate-400">
            {answer.length}/4000
          </span>
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
            className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-sky-700"
          >
            Save FAQ
          </button>
        </div>
      </form>
    </div>,
    document.body
  );
}
