import { API_BASE } from "./client";

export interface KnowledgeDocument {
  id: number;
  title: string;
  type: string;
  is_active: boolean;
  chunk_count: number;
  created_at: string;
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

export const documentsKey = `${API_BASE}/knowledge/documents`;

export async function fetchDocuments(): Promise<KnowledgeDocument[]> {
  return handle(await fetch(documentsKey));
}

export async function uploadDocument(file: File): Promise<KnowledgeDocument> {
  const form = new FormData();
  form.append("file", file);
  return handle(
    await fetch(documentsKey, { method: "POST", body: form })
  );
}

export async function deleteDocument(id: number): Promise<void> {
  return handle(await fetch(`${documentsKey}/${id}`, { method: "DELETE" }));
}

export async function toggleDocument(
  id: number,
  isActive: boolean
): Promise<KnowledgeDocument> {
  return handle(
    await fetch(`${documentsKey}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive }),
    })
  );
}

export async function fetchChunks(id: number): Promise<KnowledgeChunk[]> {
  return handle(await fetch(`${documentsKey}/${id}/chunks`));
}
