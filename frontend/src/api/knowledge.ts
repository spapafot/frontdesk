import { API_BASE } from "./client";

export interface KnowledgeDocument {
  id: number;
  title: string;
  type: string;
  /** Set for link entries (type === "url"); null for uploaded files. */
  source_url: string | null;
  is_active: boolean;
  processing_status: "queued" | "processing" | "ready" | "failed";
  chunk_count: number;
  created_at: string;
  processed_at: string | null;
}

export interface KnowledgeChunk {
  id: number;
  content: string;
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const base = `${API_BASE}/knowledge/documents`;

export const documentsKey = (siteId: number) => `${base}?site_id=${siteId}`;

export async function fetchDocuments(siteId: number): Promise<KnowledgeDocument[]> {
  return handle(await fetch(documentsKey(siteId)));
}

export async function uploadDocument(
  siteId: number,
  file: File
): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.append("file", file);
  return handle(await fetch(documentsKey(siteId), { method: "POST", body: form }));
}

export async function addLink(
  siteId: number,
  url: string
): Promise<KnowledgeDocument> {
  return handle(
    await fetch(`${API_BASE}/knowledge/links?site_id=${siteId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    })
  );
}

export async function rescanDocument(
  siteId: number,
  id: number
): Promise<KnowledgeDocument> {
  return handle(
    await fetch(`${base}/${id}/rescan?site_id=${siteId}`, { method: "POST" })
  );
}

export async function deleteDocument(siteId: number, id: number): Promise<void> {
  return handle(await fetch(`${base}/${id}?site_id=${siteId}`, { method: "DELETE" }));
}

export async function toggleDocument(
  siteId: number,
  id: number,
  isActive: boolean
): Promise<KnowledgeDocument> {
  return handle(
    await fetch(`${base}/${id}?site_id=${siteId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive }),
    })
  );
}

export const chunksKey = (siteId: number, id: number) =>
  `${base}/${id}/chunks?site_id=${siteId}`;

export async function fetchChunks(
  siteId: number,
  id: number
): Promise<KnowledgeChunk[]> {
  return handle(await fetch(chunksKey(siteId, id)));
}
