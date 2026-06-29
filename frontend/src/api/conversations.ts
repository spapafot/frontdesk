import { API_BASE } from "./client";

export type Rating = "up" | "down";

export interface ConversationSummary {
  id: number;
  title: string | null;
  started_at: string;
  rating: Rating | null;
  summary: string | null;
}

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
}

export const conversationsKey = `${API_BASE}/conversations`;

export async function listConversations(): Promise<ConversationSummary[]> {
  const response = await fetch(conversationsKey);
  if (!response.ok) throw new Error(`Failed to load conversations (${response.status})`);
  return (await response.json()) as ConversationSummary[];
}

export async function getConversationMessages(id: number): Promise<StoredMessage[]> {
  const response = await fetch(`${conversationsKey}/${id}/messages`);
  if (!response.ok) throw new Error(`Failed to load conversation (${response.status})`);
  return (await response.json()) as StoredMessage[];
}

export async function renameConversation(
  id: number,
  title: string
): Promise<ConversationSummary> {
  const response = await fetch(`${conversationsKey}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error(`Failed to rename conversation (${response.status})`);
  return (await response.json()) as ConversationSummary;
}

export async function deleteConversation(id: number): Promise<void> {
  const response = await fetch(`${conversationsKey}/${id}`, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete conversation (${response.status})`);
  }
}

export async function getConversationDetail(id: number): Promise<ConversationSummary> {
  const response = await fetch(`${conversationsKey}/${id}`);
  if (!response.ok) throw new Error(`Failed to load conversation (${response.status})`);
  return (await response.json()) as ConversationSummary;
}

export async function rateConversation(
  id: number,
  rating: Rating
): Promise<ConversationSummary> {
  const response = await fetch(`${conversationsKey}/${id}/rating`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
  if (!response.ok) throw new Error(`Failed to rate conversation (${response.status})`);
  return (await response.json()) as ConversationSummary;
}
