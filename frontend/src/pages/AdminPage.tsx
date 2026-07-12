import { useRef, useState } from "react";
import useSWR from "swr";
import {
  KnowledgeDocument,
  deleteDocument,
  documentsKey,
  fetchDocuments,
  toggleDocument,
  uploadDocument,
} from "../api/knowledge";

const ACCEPT = ".txt,.pdf,.doc,.docx,.xls,.xlsx";

export function AdminPage() {
  const { data: documents, error, isLoading, mutate } = useSWR<KnowledgeDocument[]>(
    documentsKey,
    fetchDocuments,
    {
      refreshInterval: (latest) =>
        latest?.some(
          (doc) =>
            doc.processing_status === "queued" ||
            doc.processing_status === "processing"
        )
          ? 5000
          : 0,
    }
  );
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const onFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploadError(null);
    setUploadNotice(null);
    setUploading(true);
    let queuedAny = false;
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(file);
        queuedAny = true;
      }
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      if (queuedAny) {
        await mutate().catch(() => undefined);
        setUploadNotice(
          "Your document will be ready soon, after that you can start using our widget, check again in a minute or two!"
        );
      }
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const onDelete = async (id: number) => {
    await deleteDocument(id);
    await mutate();
  };

  const onToggle = async (doc: KnowledgeDocument) => {
    await toggleDocument(doc.id, !doc.is_active);
    await mutate();
  };

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col p-4">
      <h2 className="text-lg font-semibold text-slate-800">Knowledge base</h2>
      <p className="mt-1 text-sm text-slate-500">
        Upload the documents the assistant is allowed to answer from. Supported types:
        TXT, PDF, DOC, DOCX, XLS, XLSX.
      </p>

      <div className="mt-4 rounded-xl border-2 border-dashed border-slate-300 bg-white p-6 text-center">
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
        {uploadError && <p className="mt-3 text-sm text-red-600">{uploadError}</p>}
        {uploadNotice && (
          <p className="mt-3 text-sm text-sky-700" role="status">
            {uploadNotice}
          </p>
        )}
      </div>

      <div className="mt-6 flex-1 overflow-y-auto">
        {isLoading && <p className="text-sm text-slate-500">Loading documents...</p>}
        {error && <p className="text-sm text-red-600">Failed to load documents.</p>}
        {documents && documents.length === 0 && (
          <p className="text-sm text-slate-500">
            No documents yet. Upload a file to give the assistant something to answer from.
          </p>
        )}
        {documents && documents.length > 0 && (
          <div className="overflow-x-auto">
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
              {documents.map((doc) => (
                <tr key={doc.id} className="border-b border-slate-100">
                  <td className="py-2 pr-2 font-medium text-slate-800">{doc.title}</td>
                  <td className="py-2 pr-2 uppercase text-slate-500">{doc.type}</td>
                  <td className="py-2 pr-2 text-slate-500">
                    {doc.processing_status === "ready" ? doc.chunk_count : "—"}
                  </td>
                  <td className="py-2 pr-2">
                    {doc.processing_status === "queued" && (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">Queued</span>
                    )}
                    {doc.processing_status === "processing" && (
                      <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-700">Processing</span>
                    )}
                    {doc.processing_status === "ready" && (
                      <span className={`rounded-full px-2 py-0.5 text-xs ${doc.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                        {doc.is_active ? "Ready / Active" : "Ready / Inactive"}
                      </span>
                    )}
                    {doc.processing_status === "failed" && (
                      <div>
                        <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-700">Failed</span>
                        <p className="mt-1 max-w-56 text-xs text-red-600">
                          Your document failed to process. Please{" "}
                          <a className="font-medium underline" href="mailto:support@plugandplay.gr">contact support</a>.
                        </p>
                      </div>
                    )}
                  </td>
                  <td className="py-2 text-right">
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
        )}
      </div>
    </div>
  );
}
