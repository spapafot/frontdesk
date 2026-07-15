import { useEffect } from "react";
import { createPortal } from "react-dom";
import useSWR from "swr";
import {
  KnowledgeChunk,
  KnowledgeDocument,
  chunksKey,
  fetchChunks,
} from "../api/knowledge";

interface Props {
  open: boolean;
  siteId: number;
  doc: KnowledgeDocument | null;
  onClose: () => void;
}

/**
 * Read-only preview of the exact chunks stored for a document, so an admin can
 * verify what the assistant actually ingested and searches over.
 */
export function ChunkPreviewDialog({ open, siteId, doc, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const {
    data: chunks,
    error,
    isLoading,
  } = useSWR<KnowledgeChunk[]>(
    open && doc ? chunksKey(siteId, doc.id) : null,
    () => fetchChunks(siteId, (doc as KnowledgeDocument).id),
  );

  if (!open || !doc) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="chunk-preview-title"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2
              id="chunk-preview-title"
              className="truncate text-base font-semibold text-slate-800"
            >
              {doc.title}
            </h2>
            <p className="mt-0.5 text-xs text-slate-500">
              {doc.type === "faq"
                ? "The exact text stored and searched for this FAQ."
                : `The exact text stored and searched for answers${
                    doc.source_url ? ", extracted from the page." : "."
                  }`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-100"
          >
            Close
          </button>
        </div>

        <div className="mt-4 min-h-0 flex-1 overflow-y-auto">
          {isLoading && (
            <p className="text-sm text-slate-500">Loading preview…</p>
          )}
          {error && (
            <p className="text-sm text-red-600">Couldn't load the preview.</p>
          )}
          {chunks && chunks.length === 0 && (
            <p className="text-sm text-slate-500">
              No text was extracted from this source.
            </p>
          )}
          {chunks && chunks.length > 0 && (
            <ol className="space-y-3">
              {chunks.map((c, i) => (
                <li
                  key={c.id}
                  className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                >
                  <div className="mb-1 text-xs font-medium uppercase text-slate-400">
                    Chunk {i + 1}
                  </div>
                  <p className="whitespace-pre-wrap break-words text-sm text-slate-700">
                    {c.content}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </div>

        {chunks && chunks.length > 0 && (
          <p className="mt-3 shrink-0 text-xs text-slate-400">
            {chunks.length} chunk{chunks.length === 1 ? "" : "s"} - these are
            what the assistant retrieves from.
          </p>
        )}
      </div>
    </div>,
    document.body,
  );
}
