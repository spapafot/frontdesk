import { API_BASE } from "./client";

export interface SocketTicket {
  ticket: string;
  websocket_path: string;
  conversation_id: number | null;
  conversation_token?: string | null;
  expires_in: number;
}

export interface LiveMessage {
  id: number;
  client_message_id: string | null;
  role: "user" | "assistant";
  content: string;
  sender_type: "visitor" | "operator" | "ai" | "system";
  sender_user_id: string | null;
  sender_display_name: string | null;
  created_at: string;
}

export interface LiveState {
  conversation_id: number;
  profile_id: number;
  mode: "ai" | "waiting" | "human" | "pending_ticket" | "closed";
  assigned_user_id: string | null;
  escalation_requested_at: string | null;
  escalation_expires_at: string | null;
  accepted_at: string | null;
  closed_at: string | null;
  messages?: LiveMessage[];
}

async function json<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? `Request failed (${response.status})`);
  return body as T;
}

export async function operatorSocketTicket(
  siteId: number,
  channel: "inbox" | "conversation",
  conversationId?: number,
): Promise<SocketTicket> {
  return json(
    await fetch(`${API_BASE}/live/operator/socket-ticket`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        site_id: siteId,
        channel,
        conversation_id: conversationId,
      }),
    }),
  );
}

export function openLiveSocket(ticket: SocketTicket): WebSocket {
  const url = new URL(ticket.websocket_path, API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(url, ["live-v1", `ticket.${ticket.ticket}`]);
}

export interface CallbackTicket {
  id: number;
  conversation_id: number;
  customer_name: string | null;
  customer_email: string;
  customer_message: string | null;
  status: "pending" | "resolved";
  created_at: string;
  resolved_at: string | null;
}

export async function listCallbacks(siteId: number): Promise<CallbackTicket[]> {
  return json(await fetch(`${API_BASE}/live/callbacks?site_id=${siteId}`));
}

export async function resolveCallback(siteId: number, ticketId: number): Promise<CallbackTicket> {
  return json(
    await fetch(`${API_BASE}/live/callbacks/${ticketId}/resolve?site_id=${siteId}`, {
      method: "POST",
    }),
  );
}
