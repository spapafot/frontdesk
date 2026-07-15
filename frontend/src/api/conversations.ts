import { API_BASE } from "./client";

export type Rating = "up" | "down";

export interface ConversationSummary {
  id: number;
  title: string | null;
  started_at: string;
  rating: Rating | null;
  summary: string | null;
  mode: "ai" | "waiting" | "human" | "pending_ticket" | "closed";
  assigned_user_id: string | null;
  escalation_requested_at: string | null;
  accepted_at: string | null;
  closed_at: string | null;
  last_message_at: string | null;
}

export interface StoredMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  sender_type: "visitor" | "operator" | "ai" | "system";
  sender_display_name: string | null;
  created_at: string;
}

const base = `${API_BASE}/conversations`;

export const conversationsKey = (siteId: number) => `${base}?site_id=${siteId}`;

export async function listConversations(siteId: number): Promise<ConversationSummary[]> {
  const response = await fetch(conversationsKey(siteId));
  if (!response.ok) throw new Error(`Failed to load conversations (${response.status})`);
  return (await response.json()) as ConversationSummary[];
}

export async function getConversationMessages(
  siteId: number,
  id: number
): Promise<StoredMessage[]> {
  const response = await fetch(`${base}/${id}/messages?site_id=${siteId}`);
  if (!response.ok) throw new Error(`Failed to load conversation (${response.status})`);
  return (await response.json()) as StoredMessage[];
}

export async function renameConversation(
  siteId: number,
  id: number,
  title: string
): Promise<ConversationSummary> {
  const response = await fetch(`${base}/${id}?site_id=${siteId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new Error(`Failed to rename conversation (${response.status})`);
  return (await response.json()) as ConversationSummary;
}

export async function deleteConversation(siteId: number, id: number): Promise<void> {
  const response = await fetch(`${base}/${id}?site_id=${siteId}`, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete conversation (${response.status})`);
  }
}

export async function getConversationDetail(
  siteId: number,
  id: number
): Promise<ConversationSummary> {
  const response = await fetch(`${base}/${id}?site_id=${siteId}`);
  if (!response.ok) throw new Error(`Failed to load conversation (${response.status})`);
  return (await response.json()) as ConversationSummary;
}

export async function rateConversation(
  siteId: number,
  id: number,
  rating: Rating
): Promise<ConversationSummary> {
  const response = await fetch(`${base}/${id}/rating?site_id=${siteId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
  if (!response.ok) throw new Error(`Failed to rate conversation (${response.status})`);
  return (await response.json()) as ConversationSummary;
}
