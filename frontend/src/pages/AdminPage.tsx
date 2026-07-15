import { FormEvent, useRef, useState } from "react";
import useSWR from "swr";
import {
  KnowledgeDocument,
  addFaq,
  addLink,
  deleteDocument,
  documentsKey,
  fetchDocuments,
  rescanDocument,
  toggleDocument,
  updateFaq,
  uploadDocument,
} from "../api/knowledge";
import { TERMS_URL } from "../api/client";
import { ChunkPreviewDialog } from "../components/ChunkPreviewDialog";
import { FaqDialog } from "../components/FaqDialog";
import { LinkDisclaimerDialog } from "../components/LinkDisclaimerDialog";
import { useSite } from "../components/SiteProvider";
import { Skeleton } from "../components/Skeleton";
import { useToast } from "../components/Toast";

const ACCEPT = ".txt,.pdf,.doc,.docx,.xls,.xlsx";

export function AdminPage() {
  const { selectedSiteId } = useSite();
  const { showToast } = useToast();
  const {
    data: documents,
    error,
    isLoading,
    mutate,
  } = useSWR<KnowledgeDocument[]>(
    selectedSiteId != null ? documentsKey(selectedSiteId) : null,
    () => fetchDocuments(selectedSiteId as number),
    {
      refreshInterval: (latest) =>
        latest?.some(
          (doc) =>
            doc.processing_status === "queued" ||
            doc.processing_status === "processing",
        )
          ? 5000
          : 0,
    },
  );
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [linkUrl, setLinkUrl] = useState("");
  const [addingLink, setAddingLink] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkNotice, setLinkNotice] = useState<string | null>(null);
  const [showLinkDisclaimer, setShowLinkDisclaimer] = useState(false);
  const [previewDoc, setPreviewDoc] = useState<KnowledgeDocument | null>(null);
  // null = closed; { doc: null } = add mode; { doc } = edit mode.
  const [faqDialog, setFaqDialog] = useState<{ doc: KnowledgeDocument | null } | null>(
    null,
  );

  const onFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadError(null);
    setUploadNotice(null);
    setUploading(true);
    let queuedAny = false;
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(selectedSiteId as number, file);
        queuedAny = true;
      }
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      if (queuedAny) {
        await mutate().catch(() => undefined);
        setUploadNotice(
          "Your document will be ready soon, after that you can start using our widget, check again in a minute or two!",
        );
      }
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const onAddLink = (e: FormEvent) => {
    e.preventDefault();
    if (!linkUrl.trim() || addingLink) return;
    setLinkError(null);
    setLinkNotice(null);
    // Require the responsibility acknowledgment before fetching the page.
    setShowLinkDisclaimer(true);
  };

  const confirmAddLink = async () => {
    setShowLinkDisclaimer(false);
    const url = linkUrl.trim();
    if (!url) return;
    setAddingLink(true);
    try {
      await addLink(selectedSiteId as number, url);
      await mutate().catch(() => undefined);
      setLinkUrl("");
      setLinkNotice(
        "We're reading that page now. It'll be ready in a minute or two - check back shortly!",
      );
    } catch (err) {
      setLinkError((err as Error).message);
    } finally {
      setAddingLink(false);
    }
  };

  const onRescan = async (doc: KnowledgeDocument) => {
    const siteId = selectedSiteId as number;
    try {
      await mutate(
        async (docs) => {
          const updated = await rescanDocument(siteId, doc.id);
          return docs?.map((d) => (d.id === updated.id ? updated : d)) ?? [];
        },
        {
          // Flip the row to "queued" instantly; polling drives it back to ready.
          optimisticData: (docs) =>
            docs?.map((d) =>
              d.id === doc.id ? { ...d, processing_status: "queued" } : d,
            ) ?? [],
          rollbackOnError: true,
          revalidate: false,
        },
      );
    } catch {
      showToast("Couldn't rescan the page. Try again.");
    }
  };

  const onDelete = async (id: number) => {
    const siteId = selectedSiteId as number;
    try {
      await mutate(
        async (docs) => {
          await deleteDocument(siteId, id);
          return docs?.filter((d) => d.id !== id) ?? [];
        },
        {
          optimisticData: (docs) => docs?.filter((d) => d.id !== id) ?? [],
          rollbackOnError: true,
          revalidate: false,
        },
      );
    } catch {
      showToast("Couldn't delete the document. Restored.");
    }
  };

  const onToggle = async (doc: KnowledgeDocument) => {
    const siteId = selectedSiteId as number;
    try {
      await mutate(
        async (docs) => {
          const updated = await toggleDocument(siteId, doc.id, !doc.is_active);
          return docs?.map((d) => (d.id === updated.id ? updated : d)) ?? [];
        },
        {
          optimisticData: (docs) =>
            docs?.map((d) =>
              d.id === doc.id ? { ...d, is_active: !doc.is_active } : d,
            ) ?? [],
          rollbackOnError: true,
          revalidate: false,
        },
      );
    } catch {
      showToast("Couldn't update the document. Restored.");
    }
  };

  // FAQ entries are indexed synchronously, so the saved row comes back
  // already "ready" - patch the cache from the response, no refetch needed.
  const onSaveFaq = async (question: string, answer: string) => {
    const siteId = selectedSiteId as number;
    const editing = faqDialog?.doc ?? null;
    if (editing) {
      const updated = await updateFaq(siteId, editing.id, question, answer);
      await mutate(
        (docs) => docs?.map((d) => (d.id === updated.id ? updated : d)) ?? [updated],
        { revalidate: false },
      );
    } else {
      const created = await addFaq(siteId, question, answer);
      // The list is newest-first, so prepend to match server order.
      await mutate((docs) => [created, ...(docs ?? [])], { revalidate: false });
    }
  };

  const fileDocs =
    documents?.filter((d) => d.type !== "url" && d.type !== "faq") ?? [];
  const urlDocs = documents?.filter((d) => d.type === "url") ?? [];
  const faqDocs = documents?.filter((d) => d.type === "faq") ?? [];

  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto p-4">
      <h2 className="text-lg font-semibold text-slate-800">Knowledge base</h2>
      <p className="mt-1 text-sm text-slate-500">
        Everything the assistant is allowed to answer from. Add files, web
        pages, or FAQs below.
      </p>

      {error && (
        <p className="mt-4 text-sm text-red-600">
          Failed to load your knowledge base.
        </p>
      )}

      {/* Documents ------------------------------------------------------- */}
      <section className="mt-6">
        <h3 className="text-sm font-semibold text-slate-700">Documents</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          Upload files: TXT, PDF, DOC, DOCX, XLS, XLSX.
        </p>

        <div className="mt-3 rounded-xl border-2 border-dashed border-slate-300 bg-white p-6 text-center">
          <input
            ref={fileInput}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => onFiles(e.target.files)}
          />
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
            className="rounded-full bg-sky-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Choose files to upload"}
          </button>
          <p className="mt-2 text-xs text-slate-400">Max 10 MB per file.</p>
          <p className="mt-1 text-xs text-slate-400">
            By uploading, you confirm you have the right to use the content and
            accept our{" "}
            <a
              href={TERMS_URL}
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-slate-500"
            >
              Terms of Service
            </a>
            .
          </p>
          {uploadError && (
            <p className="mt-3 text-sm text-red-600">{uploadError}</p>
          )}
          {uploadNotice && (
            <p className="mt-3 text-sm text-sky-700" role="status">
              {uploadNotice}
            </p>
          )}
        </div>

        <div className="mt-4">
          {isLoading && <DocumentsSkeleton />}
          {documents &&
            (fileDocs.length === 0 ? (
              <p className="text-sm text-slate-500">
                No documents yet. Upload a file above.
              </p>
            ) : (
              <DocumentTable
                docs={fileDocs}
                showType
                onPreview={setPreviewDoc}
                onToggle={onToggle}
                onDelete={onDelete}
              />
            ))}
        </div>
      </section>

      {/* Web pages ------------------------------------------------------- */}
      <section className="mt-8">
        <h3 className="text-sm font-semibold text-slate-700">Web pages</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          Add a page by its URL. We read and keep its text - use Rescan to
          refresh it later.
        </p>

        <form
          onSubmit={onAddLink}
          className="mt-3 rounded-xl border border-slate-200 bg-white p-4"
        >
          <label htmlFor="knowledge-link-url" className="sr-only">
            Web page URL
          </label>
          <div className="flex gap-2">
            <input
              id="knowledge-link-url"
              type="url"
              required
              maxLength={2048}
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              placeholder="https://example.com/pricing"
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
            />
            <button
              type="submit"
              disabled={addingLink}
              className="shrink-0 rounded-full bg-sky-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
            >
              {addingLink ? "Adding…" : "Add link"}
            </button>
          </div>
          {linkError && (
            <p className="mt-2 text-sm text-red-600">{linkError}</p>
          )}
          {linkNotice && (
            <p className="mt-2 text-sm text-sky-700" role="status">
              {linkNotice}
            </p>
          )}
        </form>

        <div className="mt-4">
          {documents &&
            (urlDocs.length === 0 ? (
              <p className="text-sm text-slate-500">
                No web pages yet. Paste a URL above to add one.
              </p>
            ) : (
              <DocumentTable
                docs={urlDocs}
                onPreview={setPreviewDoc}
                onRescan={onRescan}
                onToggle={onToggle}
                onDelete={onDelete}
              />
            ))}
        </div>
      </section>

      {/* FAQs ------------------------------------------------------------ */}
      <section className="mt-8">
        <h3 className="text-sm font-semibold text-slate-700">FAQs</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          Add common questions with the exact answers you want the assistant to
          give. Ready to use instantly.
        </p>

        <div className="mt-3 rounded-xl border border-slate-200 bg-white p-4">
          <button
            type="button"
            onClick={() => setFaqDialog({ doc: null })}
            className="rounded-full bg-sky-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-sky-700"
          >
            Add FAQ
          </button>
        </div>

        <div className="mt-4">
          {documents &&
            (faqDocs.length === 0 ? (
              <p className="text-sm text-slate-500">
                No FAQs yet. Add your first question and answer.
              </p>
            ) : (
              <DocumentTable
                docs={faqDocs}
                onPreview={setPreviewDoc}
                onEdit={(doc) => setFaqDialog({ doc })}
                onToggle={onToggle}
                onDelete={onDelete}
              />
            ))}
        </div>
      </section>

      <LinkDisclaimerDialog
        open={showLinkDisclaimer}
        url={linkUrl.trim()}
        onConfirm={confirmAddLink}
        onCancel={() => setShowLinkDisclaimer(false)}
      />

      <FaqDialog
        open={faqDialog !== null}
        doc={faqDialog?.doc ?? null}
        onSubmit={onSaveFaq}
        onClose={() => setFaqDialog(null)}
      />

      <ChunkPreviewDialog
        open={previewDoc !== null}
        siteId={selectedSiteId as number}
        doc={previewDoc}
        onClose={() => setPreviewDoc(null)}
      />
    </div>
  );
}

function DocumentTable({
  docs,
  showType,
  onPreview,
  onRescan,
  onEdit,
  onToggle,
  onDelete,
}: {
  docs: KnowledgeDocument[];
  showType?: boolean;
  onPreview: (doc: KnowledgeDocument) => void;
  onRescan?: (doc: KnowledgeDocument) => void;
  onEdit?: (doc: KnowledgeDocument) => void;
  onToggle: (doc: KnowledgeDocument) => void;
  onDelete: (id: number) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
            <th className="py-2">Title</th>
            {showType && <th className="py-2">Type</th>}
            <th className="py-2">Chunks</th>
            <th className="py-2">Status</th>
            <th className="py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((doc) => (
            <tr key={doc.id} className="border-b border-slate-100">
              <td className="py-2 pr-2 font-medium text-slate-800">
                <div>{doc.title}</div>
                {doc.source_url && (
                  <a
                    href={doc.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="block max-w-64 truncate text-xs font-normal text-sky-600 hover:underline"
                  >
                    {doc.source_url}
                  </a>
                )}
              </td>
              {showType && (
                <td className="py-2 pr-2 uppercase text-slate-500">
                  {doc.type}
                </td>
              )}
              <td className="py-2 pr-2 text-slate-500">
                {doc.processing_status === "ready" ? doc.chunk_count : "-"}
              </td>
              <td className="py-2 pr-2">
                {doc.processing_status === "queued" && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                    Queued
                  </span>
                )}
                {doc.processing_status === "processing" && (
                  <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-700">
                    Processing
                  </span>
                )}
                {doc.processing_status === "ready" && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${doc.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}
                  >
                    {doc.is_active ? "Ready / Active" : "Ready / Inactive"}
                  </span>
                )}
                {doc.processing_status === "failed" && (
                  <div>
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">
                      Failed
                    </span>
                    <p className="mt-1 max-w-56 text-xs text-red-600">
                      This source couldn't be processed. Please{" "}
                      <a
                        className="font-medium underline"
                        href="mailto:support@plugandplay.gr"
                      >
                        contact support
                      </a>
                      .
                    </p>
                  </div>
                )}
              </td>
              <td className="py-2 text-right">
                <button
                  type="button"
                  onClick={() => onPreview(doc)}
                  disabled={doc.processing_status !== "ready"}
                  className="mr-3 text-xs font-medium text-sky-600 hover:underline disabled:cursor-not-allowed disabled:text-slate-300 disabled:no-underline"
                >
                  Preview
                </button>
                {onRescan && doc.type === "url" && (
                  <button
                    type="button"
                    onClick={() => onRescan(doc)}
                    disabled={doc.processing_status !== "ready"}
                    className="mr-3 text-xs font-medium text-sky-600 hover:underline disabled:cursor-not-allowed disabled:text-slate-300 disabled:no-underline"
                  >
                    Rescan
                  </button>
                )}
                {onEdit && doc.type === "faq" && (
                  <button
                    type="button"
                    onClick={() => onEdit(doc)}
                    disabled={doc.processing_status !== "ready"}
                    className="mr-3 text-xs font-medium text-sky-600 hover:underline disabled:cursor-not-allowed disabled:text-slate-300 disabled:no-underline"
                  >
                    Edit
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => onToggle(doc)}
                  disabled={doc.processing_status !== "ready"}
                  className="mr-3 text-xs font-medium text-sky-600 hover:underline disabled:cursor-not-allowed disabled:text-slate-300 disabled:no-underline"
                >
                  {doc.is_active ? "Disable" : "Enable"}
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(doc.id)}
                  className="text-xs font-medium text-red-600 hover:underline"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DocumentsSkeleton() {
  return (
    <div
      className="overflow-x-auto"
      role="status"
      aria-label="Loading documents"
    >
      <table className="w-full min-w-[32rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
            <th className="py-2">Title</th>
            <th className="py-2">Type</th>
            <th className="py-2">Chunks</th>
            <th className="py-2">Status</th>
            <th className="py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 4 }).map((_, i) => (
            <tr key={i} className="border-b border-slate-100">
              <td className="py-3 pr-2">
                <Skeleton className="h-4 w-40" />
              </td>
              <td className="py-3 pr-2">
                <Skeleton className="h-4 w-10" />
              </td>
              <td className="py-3 pr-2">
                <Skeleton className="h-4 w-8" />
              </td>
              <td className="py-3 pr-2">
                <Skeleton className="h-5 w-20 rounded-full" />
              </td>
              <td className="py-3">
                <div className="flex justify-end gap-3">
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-12" />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
